import pandas as pd

from pl_predictor.data.match_players import _birth_year, unknown_teams
from pl_predictor.data.player_stats import FBREF_TEAM_NAME_FIXES


def test_birth_year_from_fbref_age():
    # "24-350" on 2026-08-21: 24 years and 350 days old -> born 5 Sep 2001
    assert _birth_year("2026-08-21", "24-350") == 2001
    # birthday falls on the match day itself
    assert _birth_year("2026-08-21", "27-000") == 1999
    assert pd.isna(_birth_year("2026-08-21", ""))


def test_match_report_club_names_map_to_schedule_names():
    # Match reports spell clubs out in full; the schedule uses short forms.
    for full, short in [
        ("Manchester United", "Man United"),
        ("Newcastle United", "Newcastle"),
        ("Nottingham Forest", "Nottm Forest"),
        ("Manchester City", "Man City"),
    ]:
        assert FBREF_TEAM_NAME_FIXES[full] == short


def test_unknown_teams_flags_unmapped_spellings():
    schedule = pd.DataFrame({"home_team": ["Arsenal"], "away_team": ["Nottm Forest"]})
    players = pd.DataFrame({"team": ["Arsenal", "Nottm Forest", "Some New FC"]})
    assert unknown_teams(players, schedule) == {"Some New FC"}
