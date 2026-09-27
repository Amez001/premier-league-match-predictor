import pandas as pd
import pytest


@pytest.fixture
def toy_matches() -> pd.DataFrame:
    """A tiny synthetic league (4 teams, 2 rounds) for fast, deterministic unit tests."""
    rows = [
        # round 1
        ("2020-08-01", "Arsenal", "Chelsea", 2, 0),
        ("2020-08-01", "Liverpool", "Everton", 3, 1),
        # round 2
        ("2020-08-08", "Chelsea", "Liverpool", 1, 1),
        ("2020-08-08", "Everton", "Arsenal", 0, 2),
        # round 3
        ("2020-08-15", "Arsenal", "Liverpool", 1, 1),
        ("2020-08-15", "Chelsea", "Everton", 2, 2),
    ]
    df = pd.DataFrame(rows, columns=["date", "home_team", "away_team", "home_goals", "away_goals"])
    df["date"] = pd.to_datetime(df["date"])
    df["result"] = df.apply(
        lambda r: "H" if r.home_goals > r.away_goals else ("A" if r.home_goals < r.away_goals else "D"), axis=1
    )
    df["season_start_year"] = 2020
    df["season_code"] = "2021"
    df["match_id"] = df.index
    return df
