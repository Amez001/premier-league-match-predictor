import subprocess
import time

import pytest

from pl_predictor.refresh import Refresh, Step, data_counts


def _run(steps, **kwargs):
    refresh = Refresh(2026, steps=steps, **kwargs)
    refresh.run()
    return refresh


def test_steps_run_in_order_and_a_failure_does_not_stop_the_rest():
    reloaded = []
    refresh = _run(
        [
            Step("match_players", "Feuilles", ["-c", "print('[2/5] week 6: Arsenal vs Chelsea')"]),
            Step("players", "Joueurs", ["-c", "import sys; print('FBref unreachable'); sys.exit(3)"]),
            Step("betting", "Paris", ["-c", "print('ok')"]),
        ],
        reload=lambda: reloaded.append(True),
        publish=False,
    )
    status = {s["key"]: s for s in refresh.as_dict()["steps"]}
    assert status["match_players"]["status"] == "done"
    assert status["match_players"]["detail"] == "2 / 5"
    assert status["players"]["status"] == "failed"
    assert status["players"]["detail"] == "FBref unreachable"
    assert status["betting"]["status"] == "done"
    assert status["reload"]["status"] == "done" and reloaded
    assert "publish" not in status
    assert refresh.state == "error"


def test_a_leftover_child_process_does_not_hold_the_step():
    # The FBref scrapers leave a Chrome driver running, which inherits their
    # output: the step must end when the script ends, not when the driver does.
    script = (
        "import subprocess, sys; "
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        "print('[1/1] week 6: A vs B')"
    )
    start = time.monotonic()
    refresh = _run([Step("match_players", "Feuilles", ["-c", script])], publish=False)
    assert time.monotonic() - start < 10
    step = refresh.as_dict()["steps"][0]
    assert step["status"] == "done"
    assert step["detail"] == "1 / 1"


def test_a_stuck_step_is_stopped():
    refresh = _run([Step("players", "Joueurs", ["-c", "import time; time.sleep(30)"], timeout=0.5)], publish=False)
    step = refresh.as_dict()["steps"][0]
    assert step["status"] == "failed"
    assert "Arrêté" in step["detail"]


def test_data_counts(tmp_path):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "E0_2627.csv").write_text("Div,Date\nE0,1\nE0,2\nE0,3\n,,\n", encoding="utf-8")
    players = tmp_path / "data" / "players"
    players.mkdir(parents=True)
    (players / "match_stats_2026.csv").write_text("game_id,player\ng1,a\ng1,b\ng2,c\n", encoding="utf-8")
    assert data_counts(2026, tmp_path) == {"results": 3, "match_reports": 2}


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def clone(tmp_path):
    """A working copy with a remote, like the real repository and GitHub."""
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", str(remote))
    work = tmp_path / "work"
    _git(tmp_path, "clone", str(remote), str(work))
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "Test")
    (work / "README").write_text("x", encoding="utf-8")
    _git(work, "add", ".")
    _git(work, "commit", "-m", "init")
    _git(work, "push", "-u", "origin", "HEAD")
    (work / "data" / "players").mkdir(parents=True)
    return work


def test_publish_commits_only_the_data_and_pushes_it(clone):
    (clone / "data" / "players" / "latest.csv").write_text("a\n1\n", encoding="utf-8")
    (clone / "notes.txt").write_text("work in progress", encoding="utf-8")  # not data: must stay out
    refresh = Refresh(2026, root=clone, steps=[])

    assert refresh._publish() == ("done", "")
    committed = _git(clone, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert committed == ["data/players/latest.csv"]
    assert _git(clone, "rev-parse", "HEAD") == _git(clone, "rev-parse", "@{u}")  # pushed
    assert "notes.txt" in _git(clone, "status", "--porcelain")

    assert refresh._publish()[0] == "skipped"  # nothing new the second time


def test_publish_leaves_unpushed_work_alone(clone):
    (clone / "code.py").write_text("x = 1\n", encoding="utf-8")
    _git(clone, "add", "code.py")
    _git(clone, "commit", "-m", "local work")
    (clone / "data" / "players" / "latest.csv").write_text("a\n2\n", encoding="utf-8")

    status, detail = Refresh(2026, root=clone, steps=[])._publish()
    assert status == "skipped"
    assert "commits locaux" in detail
    assert _git(clone, "rev-list", "--count", "@{u}..HEAD") == "1"  # nothing pushed, no data commit
