import pandas as pd
import pytest

from pl_predictor.track_record import build_track_record, player_totals_before


@pytest.fixture
def two_seasons(toy_matches):
    """Last season (the toy fixtures a year earlier) + the current one, so
    even matchweek 1 has history to learn from - as with the real data."""
    last = toy_matches.assign(
        date=toy_matches["date"] - pd.DateOffset(years=1), season_start_year=2019, season_code="1920"
    )
    last["match_id"] = range(100, 100 + len(last))
    return pd.concat([last, toy_matches], ignore_index=True)


def _schedule(matches: pd.DataFrame) -> pd.DataFrame:
    # toy_matches: 3 dates, 2 matches each -> matchweeks 1, 2, 3
    dates = sorted(matches["date"].dt.date.astype(str).unique())
    return pd.DataFrame(
        {
            "week": [dates.index(d) + 1 for d in matches["date"].dt.date.astype(str)],
            "date": matches["date"].dt.date.astype(str),
            "home_team": matches["home_team"],
            "away_team": matches["away_team"],
            "home_goals": matches["home_goals"],
            "away_goals": matches["away_goals"],
            "game_id": [f"g{i}" for i in range(len(matches))],
        }
    )


def _match_players(schedule: pd.DataFrame) -> pd.DataFrame:
    """Each team's '9' scores all its goals; its '6' plays and never scores."""
    rows = []
    for g in schedule.itertuples(index=False):
        for team, goals in ((g.home_team, g.home_goals), (g.away_team, g.away_goals)):
            for name, pos, scored in ((f"{team} 9", "FW", goals), (f"{team} 6", "MF", 0)):
                rows.append({"game_id": g.game_id, "week": g.week, "date": g.date, "team": team, "player": name,
                             "nation": "ENG", "born": 1995.0, "position": pos, "minutes": 90,
                             "goals": int(scored), "assists": 0})
    return pd.DataFrame(rows)


def test_player_totals_only_count_earlier_matches(toy_matches):
    players = _match_players(_schedule(toy_matches))
    before_week_2 = player_totals_before(players, "2020-08-08", 2020).set_index("player")
    # Arsenal's 9 scored 2 in week 1 and 2 more in week 2: only week 1 counts
    assert before_week_2.loc["Arsenal 9", "season_goals"] == 2
    assert before_week_2.loc["Arsenal 9", "minutes_90s"] == 1.0
    assert player_totals_before(players, "2020-08-01", 2020).empty  # nothing before week 1


def test_track_record_scores_every_played_match(two_seasons, toy_matches):
    schedule = _schedule(toy_matches)
    record = build_track_record(two_seasons, schedule, _match_players(schedule), last_season=None)

    assert len(record["matches"]) == len(toy_matches)
    assert [w["week"] for w in record["weeks"]] == [1, 2, 3]
    o = record["overall"]
    assert o["outcome"]["hits"] == sum(m["outcome_hit"] for m in record["matches"])
    assert o["outcome"]["expected_low"] <= o["outcome"]["expected"] <= o["outcome"]["expected_high"]

    week1 = [m for m in record["matches"] if m["week"] == 1]
    later = [m for m in record["matches"] if m["week"] > 1]
    assert not any(m["scorers_known"] for m in week1)  # nobody had played yet: no basis for scorer picks
    assert all(m["scorers_known"] for m in later)
    for m in later:
        scorers = {s["player"] for s in m["actual_scorers"]}
        for pick in m["scorers_home"] + m["scorers_away"]:
            assert pick["scored"] == (pick["player"] in scorers)


def test_no_leakage_from_the_predicted_matchweek(two_seasons, toy_matches):
    """Changing week 3's results must not change any week-3 prediction."""
    schedule = _schedule(toy_matches)
    base = build_track_record(two_seasons, schedule, _match_players(schedule), last_season=None)

    altered = two_seasons.copy()
    week3 = altered["date"] == altered["date"].max()
    altered.loc[week3, ["home_goals", "away_goals"]] = [[5, 0], [0, 5]]
    altered.loc[week3, "result"] = ["H", "A"]
    altered_current = altered[altered["season_start_year"] == 2020]
    altered_schedule = _schedule(altered_current)
    changed = build_track_record(altered, altered_schedule, _match_players(altered_schedule), last_season=None)

    # sanity check that the test actually changed something observable
    assert [m["actual"] for m in base["matches"] if m["week"] == 3] != [m["actual"] for m in changed["matches"] if m["week"] == 3]

    def week3_predictions(record):
        return [(m["p_home"], m["p_draw"], m["p_away"], [s["player"] for s in m["scorers_home"]])
                for m in record["matches"] if m["week"] == 3]

    assert week3_predictions(base) == week3_predictions(changed)
