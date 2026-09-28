"""Match-level data from FBref: the fixture list with official matchweeks, and
who played, scored and assisted in each match.

This is what makes an honest track record possible (see track_record.py).
The season-total snapshots in player_stats.py include every goal scored so
far, so using them to "predict" an earlier matchweek would leak the answer.
Per-match rows let us rebuild each player's totals *as they stood before*
any given matchweek, and tell us who actually scored.

FBref serves one match report per request and rate-limits heavily (~25s per
match here), so rows are stored in the repo (data/players/match_stats_*.csv)
and only matches not already there are fetched: the first run takes a while,
each weekly refresh only fetches that week's ~10 matches.
"""
from __future__ import annotations

import datetime as dt
import logging
import re

import pandas as pd

from pl_predictor.data.player_stats import FBREF_LEAGUE, FBREF_TEAM_NAME_FIXES, PLAYERS_DIR, _fbref_season_code

logger = logging.getLogger(__name__)

# FBref's per-match position codes -> the FW / MF / DF / GK buckets used by
# the season stats (and by the position priors in player_goals.py).
_POSITION_BUCKET = {
    "FW": "FW", "LW": "FW", "RW": "FW", "CF": "FW",
    "AM": "MF", "CM": "MF", "DM": "MF", "LM": "MF", "RM": "MF", "MF": "MF",
    "CB": "DF", "LB": "DF", "RB": "DF", "WB": "DF", "DF": "DF",
    "GK": "GK",
}


def schedule_path(season_start_year: int):
    return PLAYERS_DIR / f"schedule_{season_start_year}.csv"


def match_stats_path(season_start_year: int):
    return PLAYERS_DIR / f"match_stats_{season_start_year}.csv"


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reset_index()
    df.columns = ["_".join(part for part in col if part) if isinstance(col, tuple) else col for col in df.columns]
    return df


def _reader(season_start_year: int):
    import soccerdata as sd  # heavy optional dependency, imported lazily

    return sd.FBref(leagues=FBREF_LEAGUE, seasons=_fbref_season_code(season_start_year))


def fetch_schedule(season_start_year: int, reader=None) -> pd.DataFrame:
    """All 380 fixtures with official matchweek, date, teams, score (NaN if unplayed) and FBref game id."""
    reader = reader or _reader(season_start_year)
    raw = _flatten(reader.read_schedule())
    goals = raw["score"].astype(str).str.extract(r"(\d+)\D+(\d+)")
    out = pd.DataFrame(
        {
            "week": pd.to_numeric(raw["week"], errors="coerce").astype("Int64"),
            "date": pd.to_datetime(raw["date"]).dt.date.astype(str),
            "home_team": raw["home_team"].replace(FBREF_TEAM_NAME_FIXES),
            "away_team": raw["away_team"].replace(FBREF_TEAM_NAME_FIXES),
            "home_goals": pd.to_numeric(goals[0], errors="coerce").astype("Int64"),
            "away_goals": pd.to_numeric(goals[1], errors="coerce").astype("Int64"),
            "game_id": raw["game_id"],
        }
    )
    return out.sort_values(["week", "date", "home_team"]).reset_index(drop=True)


def _birth_year(match_date: str, age: str) -> float:
    """FBref gives age at the match as "24-350" (years-days); recover the birth year."""
    m = re.match(r"(\d+)-(\d+)", str(age))
    if not m:
        return float("nan")
    d = dt.date.fromisoformat(match_date)
    years, days = int(m.group(1)), int(m.group(2))
    try:
        anniversary = d.replace(year=d.year - years)
    except ValueError:  # Feb 29
        anniversary = d.replace(year=d.year - years, day=28)
    return float((anniversary - dt.timedelta(days=days)).year)


def fetch_match_players(game: pd.Series, reader) -> pd.DataFrame:
    """One row per player who appeared in `game` (a schedule row)."""
    raw = _flatten(reader.read_player_match_stats(stat_type="summary", match_id=game["game_id"]))
    positions = raw["pos"].fillna("MF").astype(str).str.split(",").str[0].str.strip()
    return pd.DataFrame(
        {
            "game_id": game["game_id"],
            "week": game["week"],
            "date": game["date"],
            "team": raw["team"].replace(FBREF_TEAM_NAME_FIXES),
            "player": raw["player"],
            "nation": raw["nation"],
            "born": [_birth_year(game["date"], a) for a in raw["age"]],
            "position": positions.map(_POSITION_BUCKET).fillna("MF"),
            "minutes": pd.to_numeric(raw["min"], errors="coerce").fillna(0).astype(int),
            "goals": pd.to_numeric(raw["Performance_Gls"], errors="coerce").fillna(0).astype(int),
            "assists": pd.to_numeric(raw["Performance_Ast"], errors="coerce").fillna(0).astype(int),
        }
    )


def load_schedule(season_start_year: int) -> pd.DataFrame | None:
    path = schedule_path(season_start_year)
    return pd.read_csv(path, encoding="utf-8") if path.exists() else None


def load_match_players(season_start_year: int) -> pd.DataFrame | None:
    path = match_stats_path(season_start_year)
    if not path.exists():
        return None
    df = pd.read_csv(path, encoding="utf-8")
    # Normalize on read too: rows stored before a spelling was added to
    # FBREF_TEAM_NAME_FIXES must still match the rest of the data.
    df["team"] = df["team"].replace(FBREF_TEAM_NAME_FIXES)
    return df


def unknown_teams(match_players: pd.DataFrame, schedule: pd.DataFrame) -> set[str]:
    """Club names in the player rows that the schedule doesn't know - a
    spelling missing from FBREF_TEAM_NAME_FIXES, which would silently drop
    that club's players from the scorer predictions."""
    known = set(schedule["home_team"]) | set(schedule["away_team"])
    return set(match_players["team"]) - known


def update_match_players(season_start_year: int, max_new: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Refresh the schedule, then fetch player rows for played matches not stored yet.

    Saves after every match, so an interrupted run (or FBref hiccup) keeps
    what it already has and the next run resumes from there.
    """
    reader = _reader(season_start_year)
    schedule = fetch_schedule(season_start_year, reader)
    schedule.to_csv(schedule_path(season_start_year), index=False, encoding="utf-8")

    stored = load_match_players(season_start_year)
    have = set(stored["game_id"]) if stored is not None else set()
    todo = schedule[schedule["home_goals"].notna() & ~schedule["game_id"].isin(have)]
    if max_new is not None:
        todo = todo.head(max_new)

    frames = [stored] if stored is not None else []
    for i, (_, game) in enumerate(todo.iterrows(), start=1):
        try:
            frames.append(fetch_match_players(game, reader))
        except Exception as exc:  # noqa: BLE001 - one bad match report shouldn't lose the others
            logger.warning("could not fetch %s vs %s (%s): %s", game["home_team"], game["away_team"], game["game_id"], exc)
            continue
        pd.concat(frames, ignore_index=True).to_csv(match_stats_path(season_start_year), index=False, encoding="utf-8")
        logger.info("[%d/%d] week %s: %s vs %s", i, len(todo), game["week"], game["home_team"], game["away_team"])

    stats = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if len(stats):
        stats["team"] = stats["team"].replace(FBREF_TEAM_NAME_FIXES)
        unknown = unknown_teams(stats, schedule)
        if unknown:
            logger.warning("club names not in the schedule (add them to FBREF_TEAM_NAME_FIXES): %s", sorted(unknown))
    return schedule, stats
