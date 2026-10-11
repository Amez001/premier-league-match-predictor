#!/usr/bin/env python
"""CLI: replay betting strategies on our past predictions, at real bookmaker odds.

Usage:
    python scripts/build_betting.py             # past seasons reused from the cache
    python scripts/build_betting.py --rebuild   # recompute every season (several minutes)

Writes reports/betting_predictions.csv (our predictions for every match
since 2013-14, each made before its round from earlier matches only) and
reports/betting.json, which the API serves on the "Paris" page. See
src/pl_predictor/betting.py.
"""
import argparse
import json
import sys
import time

from pl_predictor.betting import STRATEGIES, build_report, update_predictions
from pl_predictor.config import REPORTS_DIR, season_label
from pl_predictor.data.load import load_clean_matches
from pl_predictor.data.match_players import load_schedule
from pl_predictor.data.odds import load_odds

BETTING_PATH = REPORTS_DIR / "betting.json"


def _rounded(value, digits: int = 4):
    """Shorter JSON: 4 decimals is plenty for probabilities, odds and units."""
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {k: _rounded(v, digits) for k, v in value.items()}
    if isinstance(value, list):
        return [_rounded(v, digits) for v in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true", help="recompute the predictions of every season")
    args = parser.parse_args()

    matches = load_clean_matches()
    season = int(matches["season_start_year"].max())

    t0 = time.perf_counter()
    predictions = update_predictions(
        matches, rebuild=args.rebuild, on_season=lambda s: print(f"Predicting {season_label(s)}...", flush=True)
    )
    if predictions.empty:
        print("No played match to bet on yet.")
        return 0
    report = build_report(matches, predictions, load_odds(), load_schedule(season))
    BETTING_PATH.write_text(json.dumps(_rounded(report), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    names = {s["key"]: s["name"] for s in STRATEGIES}
    for key, title in (("history", "Since 2013-14"), ("season", season_label(season))):
        period = report["periods"][key]
        market = period["market"]
        print(f"\n{title}: {period['n_matches']} matches ({time.perf_counter() - t0:.0f}s)")
        if market["n_matches"]:
            print(f"Log loss: model {market['log_loss_model']:.4f}, market {market['log_loss_market']:.4f}"
                  f" - bookmaker margin {market['margin']:.1%}")
        print(f"{'Strategy':<34}{'Bets':>6}{'Won':>7}{'Odds':>7}{'Profit':>9}{'ROI':>8}{'Model said':>12}")
        for s in sorted(period["strategies"], key=lambda s: -s["profit"]):
            if not s["n_bets"]:
                print(f"{names[s['key']]:<34}{0:>6}")
                continue
            print(f"{names[s['key']]:<34}{s['n_bets']:>6}{s['hit_rate']:>7.0%}{s['avg_odds']:>7.2f}"
                  f"{s['profit']:>+9.1f}{s['roi']:>+8.1%}{s['expected_roi']:>+12.1%}")

    honesty = report["honesty"]
    if honesty:
        best = next(r for r in honesty["strategies"] if r["key"] == honesty["best_first"])
        print(f"\nBest strategy on {honesty['first'][0]}-{honesty['first'][1]}: {best['name']} "
              f"({best['roi_first']:+.1%}); on {honesty['second'][0]}-{honesty['second'][1]}: {best['roi_second']:+.1%}")
    print(f"\nSaved {BETTING_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
