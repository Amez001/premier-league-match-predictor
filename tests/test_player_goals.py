import numpy as np
import pandas as pd

from pl_predictor.models.player_goals import (
    TYPICAL_ASSISTS_PER_GOAL,
    TYPICAL_GOAL_CREDIT_RATE,
    compute_assist_shares,
    compute_attack_shares,
    credit_rates,
    mark_current_club,
    predict_team_scorers,
    prepare_player_features,
)


def _toy_squad() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"team": "Arsenal", "player": "Striker", "position": "FW", "minutes_90s": 10.0,
             "season_goals": 8.0, "season_assists": 1.0, "season_goals_per90": 0.8},
            {"team": "Arsenal", "player": "Winger", "position": "FW", "minutes_90s": 9.0,
             "season_goals": 2.0, "season_assists": 4.0, "season_goals_per90": 2.0 / 9.0},
            {"team": "Arsenal", "player": "Defender", "position": "DF", "minutes_90s": 10.0,
             "season_goals": 0.0, "season_assists": 0.0, "season_goals_per90": 0.0},
        ]
    )


def test_attack_shares_sum_to_one_per_team():
    df = compute_attack_shares(_toy_squad())
    assert np.isclose(df["attack_share"].sum(), 1.0)
    shares = df.set_index("player")["attack_share"]
    assert shares["Striker"] > shares["Winger"] > shares["Defender"]


def test_attack_shares_are_shrunk_early_and_converge_late():
    # 8 of 10 goals is a small sample: the share is pulled below the raw 80%...
    early = compute_attack_shares(_toy_squad()).set_index("player")["attack_share"]
    assert 0.5 < early["Striker"] < 0.8

    # ...but with 20x the goals (same proportions) the data dominates the prior.
    late_squad = _toy_squad()
    late_squad["season_goals"] *= 20
    late = compute_attack_shares(late_squad).set_index("player")["attack_share"]
    assert abs(late["Striker"] - 0.8) < 0.02


def test_attack_shares_fall_back_to_minutes_when_team_has_no_goals():
    squad = _toy_squad()
    squad["season_goals"] = 0.0
    df = compute_attack_shares(squad)
    assert np.isclose(df["attack_share"].sum(), 1.0)
    # equal minutes for Striker/Defender (10 each) -> equal share, higher than Winger (9)
    assert df.loc[df.player == "Striker", "attack_share"].iloc[0] == df.loc[df.player == "Defender", "attack_share"].iloc[0]


def test_predict_team_scorers_lambdas_sum_to_team_expected_goals():
    features = prepare_player_features(_toy_squad(), previous_df=None)
    team_goals = 1.7
    scorers = predict_team_scorers(features, "Arsenal", team_goals, top_n=10)
    assert np.isclose(scorers["lambda_goals"].sum(), team_goals)
    # top scorer should be the one with by far the biggest historical share
    assert scorers.iloc[0]["player"] == "Striker"
    assert (scorers["scorer_probability"] <= 1.0).all()


def test_assist_shares_sum_to_one_and_follow_assists():
    df = compute_assist_shares(_toy_squad())
    assert np.isclose(df["assist_share"].sum(), 1.0)
    shares = df.set_index("player")["assist_share"]
    assert shares["Winger"] > shares["Striker"] > shares["Defender"]


def test_last_season_record_shapes_the_prior():
    # Two forwards with identical current seasons: the one who scored 25 last
    # season must get the bigger share than the one who scored 2.
    squad = pd.DataFrame(
        [
            {"team": "A", "player": "Proven", "born": 1995, "nation": "ENG", "position": "FW",
             "minutes_90s": 3.0, "season_goals": 1.0, "season_assists": 0.0, "season_goals_per90": 1 / 3},
            {"team": "A", "player": "Unproven", "born": 1998, "nation": "ENG", "position": "FW",
             "minutes_90s": 3.0, "season_goals": 1.0, "season_assists": 0.0, "season_goals_per90": 1 / 3},
        ]
    )
    last_season = pd.DataFrame(
        [
            {"player": "Proven", "born": 1995.0, "nation": "ENG", "minutes_90s": 30.0, "season_goals": 25.0, "season_assists": 3.0},
            {"player": "Unproven", "born": 1998.0, "nation": "ENG", "minutes_90s": 30.0, "season_goals": 2.0, "season_assists": 3.0},
        ]
    )
    without = compute_attack_shares(squad).set_index("player")["attack_share"]
    with_prior = compute_attack_shares(squad, last_season).set_index("player")["attack_share"]
    assert np.isclose(without["Proven"], without["Unproven"])  # nothing tells them apart this season
    assert with_prior["Proven"] > 0.6  # born 1995 vs 1995.0 must still match across files


def test_mark_current_club_after_a_transfer():
    squad = pd.DataFrame(
        [
            {"team": "Old", "player": "Mover", "born": 2000, "nation": "FRA", "minutes_90s": 3.0},
            {"team": "New", "player": "Mover", "born": 2000, "nation": "FRA", "minutes_90s": 1.0},
            {"team": "Old", "player": "Stayer", "born": 1999, "nation": "FRA", "minutes_90s": 4.0},
            # same name, different player: must not be treated as a transfer
            {"team": "New", "player": "Stayer", "born": 2004, "nation": "BRA", "minutes_90s": 2.0},
        ]
    )
    # No previous snapshot: the club with more minutes wins.
    marked = mark_current_club(squad)
    assert marked["is_current_club"].tolist() == [True, False, True, True]

    # With a previous snapshot where only his "New" minutes grew, New is current.
    previous = squad.assign(minutes_90s=[3.0, 0.0, 3.0, 1.0])
    marked = mark_current_club(squad, previous)
    assert marked["is_current_club"].tolist() == [False, True, True, True]


def test_departed_player_never_listed_as_a_scorer_for_his_old_club():
    squad = pd.concat(
        [_toy_squad().assign(born=1990, nation="ENG"),
         pd.DataFrame([{"team": "Chelsea", "player": "Striker", "born": 1990, "nation": "ENG", "position": "FW",
                        "minutes_90s": 1.0, "season_goals": 0.0, "season_assists": 0.0, "season_goals_per90": 0.0}])],
        ignore_index=True,
    )
    # Striker has 10 90s at Arsenal vs 1 at Chelsea -> Arsenal is current.
    features = prepare_player_features(squad, previous_df=None)
    assert "Striker" not in predict_team_scorers(features, "Chelsea", 1.5, top_n=10)["player"].tolist()
    assert "Striker" in predict_team_scorers(features, "Arsenal", 1.5, top_n=10)["player"].tolist()


def test_credit_rates_prefer_last_season_then_this_season_then_typical():
    # 100 team goals last season, 10 so far this season
    matches = pd.DataFrame(
        {"season_start_year": [2025, 2025, 2026], "home_goals": [30, 20, 6], "away_goals": [25, 25, 4]}
    )
    # 96 of last season's 100 goals credited to players (4 own goals), 66 assists
    last_season = pd.DataFrame(
        {"season_start_year": [2025, 2025], "season_goals": [60, 36], "season_assists": [40, 26]}
    )
    this_season = pd.DataFrame({"season_goals": [9], "season_assists": [7]})
    assert np.allclose(credit_rates(matches, last_season, this_season), (0.96, 0.66))
    assert np.allclose(credit_rates(matches, None, this_season), (0.9, 0.7))
    assert credit_rates(matches) == (TYPICAL_GOAL_CREDIT_RATE, TYPICAL_ASSISTS_PER_GOAL)
