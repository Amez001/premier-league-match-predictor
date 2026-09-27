"""Current-season player stats (squad, minutes, goals) via FBref, for the
player-level goalscorer model in models/player_goals.py.

Uses the `soccerdata` library rather than a hand-rolled scraper: it already
handles FBref's tables (hidden inside HTML comments), rate limiting, and
local response caching.

Data is snapshotted with a date stamp every time it's fetched
(data/players/snapshots/<date>.csv) and the latest snapshot is also written
to data/players/latest.csv. Comparing the two most recent snapshots is how
models/player_goals.py estimates "recent form" without needing a separate,
much heavier per-match scrape for every player (see fetch_current_squad_stats
docstring and the README's "Effectifs & buteurs probables" section for the
reasoning and its honest limitations).
"""
from __future__ import annotations

import datetime as dt
import logging

import pandas as pd

from pl_predictor.config import ROOT_DIR

logger = logging.getLogger(__name__)

PLAYERS_DIR = ROOT_DIR / "data" / "players"
SNAPSHOTS_DIR = PLAYERS_DIR / "snapshots"
LATEST_PATH = PLAYERS_DIR / "latest.csv"

for _d in (PLAYERS_DIR, SNAPSHOTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

FBREF_LEAGUE = "ENG-Premier League"

# FBref/soccerdata spells some clubs differently than football-data.co.uk
# (our canonical naming, used everywhere else in this project - Elo table,
# feature engineering, the dashboard's team pickers, etc.). Normalize here so
# a player's `team` always matches the team names the rest of the app uses.
FBREF_TEAM_NAME_FIXES = {
    "Leeds United": "Leeds",
    "Manchester City": "Man City",
    "Manchester Utd": "Man United",
    "Nottingham": "Nottm Forest",
}


def _fbref_season_code(season_start_year: int) -> str:
    """2025 -> '2526' (the FBref/soccerdata season code for 2025-26)."""
    y1 = season_start_year % 100
    y2 = (season_start_year + 1) % 100
    return f"{y1:02d}{y2:02d}"


def fetch_current_squad_stats(season_start_year: int) -> pd.DataFrame:
    """Fetch every current-season Premier League player's standard season stats.

    Returns one row per player with: team, player, position, minutes_90s
    (matches worth of minutes played, FBref's "90s" column), season_goals,
    season_assists, season_goals_per90.

    Raises whatever `soccerdata` raises (network error, site structure
    change, etc.) - callers are expected to catch this and degrade
    gracefully (see predict.py / dashboard/app.py), the same pattern already
    used for the optional live-fixtures API in fixtures_api.py.
    """
    import soccerdata as sd  # imported lazily: soccerdata is a heavy optional dependency

    reader = sd.FBref(leagues=FBREF_LEAGUE, seasons=_fbref_season_code(season_start_year))
    raw = reader.read_player_season_stats(stat_type="standard")

    df = raw.reset_index()
    # Flatten the (group, stat) MultiIndex columns FBref/soccerdata returns,
    # e.g. ("Playing Time", "90s") -> "Playing Time_90s".
    df.columns = [
        "_".join(part for part in col if part) if isinstance(col, tuple) else col
        for col in df.columns
    ]

    out = pd.DataFrame(
        {
            "team": df["team"].replace(FBREF_TEAM_NAME_FIXES),
            "player": df["player"],
            "position": df["pos"],
            "minutes_90s": pd.to_numeric(df["Playing Time_90s"], errors="coerce").fillna(0.0),
            "season_goals": pd.to_numeric(df["Performance_Gls"], errors="coerce").fillna(0.0),
            "season_assists": pd.to_numeric(df["Performance_Ast"], errors="coerce").fillna(0.0),
        }
    )
    out["season_goals_per90"] = out["season_goals"] / out["minutes_90s"].replace(0, pd.NA)
    out["season_goals_per90"] = out["season_goals_per90"].fillna(0.0)
    out["snapshot_date"] = dt.date.today().isoformat()
    return out.reset_index(drop=True)


def save_snapshot(df: pd.DataFrame) -> None:
    """Persist a freshly fetched squad-stats dataframe as today's snapshot + latest.csv."""
    today = dt.date.today().isoformat()
    df.to_csv(SNAPSHOTS_DIR / f"{today}.csv", index=False)
    df.to_csv(LATEST_PATH, index=False)


def load_latest_snapshot() -> pd.DataFrame:
    if not LATEST_PATH.exists():
        raise FileNotFoundError(
            f"No player data found at {LATEST_PATH}. Run `python scripts/download_player_data.py` first."
        )
    return pd.read_csv(LATEST_PATH)


def load_previous_snapshot() -> pd.DataFrame | None:
    """The second-most-recent snapshot, used to compute a "recent form" delta.

    Returns None if fewer than two snapshots exist yet (e.g. first ever run) -
    callers should then fall back to season-long rates only.
    """
    snapshots = sorted(SNAPSHOTS_DIR.glob("*.csv"))
    if len(snapshots) < 2:
        return None
    return pd.read_csv(snapshots[-2])
