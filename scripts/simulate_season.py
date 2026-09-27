#!/usr/bin/env python
"""CLI: simulate the rest of the current season and print title/top-4/relegation odds.

Usage:
    python scripts/simulate_season.py
    python scripts/simulate_season.py --sims 50000
"""
import argparse
import time

from pl_predictor.config import season_label
from pl_predictor.data.load import load_clean_matches
from pl_predictor.models.poisson_model import PoissonGoalsModel
from pl_predictor.simulation import DEFAULT_N_SIMS, simulate_season


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sims", type=int, default=DEFAULT_N_SIMS)
    args = parser.parse_args()

    matches = load_clean_matches()
    model = PoissonGoalsModel().fit(matches)

    t0 = time.perf_counter()
    sim = simulate_season(matches, model, n_sims=args.sims)
    elapsed = time.perf_counter() - t0

    print(
        f"{season_label(sim.season_start_year)}: {sim.matches_played} matches played, "
        f"{sim.matches_remaining} remaining - {sim.n_sims:,} simulations in {elapsed:.2f}s\n"
    )
    p = sim.projections
    print(f"{'Team':<16}{'Pts':>5}{'xPts':>7}{'Title':>8}{'Top 4':>8}{'Releg.':>8}")
    for r in p.itertuples(index=False):
        print(
            f"{r.team:<16}{r.current_points:>5}{r.expected_points:>7.1f}"
            f"{r.p_title * 100:>7.1f}%{r.p_top4 * 100:>7.1f}%{r.p_relegation * 100:>7.1f}%"
        )


if __name__ == "__main__":
    main()
