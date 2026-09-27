"""Walk-forward (expanding window) backtest across seasons.

We deliberately never do a random train_test_split on historical matches:
shuffling would let a model trained partly on 2022 data "predict" a 2019
match, which is data leakage from the future and would make every model look
far better than it can actually perform in production. Instead, for each
test season S we train only on seasons strictly before S:

    train on seasons < 2019, test on 2019
    train on seasons < 2020, test on 2020
    train on seasons < 2021, test on 2021
    ...

and report metrics per season plus an aggregate across all test seasons.
"""
from __future__ import annotations

from typing import Callable

import pandas as pd

from pl_predictor.config import DEFAULT_FIRST_TEST_SEASON_START_YEAR
from pl_predictor.evaluation.metrics import evaluate
from pl_predictor.models.base import OutcomeModel

ModelFactory = Callable[[], OutcomeModel]


def run_walk_forward(
    feature_df: pd.DataFrame,
    model_factories: dict[str, ModelFactory],
    first_test_season_start_year: int = DEFAULT_FIRST_TEST_SEASON_START_YEAR,
) -> pd.DataFrame:
    """Returns one row per (season, model) with accuracy / log_loss / brier_score."""
    seasons = sorted(s for s in feature_df["season_start_year"].unique() if s >= first_test_season_start_year)

    records = []
    for season in seasons:
        train_df = feature_df[feature_df["season_start_year"] < season]
        test_df = feature_df[feature_df["season_start_year"] == season]
        if train_df.empty or test_df.empty:
            continue

        for model_name, factory in model_factories.items():
            model = factory()
            model.fit(train_df)
            proba = model.predict_proba(test_df)
            metrics = evaluate(test_df["result"], proba)
            records.append({"season": season, "model": model_name, **metrics})

    return pd.DataFrame(records)


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-season results into one row per model (matches-weighted average)."""
    def _weighted(group: pd.DataFrame, col: str) -> float:
        return (group[col] * group["n_matches"]).sum() / group["n_matches"].sum()

    rows = []
    for model_name, group in results.groupby("model"):
        rows.append(
            {
                "model": model_name,
                "accuracy": _weighted(group, "accuracy"),
                "log_loss": _weighted(group, "log_loss"),
                "brier_score": _weighted(group, "brier_score"),
                "n_matches": int(group["n_matches"].sum()),
                "n_seasons": group["season"].nunique(),
            }
        )
    return pd.DataFrame(rows).sort_values("log_loss").reset_index(drop=True)
