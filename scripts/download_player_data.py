#!/usr/bin/env python
"""CLI: fetch current-season player stats (squad, minutes, goals, assists) from FBref.

Usage:
    python scripts/download_player_data.py

Writes a dated snapshot to data/players/snapshots/<date>.csv and updates
data/players/latest.csv. Run this periodically (e.g. weekly) - comparing
successive snapshots is how the "recent form" signal in the goalscorer
model is computed (see src/pl_predictor/models/player_goals.py).

Also keeps data/players/previous_season.csv (last season's per-player
totals, the prior for goal/assist shares); it's only fetched when missing or
when a new season has started, since last season doesn't change.
"""
import logging

from pl_predictor.config import DEFAULT_END_YEAR
from pl_predictor.data.player_stats import (
    PLAYERS_DIR,
    fetch_current_squad_stats,
    fetch_previous_season_totals,
    load_previous_season_totals,
    save_previous_season_totals,
    save_snapshot,
)


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
    print(f"Saved {len(df)} players across {df['team'].nunique()} teams to {PLAYERS_DIR}")

    if load_previous_season_totals(DEFAULT_END_YEAR) is None:
        print("Fetching last season's player totals (prior for goal/assist shares)...")
        try:
            prev = fetch_previous_season_totals(DEFAULT_END_YEAR)
        except Exception as exc:  # noqa: BLE001 - optional: shares fall back to position-based priors
            print(f"Failed to fetch last season's totals ({exc}); shares will use position-based priors only.")
            return
        save_previous_season_totals(prev)
        print(f"Saved last season's totals for {len(prev)} players.")


if __name__ == "__main__":
    main()
