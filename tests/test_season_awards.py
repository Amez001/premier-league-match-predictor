import numpy as np
import pandas as pd

from pl_predictor.models.player_goals import prepare_player_features
from pl_predictor.models.poisson_model import PoissonGoalsModel
from pl_predictor.season_awards import project_awards, remaining_expected_goals


def _players() -> pd.DataFrame:
    rows = []
    for team in ["Arsenal", "Chelsea", "Everton", "Liverpool"]:
        rows += [
            {"team": team, "player": f"{team} 9", "born": 1995, "nation": "ENG", "position": "FW",
             "minutes_90s": 3.0, "season_goals": 1.0, "season_assists": 0.0},
            {"team": team, "player": f"{team} 10", "born": 1996, "nation": "ENG", "position": "MF",
             "minutes_90s": 3.0, "season_goals": 0.0, "season_assists": 1.0},
        ]
    # Arsenal's striker has already scored 6 (moved from Chelsea after 2 of them).
    rows[0]["season_goals"] = 4.0
    rows.append({"team": "Chelsea", "player": "Arsenal 9", "born": 1995, "nation": "ENG", "position": "FW",
                 "minutes_90s": 1.0, "season_goals": 2.0, "season_assists": 0.0})
    df = pd.DataFrame(rows)
    df["season_goals_per90"] = df["season_goals"] / df["minutes_90s"]
    return df


def test_remaining_expected_goals_covers_every_club(toy_matches):
    model = PoissonGoalsModel().fit(toy_matches)
    totals = remaining_expected_goals(toy_matches, model)
    assert set(totals.index) == {"Arsenal", "Chelsea", "Everton", "Liverpool"}
    assert (totals > 0).all()  # 6 of 12 fixtures are still to play


def test_award_race_is_consistent(toy_matches):
    model = PoissonGoalsModel().fit(toy_matches)
    features = prepare_player_features(_players(), previous_df=None)
    awards = project_awards(toy_matches, features, model, n_sims=3000, seed=1)

    scorers = pd.DataFrame(awards["top_scorer"])
    # 9 players (one listed at two clubs) - all fit in the top 10, so the
    # award probabilities (shared on ties) must sum to exactly 1.
    assert np.isclose(scorers["p_top"].sum(), 1.0)
    assert (scorers["expected_final"] >= scorers["current"]).all()
    assert (scorers["p10"] <= scorers["p90"]).all()

    mover = scorers.set_index("player").loc["Arsenal 9"]
    assert mover["current"] == 6  # goals at both clubs count toward the award
    assert mover["team"] == "Arsenal"  # ...but he's projected at his current club only
    assert scorers.iloc[0]["player"] == "Arsenal 9"  # a 5-goal head start makes him the favourite

    assisters = pd.DataFrame(awards["top_assister"])
    assert np.isclose(assisters["p_top"].sum(), 1.0)
