import pandas as pd

from pl_predictor.stats import current_stats, player_leaders, team_form

TEAMS = ["Arsenal", "Chelsea", "Everton", "Liverpool"]


def test_team_form_is_chronological_and_from_each_side(toy_matches):
    form = team_form(toy_matches, TEAMS)
    # Arsenal: W 2-0 v Chelsea, W 2-0 at Everton, D 1-1 v Liverpool (oldest first)
    assert form["Arsenal"] == ["W", "W", "D"]
    # Chelsea: L 0-2 at Arsenal, D 1-1 v Liverpool, D 2-2 v Everton
    assert form["Chelsea"] == ["L", "D", "D"]


def test_player_leaders_count_goals_at_both_clubs():
    players = pd.DataFrame(
        [
            {"team": "A", "player": "Mover", "born": 2000, "nation": "FRA", "position": "FW",
             "minutes_90s": 1.0, "season_goals": 2, "season_assists": 0, "is_current_club": False},
            {"team": "B", "player": "Mover", "born": 2000, "nation": "FRA", "position": "FW",
             "minutes_90s": 3.0, "season_goals": 2, "season_assists": 1, "is_current_club": True},
            {"team": "A", "player": "Solo", "born": 1998, "nation": "ENG", "position": "FW",
             "minutes_90s": 4.0, "season_goals": 3, "season_assists": 2, "is_current_club": True},
            {"team": "B", "player": "Blank", "born": 1999, "nation": "ENG", "position": "DF",
             "minutes_90s": 4.0, "season_goals": 0, "season_assists": 0, "is_current_club": True},
        ]
    )
    scorers, assisters = player_leaders(players)
    assert [(s["player"], s["team"], s["goals"]) for s in scorers["rows"]] == [("Mover", "B", 4), ("Solo", "A", 3)]
    assert [a["player"] for a in assisters["rows"]] == ["Solo", "Mover"]  # players with 0 are left out
    assert scorers["more_tied"] == 0


def test_player_leaders_report_ties_cut_off_by_the_list():
    players = pd.DataFrame(
        [
            {"team": "A", "player": f"P{i}", "born": 1990 + i, "nation": "ENG", "position": "FW",
             "minutes_90s": 5.0, "season_goals": 5 if i == 0 else 2, "season_assists": 0, "is_current_club": True}
            for i in range(14)
        ]
    )
    scorers, _ = player_leaders(players)
    # 1 player on 5 + 13 on 2: ten shown (1 + 9 on 2), four more on 2 left out
    assert len(scorers["rows"]) == 10 and scorers["more_tied"] == 4


def test_current_stats_without_player_data(toy_matches):
    stats = current_stats(toy_matches, player_df=None)
    assert stats["matches_played"] == len(toy_matches)
    assert stats["total_goals"] == int((toy_matches.home_goals + toy_matches.away_goals).sum())
    assert stats["top_scorers"]["rows"] == [] and stats["top_assisters"]["rows"] == []
    assert stats["table"][0]["team"] == "Arsenal" and len(stats["table"][0]["form"]) == 3
