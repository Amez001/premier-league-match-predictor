#!/usr/bin/env python
"""CLI: fetch match-by-match player data (who played, scored, assisted) from FBref.

Usage:
    python scripts/download_match_players.py
    python scripts/download_match_players.py --max-new 5   # at most 5 new matches this run

Only fetches matches not already in data/players/match_stats_<season>.csv.
FBref rate-limits match reports (~25s each), so the first run of a season
takes a while; weekly runs only fetch that week's matches. Safe to
interrupt: progress is saved after every match.
"""
import argparse
import logging

from pl_predictor.config import DEFAULT_END_YEAR
from pl_predictor.data.match_players import match_stats_path, update_match_players


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-new", type=int, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("soccerdata", "urllib3", "seleniumbase"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    try:
        schedule, stats = update_match_players(DEFAULT_END_YEAR, max_new=args.max_new)
    except ImportError:
        print("The `soccerdata` package is not installed. Run `pip install soccerdata` first.")
        return

    played = int(schedule["home_goals"].notna().sum())
    stored = stats["game_id"].nunique() if len(stats) else 0
    print(f"\n{stored}/{played} played matches stored in {match_stats_path(DEFAULT_END_YEAR)}")


if __name__ == "__main__":
    main()
