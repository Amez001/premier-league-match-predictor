#!/usr/bin/env python
"""CLI: run the full walk-forward backtest across every model and print/save results.

Usage:
    python scripts/run_backtest.py
    python scripts/run_backtest.py --first-test-season 2015
"""
import argparse

from pl_predictor.config import DEFAULT_FIRST_TEST_SEASON_START_YEAR, REPORTS_DIR, season_label
from pl_predictor.data.load import load_clean_matches
from pl_predictor.evaluation.backtest import run_walk_forward, summarize
from pl_predictor.features.engineering import BASELINE_FEATURE_COLUMNS, build_feature_table
from pl_predictor.models.baseline_logreg import LogisticOutcomeModel
from pl_predictor.models.ml_models import RandomForestOutcomeModel, XGBoostOutcomeModel, xgboost_available
from pl_predictor.models.naive import ConstantFrequencyModel
from pl_predictor.models.poisson_model import PoissonGoalsModel


def build_model_factories() -> dict:
    factories = {
        "naive_base_rate": ConstantFrequencyModel,
        "elo_logistic": lambda: LogisticOutcomeModel(feature_columns=["elo_diff"], name="elo_logistic"),
        "baseline_logistic": lambda: LogisticOutcomeModel(
            feature_columns=BASELINE_FEATURE_COLUMNS, name="baseline_logistic"
        ),
        "poisson": PoissonGoalsModel,
        "random_forest": lambda: RandomForestOutcomeModel(feature_columns=BASELINE_FEATURE_COLUMNS),
    }
    if xgboost_available():
        factories["xgboost"] = lambda: XGBoostOutcomeModel(feature_columns=BASELINE_FEATURE_COLUMNS)
    return factories


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-test-season", type=int, default=DEFAULT_FIRST_TEST_SEASON_START_YEAR)
    args = parser.parse_args()

    print("Loading and cleaning historical matches...")
    matches = load_clean_matches()
    print(f"  {len(matches)} matches, seasons {matches['season_start_year'].min()}-{matches['season_start_year'].max()}")

    print("Building Elo + form features (single leakage-safe chronological pass)...")
    feature_df = build_feature_table(matches)

    print(f"Running walk-forward backtest from season {season_label(args.first_test_season)} onward...\n")
    results = run_walk_forward(feature_df, build_model_factories(), first_test_season_start_year=args.first_test_season)

    per_season_path = REPORTS_DIR / "backtest_per_season.csv"
    summary_path = REPORTS_DIR / "backtest_summary.csv"
    results.to_csv(per_season_path, index=False)

    summary = summarize(results)
    summary.to_csv(summary_path, index=False)

    print("=== Summary (matches-weighted average across all test seasons) ===")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"\nSaved: {per_season_path}")
    print(f"Saved: {summary_path}")


if __name__ == "__main__":
    main()
