import pandas as pd

from pl_predictor.data.load import get_current_season_teams


def test_get_current_season_teams_only_returns_latest_season(toy_matches):
    # toy_matches is a single season (2020) with 4 teams: Arsenal, Chelsea, Liverpool, Everton.
    teams = get_current_season_teams(toy_matches)
    assert teams == ["Arsenal", "Chelsea", "Everton", "Liverpool"]


def test_get_current_season_teams_ignores_older_seasons(toy_matches):
    # Add an older-season match featuring a club that has since been relegated -
    # it must not show up in the "current season" team list.
    older = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2015-08-01"),
                "home_team": "Relegated FC",
                "away_team": "Arsenal",
                "home_goals": 0,
                "away_goals": 3,
                "result": "A",
                "season_start_year": 2015,
                "season_code": "1516",
                "match_id": -1,
            }
        ]
    )
    combined = pd.concat([older, toy_matches], ignore_index=True)
    teams = get_current_season_teams(combined)
    assert "Relegated FC" not in teams
    assert teams == ["Arsenal", "Chelsea", "Everton", "Liverpool"]
