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
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# allow running as `uvicorn api.main:app` without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pl_predictor.config import REPORTS_DIR  # noqa: E402
from pl_predictor.data.fixtures_api import get_upcoming_fixtures  # noqa: E402
from pl_predictor.data.load import load_clean_matches  # noqa: E402
from pl_predictor.predict import MatchPredictor  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    matches = load_clean_matches()
    _state["predictor"] = MatchPredictor(matches)
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
