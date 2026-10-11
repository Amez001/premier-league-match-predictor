#!/usr/bin/env python
"""CLI: the site's "Mettre à jour" button, from a terminal.

Usage:
    python scripts/refresh_data.py               # update everything, then commit and push the data
    python scripts/refresh_data.py --no-publish  # keep the new data local

Downloads the new results (football-data.co.uk) and player data (FBref),
rebuilds the season's track record and the betting analysis, then commits
data/players/ and reports/ and pushes them. See src/pl_predictor/refresh.py.
A running site picks the new data up on its next start; the button in the
site reloads it on the spot.
"""
import argparse
import sys

from pl_predictor.config import current_season_start_year
from pl_predictor.refresh import Refresh


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-publish", action="store_true", help="don't commit and push the new data")
    args = parser.parse_args()

    refresh = Refresh(current_season_start_year(), publish=not args.no_publish, echo=True)
    refresh.run()
    status = refresh.as_dict()
    print(f"\n{status['new_results']} new result(s), {status['new_match_reports']} new match report(s).")
    for step in status["steps"]:
        print(f"  {step['label']:<28}{step['status']:<9}{step['detail']}")
    return 0 if refresh.state == "done" else 1


if __name__ == "__main__":
    sys.exit(main())
