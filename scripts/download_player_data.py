#!/usr/bin/env python
"""CLI: fetch current-season player stats (squad, minutes, goals) from FBref.

Usage:
    python scripts/download_player_data.py

Writes a dated snapshot to data/players/snapshots/<date>.csv and updates
data/players/latest.csv. Run this periodically (e.g. weekly) - comparing
successive snapshots is how the "recent form" signal in the goalscorer
model is computed (see src/pl_predictor/models/player_goals.py).
"""
import logging

from pl_predictor.config import DEFAULT_END_YEAR
from pl_predictor.data.player_stats import PLAYERS_DIR, fetch_current_squad_stats, save_snapshot


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(f"Fetching current-season ({DEFAULT_END_YEAR}-{(DEFAULT_END_YEAR + 1) % 100:02d}) player stats from FBref...")
    try:
        df = fetch_current_squad_stats(DEFAULT_END_YEAR)
    except ImportError:
        print("The `soccerdata` package is not installed. Run `pip install soccerdata` first.")
        return
    except Exception as exc:  # noqa: BLE001 - network/scraping failures should be visible, not crash the caller
        print(f"Failed to fetch player data: {exc}")
        return

    save_snapshot(df)
    n_teams = df["team"].nunique()
    print(f"Saved {len(df)} players across {n_teams} teams to {PLAYERS_DIR}")


if __name__ == "__main__":
    main()
