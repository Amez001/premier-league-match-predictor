import numpy as np
import pandas as pd

from pl_predictor.models.poisson_model import PoissonGoalsModel
from pl_predictor.simulation import league_table, remaining_fixtures, simulate_season

TEAMS = ["Arsenal", "Chelsea", "Everton", "Liverpool"]


def test_league_table_points_and_goal_difference(toy_matches):
    table = league_table(toy_matches, TEAMS).set_index("team")
    # Arsenal: W 2-0, W 2-0 (away), D 1-1 -> 7 pts, GD +4
    assert table.loc["Arsenal", "points"] == 7
    assert table.loc["Arsenal", "goal_diff"] == 4
    assert table["played"].sum() == 2 * len(toy_matches)


def test_remaining_fixtures_complete_the_double_round_robin(toy_matches):
    fixtures = remaining_fixtures(toy_matches, TEAMS)
    assert len(fixtures) == len(TEAMS) * (len(TEAMS) - 1) - len(toy_matches)
    played = set(zip(toy_matches.home_team, toy_matches.away_team))
    assert not played & set(zip(fixtures.home_team, fixtures.away_team))


def test_simulation_probabilities_are_consistent(toy_matches):
    model = PoissonGoalsModel().fit(toy_matches)
    sim = simulate_season(toy_matches, model, n_sims=2000, seed=0)
    p = sim.projections

    assert np.isclose(p["p_title"].sum(), 1.0)
    positions = np.array(p["position_probs"].tolist())
    # every team finishes somewhere, and every position is filled by someone
    assert np.allclose(positions.sum(axis=1), 1.0)
    assert np.allclose(positions.sum(axis=0), 1.0)
    assert sim.matches_remaining == len(TEAMS) * (len(TEAMS) - 1) - len(toy_matches)
    # expected points can never be below points already banked
    assert (p["expected_points"] >= p["current_points"]).all()


def test_completed_season_is_deterministic(toy_matches):
    # Play out every remaining fixture so nothing is left to simulate:
    # the leader must then win the title in 100% of simulations.
    fixtures = remaining_fixtures(toy_matches, TEAMS)
    extra = fixtures.assign(
        home_goals=1,
        away_goals=0,
        result="H",
        date=toy_matches["date"].max(),
        season_start_year=2020,
        season_code="2021",
    )
    extra["match_id"] = range(100, 100 + len(extra))
    full = pd.concat([toy_matches, extra], ignore_index=True)

    sim = simulate_season(full, PoissonGoalsModel().fit(full), n_sims=500, seed=0)
    assert sim.matches_remaining == 0
    leader = league_table(full, TEAMS).iloc[0]["team"]
    assert sim.projections.set_index("team").loc[leader, "p_title"] == 1.0
