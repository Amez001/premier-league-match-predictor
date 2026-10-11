import pandas as pd

from pl_predictor.data.load import add_fbref_results, get_current_season_teams


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


def test_fbref_fills_in_results_football_data_has_not_published_yet(toy_matches):
    schedule = pd.DataFrame(
        {
            "week": [1, 4, 4],
            "date": ["2020-08-01", "2020-08-22", "2020-08-23"],
            "home_team": ["Arsenal", "Chelsea", "Everton"],
            "away_team": ["Chelsea", "Arsenal", "Liverpool"],
            # already in football-data, played but not published there yet, not played yet
            "home_goals": [2, 0, None],
            "away_goals": [0, 1, None],
        }
    )
    matches = add_fbref_results(toy_matches, schedule, 2020)
    assert len(matches) == len(toy_matches) + 1  # neither a duplicate nor an unplayed match
    new = matches[matches["date"] == pd.Timestamp("2020-08-22")].iloc[0]
    assert (new["home_team"], new["away_team"], new["result"], new["season_code"]) == ("Chelsea", "Arsenal", "A", "2021")
    assert matches["date"].is_monotonic_increasing
    assert matches["match_id"].tolist() == list(range(len(matches)))
    assert add_fbref_results(toy_matches, None, 2020) is toy_matches
