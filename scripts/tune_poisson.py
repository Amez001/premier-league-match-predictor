#!/usr/bin/env python
"""CLI: pick the Poisson model's time-decay half-life, L2 strength and promoted effect.

Usage:
    python scripts/tune_poisson.py

Everything here is tuned on validation seasons 2008-09 -> 2012-13 only, all
of which come *before* the first season of the reported backtest (2013-14,
see scripts/run_backtest.py). Tuning on the backtest seasons themselves would
leak the test set into model selection and make the published numbers
optimistic.

Two evaluations, because they probe different regimes:

1. Pre-season walk-forward (train before the season, predict all of it).
   Picks the half-life: time decay matters most here.
2. In-season rolling (refit weekly, predict the next week) - the way the live
   predictor and the season simulator actually use the model. This is where
   regularization and the promoted-club effect matter: a promoted side has
   only a handful of recent matches, and weak shrinkage lets 5 results
   dominate its rating (an early version projected a promoted club to 21
   points after one bad month). Reported separately for early-season matches.
"""
import itertools

import numpy as np

from pl_predictor.data.load import load_clean_matches
from pl_predictor.evaluation.backtest import run_in_season_rolling, run_walk_forward, summarize
from pl_predictor.evaluation.metrics import multiclass_log_loss
from pl_predictor.models.poisson_model import PoissonGoalsModel

VALIDATION_SEASONS = list(range(2008, 2013))
EARLY_SEASON_GAMES = 8  # "early season" = either club has played fewer than this many games


def pre_season_half_life_search(matches):
    factories = {
        f"half_life={h}": (lambda h=h: PoissonGoalsModel(half_life_days=h)) for h in [None, 180, 365, 730]
    }
    results = run_walk_forward(matches, factories, first_test_season_start_year=min(VALIDATION_SEASONS))
    print("== Pre-season walk-forward (picks the half-life) ==")
    print(summarize(results)[["model", "log_loss", "accuracy"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))


def in_season_search(matches):
    factories = {}
    for alpha, promoted in itertools.product([0.001, 0.003, 0.01, 0.03], [False, True]):
        factories[f"alpha={alpha:<5} promoted={promoted!s:<5}"] = (
            lambda a=alpha, p=promoted: PoissonGoalsModel(alpha=a, use_promoted_effect=p)
        )
    preds = run_in_season_rolling(matches, factories, VALIDATION_SEASONS)

    print("\n== In-season rolling, weekly refits (picks alpha + promoted effect) ==")
    print(f"{'config':<30}{'all':>8}{'early':>8}   (log loss; early = a club has < {EARLY_SEASON_GAMES} games)")
    for name, g in preds.groupby("model", sort=False):
        early = g[g["matches_played_by_teams"] < EARLY_SEASON_GAMES]
        ll_all = multiclass_log_loss(g["result"], g[["p_home", "p_draw", "p_away"]].to_numpy())
        ll_early = multiclass_log_loss(early["result"], early[["p_home", "p_draw", "p_away"]].to_numpy())
        print(f"{name:<30}{ll_all:>8.4f}{ll_early:>8.4f}")
    print(f"\n({preds.groupby('model').size().iloc[0]} predicted matches per config, "
          f"{np.mean(preds.groupby('model').size())} avg)")


def main():
    matches = load_clean_matches()
    matches = matches[matches["season_start_year"] <= max(VALIDATION_SEASONS)]
    pre_season_half_life_search(matches)
    in_season_search(matches)


if __name__ == "__main__":
    main()
