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


def run_in_season_rolling(
    matches: pd.DataFrame,
    model_factories: dict[str, ModelFactory],
    seasons: list[int],
    step_days: int = 7,
) -> pd.DataFrame:
    """Refit every `step_days` during each season, predict only the next window.

    run_walk_forward trains once, before a season starts - so it never
    evaluates a model refit mid-season on a handful of current-season matches,
    which is exactly how the live predictor and the season simulator use it.
    This mirrors that usage. Returns one row per predicted match with the
    model's probabilities, plus `matches_played_by_teams` (min of the two
    clubs' current-season games so far) to slice early-season performance.
    """
    records = []
    for season in seasons:
        season_df = matches[matches["season_start_year"] == season]
        start, end = season_df["date"].min(), season_df["date"].max()
        cutoff = start
        while cutoff <= end:
            window_end = cutoff + pd.Timedelta(days=step_days)
            train_df = matches[matches["date"] < cutoff]
            test_df = season_df[(season_df["date"] >= cutoff) & (season_df["date"] < window_end)]
            cutoff = window_end
            if test_df.empty:
                continue

            played_so_far = season_df[season_df["date"] < test_df["date"].min()]
            games = pd.concat([played_so_far["home_team"], played_so_far["away_team"]]).value_counts()
            n_played = [
                min(games.get(h, 0), games.get(a, 0)) for h, a in zip(test_df["home_team"], test_df["away_team"])
            ]

            for model_name, factory in model_factories.items():
                proba = factory().fit(train_df).predict_proba(test_df)
                for i, r in enumerate(test_df.itertuples(index=False)):
                    records.append(
                        {
                            "model": model_name,
                            "season": season,
                            "result": r.result,
                            "matches_played_by_teams": n_played[i],
                            "p_home": proba[i, 0],
                            "p_draw": proba[i, 1],
                            "p_away": proba[i, 2],
                        }
                    )
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
