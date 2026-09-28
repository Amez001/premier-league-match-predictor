"""FastAPI backend for the React dashboard (Phase 2).

Thin HTTP layer only - all the actual modeling logic lives in `pl_predictor`
(predict.py, player_goals.py, poisson_model.py, ...) and is reused as-is, the
same way dashboard/app.py and scripts/predict_match.py already do. Nothing
here duplicates prediction logic.

Run with:
    uvicorn api.main:app --reload --port 8000        # dev (pairs with `npm run dev` in frontend/)
    uvicorn api.main:app --port 8000                 # "prod" locally, serves frontend/dist/ too
"""
from __future__ import annotations

import csv
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# allow running as `uvicorn api.main:app` without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pl_predictor.config import REPORTS_DIR, season_label  # noqa: E402
from pl_predictor.data.fixtures_api import get_upcoming_fixtures  # noqa: E402
from pl_predictor.data.load import load_clean_matches  # noqa: E402
from pl_predictor.data.match_players import load_match_players, load_schedule  # noqa: E402
from pl_predictor.data.player_stats import load_previous_season_totals  # noqa: E402
from pl_predictor.predict import MatchPredictor  # noqa: E402
from pl_predictor.season_awards import project_awards  # noqa: E402
from pl_predictor.simulation import simulate_season  # noqa: E402
from pl_predictor.stats import current_stats  # noqa: E402
from pl_predictor.track_record import build_track_record  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

_state: dict = {}

TRACK_RECORD_PATH = REPORTS_DIR / "track_record.json"


def _load_track_record(matches) -> dict:
    """reports/track_record.json (scripts/build_track_record.py, refreshed
    weekly); if it's missing but the schedule is there, compute it now."""
    if TRACK_RECORD_PATH.exists():
        return json.loads(TRACK_RECORD_PATH.read_text(encoding="utf-8"))
    season = int(matches["season_start_year"].max())
    schedule = load_schedule(season)
    if schedule is None:
        return {}
    return build_track_record(matches, schedule, load_match_players(season), load_previous_season_totals(season))


@asynccontextmanager
async def lifespan(app: FastAPI):
    matches = load_clean_matches()
    predictor = MatchPredictor(matches)
    _state["predictor"] = predictor
    # ~0.25s for 10k seasons, so compute once at startup and serve from memory.
    _state["season"] = simulate_season(matches, predictor.poisson_model).to_dict()
    _state["awards"] = (
        project_awards(matches, predictor.player_df, predictor.poisson_model, last_season=predictor.last_season)
        if predictor.player_df is not None
        else {"n_sims": 0, "top_scorer": [], "top_assister": []}
    )
    _state["stats"] = current_stats(matches, predictor.player_df)
    _state["track_record"] = _load_track_record(matches)
    _state["meta"] = {
        "season": season_label(int(matches["season_start_year"].max())),
        "last_match_date": matches["date"].max().date().isoformat(),
        "n_matches_history": len(matches),
        "first_season": season_label(int(matches["season_start_year"].min())),
        "players_snapshot_date": (
            str(predictor.player_df["snapshot_date"].iloc[0]) if predictor.player_df is not None else None
        ),
    }
    yield
    _state.clear()


app = FastAPI(title="Premier League Match Predictor API", lifespan=lifespan)

# Only needed when running the Vite dev server (a different origin) against
# this API directly instead of through its proxy; harmless in "prod" mode
# where the frontend is served from this same origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _predictor() -> MatchPredictor:
    return _state["predictor"]


@app.get("/api/teams")
def teams() -> list[str]:
    return _predictor().known_teams


@app.get("/api/predict")
def predict(home: str, away: str) -> dict:
    try:
        return _predictor().predict(home, away)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/season")
def season() -> dict:
    """Monte Carlo projection of the rest of the current season (see simulation.py)."""
    return _state["season"]


@app.get("/api/awards")
def awards() -> dict:
    """Top-scorer and top-assist races, projected to the end of the season (see season_awards.py)."""
    return _state["awards"]


@app.get("/api/stats")
def stats() -> dict:
    """Real current-season numbers: table, form, latest results, scoring and assist leaders."""
    return _state["stats"]


@app.get("/api/track-record")
def track_record() -> dict:
    """This season's predictions, rebuilt before each matchweek, against the actual results."""
    return _state["track_record"]


@app.get("/api/meta")
def meta() -> dict:
    return _state["meta"]


@app.get("/api/backtest-summary")
def backtest_summary() -> list[dict]:
    path = REPORTS_DIR / "backtest_summary.csv"
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@app.get("/api/fixtures")
def fixtures() -> list[dict]:
    df = get_upcoming_fixtures()
    return df.to_dict(orient="records")


# Serve the built React app (frontend/dist/, from `npm run build`) if present,
# so the whole thing runs as a single `uvicorn api.main:app` process locally.
# Mounted last so it never shadows the /api/* routes above.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
