import numpy as np
import pandas as pd

from pl_predictor.models.player_goals import prepare_player_features
from pl_predictor.predict import MatchPredictor


def test_probable_scorers_share_only_the_goals_credited_to_players(toy_matches):
    # The toy league has 16 goals; its players are credited with 12 of them
    # (the rest are own goals), so only 75% of a team's expected goals can be
    # handed out to its squad.
    squad = pd.DataFrame(
        [
            {"team": team, "player": f"{team} {number}", "born": 1995, "nation": "ENG", "position": position,
             "minutes_90s": 3.0, "season_goals": goals, "season_assists": 0.0}
            for team in ["Arsenal", "Chelsea", "Everton", "Liverpool"]
            for number, position, goals in ((9, "FW", 3.0), (6, "MF", 0.0))
        ]
    )
    squad["season_goals_per90"] = squad["season_goals"] / squad["minutes_90s"]
    predictor = MatchPredictor(toy_matches, player_df=prepare_player_features(squad, previous_df=None))
    assert np.isclose(predictor.goal_credit_rate, 12 / 16)

    pred = predictor.predict("Arsenal", "Chelsea")
    for side in ("home", "away"):
        handed_out = sum(s["lambda_goals"] for s in pred[f"top_scorers_{side}"])  # whole 2-man squad listed
        assert np.isclose(handed_out, pred[f"expected_goals_{side}"] * 12 / 16)
