#!/usr/bin/env python
"""CLI: score this season's predictions against the actual results so far.

Usage:
    python scripts/build_track_record.py

Rebuilds the predictor before each played matchweek from earlier data only
(see src/pl_predictor/track_record.py), then writes reports/track_record.json,
which the API serves on the "Bilan" page. Needs data/players/schedule_<season>.csv
(scripts/download_match_players.py); scorer checks also need the match-by-match
player rows it fetches.
"""
import json
import time

from pl_predictor.config import REPORTS_DIR, season_label
from pl_predictor.data.load import load_clean_matches
from pl_predictor.data.match_players import load_match_players, load_schedule, unknown_teams
from pl_predictor.data.player_stats import load_previous_season_totals
from pl_predictor.track_record import build_track_record

TRACK_RECORD_PATH = REPORTS_DIR / "track_record.json"


def main():
    matches = load_clean_matches()
    season = int(matches["season_start_year"].max())
    schedule = load_schedule(season)
    if schedule is None:
        print("No schedule yet - run `python scripts/download_match_players.py` first.")
        return

    match_players = load_match_players(season)
    if match_players is not None and (unknown := unknown_teams(match_players, schedule)):
        print(f"WARNING: club names missing from FBREF_TEAM_NAME_FIXES, their players are ignored: {sorted(unknown)}\n")

    t0 = time.perf_counter()
    record = build_track_record(matches, schedule, match_players, load_previous_season_totals(season))
    TRACK_RECORD_PATH.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")

    o = record["overall"]
    print(f"{season_label(season)}: {o['matches']} matches over {len(record['weeks'])} matchweeks ({time.perf_counter() - t0:.1f}s)\n")
    for key, label in (("outcome", "Result (H/D/A)"), ("exact", "Exact score"),
                       ("scorer_favourite", "Top scorer pick"), ("scorer_listed", "Listed scorers")):
        b = o[key]
        if b["n"]:
            print(f"{label:<16}{b['hits']:>3}/{b['n']:<4}= {b['hits'] / b['n']:>4.0%}   "
                  f"expected {b['expected']:.1f} (80% range {b['expected_low']:.0f}-{b['expected_high']:.0f})")
    print(f"Log loss        {o['log_loss']:.3f}   (reference, historical frequencies: {o['log_loss_reference']:.3f})")
    print(f"\nSaved {TRACK_RECORD_PATH}")


if __name__ == "__main__":
    main()
