"""On-demand data refresh: the whole weekly update, run from the site's button.

Runs the update scripts in order, each in its own process (a crashed or
stuck FBref scrape can't take the API down with it), and reports progress:

1. results        football-data.co.uk, this season's file    a few seconds
2. players        FBref season stats (squads, minutes, goals) about a minute
3. match_players  FBref match reports, new matches only       25-60 s per match
4. track_record   this season's predictions vs results        a few seconds
5. betting        betting backtest, this season recomputed    a few seconds

then the API reloads its data, and the data files that changed are
committed and pushed to GitHub so the repository stays the reference copy.

An FBref failure (rate limiting, a site change) doesn't stop the rest: the
site keeps running on the last player data it has.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from pl_predictor.config import ROOT_DIR, current_season_start_year, season_code, season_label

PUBLISHED_PATHS = ("data/players", "reports")
# "[3/10] week 6: Arsenal vs Chelsea" (data/match_players.py)
MATCH_PROGRESS = re.compile(r"\[(\d+)/(\d+)\] week")


@dataclass
class Step:
    key: str
    label: str
    command: list[str] | None = None  # script + arguments; None for the in-process steps
    timeout: float = 15 * 60
    status: str = "pending"  # pending, running, done, failed, skipped
    detail: str = ""
    started: float | None = None
    finished: float | None = None

    def as_dict(self) -> dict:
        end = self.finished or (time.time() if self.started else None)
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
            "seconds": round(end - self.started) if self.started and end else None,
        }


def default_steps(season: int) -> list[Step]:
    year = str(season)
    return [
        Step("results", "Résultats des matchs",
             ["scripts/download_data.py", "--force", "--start-year", year, "--end-year", year], 5 * 60),
        Step("players", "Statistiques des joueurs", ["scripts/download_player_data.py"], 20 * 60),
        Step("match_players", "Feuilles de match", ["scripts/download_match_players.py"], 120 * 60),
        Step("track_record", "Bilan de la saison", ["scripts/build_track_record.py"], 15 * 60),
        Step("betting", "Analyse des paris", ["scripts/build_betting.py"], 30 * 60),
    ]


def _iso(t: float | None) -> str | None:
    return dt.datetime.fromtimestamp(t).isoformat(timespec="seconds") if t else None


def data_counts(season: int, root: Path = ROOT_DIR) -> dict:
    """Results and match reports stored for `season`.

    A result counts once known from either source: football-data.co.uk's
    file, or a score in FBref's schedule, which gets results first (see
    data/load.py add_fbref_results). One source covers the other's matches
    in practice, so the larger count is the number of known results.
    """
    football_data = fbref = reports = 0
    raw = root / "data" / "raw" / f"E0_{season_code(season)}.csv"
    if raw.exists():
        football_data = sum(1 for line in raw.read_bytes().splitlines()[1:] if line.strip(b", \r"))
    schedule = root / "data" / "players" / f"schedule_{season}.csv"
    if schedule.exists():
        fbref = int(pd.read_csv(schedule, usecols=["home_goals"])["home_goals"].notna().sum())
    stats = root / "data" / "players" / f"match_stats_{season}.csv"
    if stats.exists():
        reports = int(pd.read_csv(stats, usecols=["game_id"])["game_id"].nunique())
    return {"results": max(football_data, fbref), "match_reports": reports}


class Refresh:
    """One run of the pipeline. `run()` blocks; the API runs it in a thread
    and reads `as_dict()` meanwhile."""

    def __init__(
        self,
        season: int,
        reload: Callable[[], None] | None = None,
        publish: bool = True,
        root: Path = ROOT_DIR,
        echo: bool = False,
        steps: list[Step] | None = None,
    ):
        self.season = season
        self.root = root
        self.reload = reload
        self.publish = publish
        self.echo = echo
        self.steps = steps if steps is not None else default_steps(season)
        if reload:
            self.steps.append(Step("reload", "Rechargement du site"))
        if publish:
            self.steps.append(Step("publish", "Publication sur GitHub"))
        self.state = "running"
        self.started = time.time()
        self.finished: float | None = None
        self.before: dict = {}
        self.after: dict = {}
        self._process: subprocess.Popen | None = None
        self._cancelled = False

    # ------------------------------------------------------------------ run
    def run(self) -> None:
        self.before = data_counts(self.season, self.root)
        for step in self.steps:
            if self._cancelled:
                step.status = "skipped"
                continue
            step.status, step.started = "running", time.time()
            try:
                step.status, step.detail = self._run_step(step)
            except Exception as exc:  # noqa: BLE001 - one broken step must not kill the run
                step.status, step.detail = "failed", str(exc)[:200]
            step.finished = time.time()
            if self.echo:
                print(f"-> {step.label}: {step.status}{' - ' + step.detail if step.detail else ''}", flush=True)
        self.after = data_counts(self.season, self.root)
        self.finished = time.time()
        self.state = "error" if any(s.status == "failed" for s in self.steps) else "done"

    def cancel(self) -> None:
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.kill()

    def _run_step(self, step: Step) -> tuple[str, str]:
        if step.command:
            return self._run_script(step)
        if step.key == "reload":
            self.reload()
            return "done", ""
        if step.key == "publish":
            return self._publish()
        raise ValueError(f"unknown step {step.key}")

    def _run_script(self, step: Step) -> tuple[str, str]:
        """Run one script, following its output through a log file.

        Not a pipe: the FBref scrapers start a Chrome driver that outlives
        them and inherits their output handle, so a pipe would never reach
        end-of-file and the step would hang although the script had finished.
        Here the script's exit is what ends the step.
        """
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        fd, name = tempfile.mkstemp(prefix=f"pl-refresh-{step.key}-", suffix=".log")
        os.close(fd)
        log_path = Path(name)
        last = ""
        pending = b""

        def consume(chunk: bytes, final: bool = False) -> None:
            nonlocal last, pending
            pending += chunk
            *lines, pending = pending.split(b"\n")
            if final and pending:
                lines, pending = [*lines, pending], b""
            for raw in lines:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if not line.strip():
                    continue
                if self.echo:
                    print(line, flush=True)
                last = line.strip()
                if step.key == "match_players" and (m := MATCH_PROGRESS.search(line)):
                    step.detail = f"{m.group(1)} / {m.group(2)}"

        timed_out = False
        try:
            # separate handles: the child appends, we read at our own position
            with open(log_path, "ab") as out, open(log_path, "rb") as reader:
                process = subprocess.Popen(
                    [sys.executable, *step.command], cwd=self.root, stdout=out, stderr=subprocess.STDOUT, env=env
                )
                self._process = process
                deadline = time.monotonic() + step.timeout
                while process.poll() is None:
                    consume(reader.read())
                    if time.monotonic() > deadline:
                        timed_out = True
                        process.kill()
                    time.sleep(0.25)
                consume(reader.read(), final=True)
                code = process.returncode
        finally:
            self._process = None
            try:
                log_path.unlink()
            except OSError:
                pass  # still held open by a leftover Chrome driver: the OS temp cleanup will get it
        if timed_out:
            return "failed", f"Arrêté après {step.timeout / 60:.0f} min sans finir."
        if self._cancelled:
            return "skipped", "Annulé."
        if code != 0:
            return "failed", last[:200]
        return "done", step.detail

    # -------------------------------------------------------------- publish
    def _git(self, *args: str, timeout: float = 60) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            # fail fast instead of waiting forever for a password prompt nobody sees
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )

    def _publish(self) -> tuple[str, str]:
        paths = [p for p in PUBLISHED_PATHS if (self.root / p).exists()]
        if not paths:
            return "skipped", "Aucune donnée à publier."
        ahead = self._git("rev-list", "--count", "@{u}..HEAD")
        if ahead.returncode != 0:
            return "failed", "Pas de branche GitHub associée à ce dépôt."
        if int(ahead.stdout.strip() or 0) > 0:
            # Pushing would also publish someone's unpushed work: leave it to them.
            return "skipped", "Des commits locaux attendent déjà d'être envoyés : données gardées en local."
        if self._git("add", "-A", "--", *paths).returncode != 0:
            return "failed", "git add a échoué."
        if self._git("diff", "--cached", "--quiet", "--", *paths).returncode == 0:
            return "skipped", "Aucune donnée nouvelle à publier."
        message = f"Data refresh ({season_label(self.season)}, {dt.date.today().isoformat()})"
        commit = self._git("commit", "-m", message, "--", *paths)
        if commit.returncode != 0:
            return "failed", (commit.stderr or commit.stdout).strip().splitlines()[-1][:200]
        push = self._git("push", timeout=180)
        if push.returncode != 0:
            return "failed", "Commit créé, mais l'envoi sur GitHub a échoué : " + push.stderr.strip()[-160:]
        return "done", ""

    # --------------------------------------------------------------- status
    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "started_at": _iso(self.started),
            "finished_at": _iso(self.finished),
            "publish": self.publish,
            "steps": [s.as_dict() for s in self.steps],
            "new_results": max(0, self.after.get("results", 0) - self.before.get("results", 0)) if self.after else None,
            "new_match_reports": (
                max(0, self.after.get("match_reports", 0) - self.before.get("match_reports", 0)) if self.after else None
            ),
        }


class RefreshManager:
    """At most one refresh at a time; keeps the last one for its status."""

    def __init__(self, reload: Callable[[], None] | None = None):
        self.reload = reload
        self.current: Refresh | None = None
        self._lock = threading.Lock()

    def start(self, publish: bool = True) -> Refresh:
        with self._lock:
            if self.current and self.current.state == "running":
                raise RuntimeError("a refresh is already running")
            self.current = Refresh(current_season_start_year(), reload=self.reload, publish=publish)
            threading.Thread(target=self.current.run, name="data-refresh", daemon=True).start()
            return self.current

    def status(self) -> dict:
        return self.current.as_dict() if self.current else {"state": "idle", "steps": []}

    def cancel(self) -> None:
        if self.current and self.current.state == "running":
            self.current.cancel()
