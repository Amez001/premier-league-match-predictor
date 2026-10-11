import math

import numpy as np
import pandas as pd
import pytest

from pl_predictor.betting import (
    build_report,
    market_comparison,
    p_over_2_5,
    predict_season,
    round_starts,
    strategy_bets,
    summarize,
)


def test_round_starts_split_weekend_and_midweek():
    # 9-12 Oct 2026 is Friday to Monday, 13-15 Oct Tuesday to Thursday
    dates = pd.to_datetime(pd.Series(["2026-10-09", "2026-10-10", "2026-10-11", "2026-10-12", "2026-10-13", "2026-10-15"]))
    starts = round_starts(dates).dt.date.astype(str).tolist()
    assert starts == ["2026-10-09"] * 4 + ["2026-10-13"] * 2


def test_p_over_2_5_matches_the_poisson_sum():
    lam_h, lam_a = 1.6, 0.9
    total = lam_h + lam_a
    at_most_two = sum(math.exp(-total) * total**k / math.factorial(k) for k in range(3))
    assert p_over_2_5(lam_h, lam_a) == pytest.approx(1 - at_most_two)


def _book(rows):
    """Matches with our probabilities, odds and results, as build_report merges them."""
    df = pd.DataFrame(
        rows,
        columns=["round_start", "home_team", "away_team", "p_home", "p_draw", "p_away", "odds_home", "odds_draw",
                 "odds_away", "home_goals", "away_goals"],
    )
    df["season_start_year"] = 2020
    df["date"] = df["round_start"]
    df["result"] = np.select([df.home_goals > df.away_goals, df.home_goals < df.away_goals], ["H", "A"], "D")
    df["p_over"] = 0.55
    df["odds_over"], df["odds_under"] = 1.9, 1.9
    return df


BOOK = _book(
    [
        # round 1: A is a strong favourite and wins; C is favourite and loses
        ("2020-08-07", "A", "B", 0.70, 0.20, 0.10, 1.50, 4.00, 7.00, 2, 0),
        ("2020-08-07", "C", "D", 0.50, 0.25, 0.25, 2.20, 3.40, 3.40, 0, 1),
        # round 2: both favourites win
        ("2020-08-14", "B", "C", 0.20, 0.25, 0.55, 4.00, 3.50, 1.80, 0, 3),
        ("2020-08-14", "D", "A", 0.65, 0.20, 0.15, 1.70, 3.80, 5.50, 1, 0),
    ]
)


def test_favourite_bets_pay_the_odds_of_the_picked_result():
    bets = strategy_bets(BOOK, "fav_model")
    assert bets["pick"].tolist() == ["A", "C", "C", "D"]
    assert bets["won"].tolist() == [True, False, True, True]
    s = summarize(bets)
    # +0.5, -1, +0.8, +0.7
    assert s["profit"] == pytest.approx(1.0)
    assert s["roi"] == pytest.approx(0.25)
    assert s["max_drawdown"] == pytest.approx(1.0)
    assert s["longest_losing_streak"] == 1


def test_value_bets_need_our_probability_times_odds_above_1_05():
    bets = strategy_bets(BOOK, "value")
    # C-D: away 0.25 x 3.40 = 0.85 no; B at A-B: draw 0.20 x 4.00 = 0.80 no;
    # C vs D home 0.50 x 2.20 = 1.10 yes; D-A home 0.65 x 1.70 = 1.105 yes;
    # A-B home 0.70 x 1.50 = 1.05 yes (edge included); B-C away 0.55 x 1.80 = 0.99 no
    assert sorted(zip(bets["match"], bets["pick"])) == [("A - B", "A"), ("C - D", "C"), ("D - A", "D")]


def test_accumulator_wins_only_if_every_pick_wins():
    bets = strategy_bets(BOOK, "acca2")
    assert len(bets) == 2  # one per round
    first, second = bets.iloc[0], bets.iloc[1]
    assert not first["won"]  # C lost
    assert second["won"]
    assert second["odds"] == pytest.approx(1.80 * 1.70)
    assert second["p"] == pytest.approx(0.55 * 0.65)
    assert strategy_bets(BOOK, "acca3").empty  # never 3 matches in a round


def test_market_comparison_removes_the_margin():
    fair = BOOK.copy()
    implied = 1 / fair[["odds_home", "odds_draw", "odds_away"]].to_numpy()
    fair[["p_home", "p_draw", "p_away"]] = implied / implied.sum(axis=1, keepdims=True)
    comparison = market_comparison(fair)
    assert comparison["log_loss_model"] == pytest.approx(comparison["log_loss_market"])
    assert comparison["margin"] == pytest.approx(implied.sum(axis=1).mean() - 1)


@pytest.fixture
def two_seasons(toy_matches):
    last = toy_matches.assign(date=toy_matches["date"] - pd.DateOffset(years=1), season_start_year=2019,
                              season_code="1920")
    last["match_id"] = range(100, 100 + len(last))
    return pd.concat([last, toy_matches], ignore_index=True)


def test_no_leakage_from_the_predicted_round(two_seasons):
    """Changing the last round's results must not change its predictions."""
    base = predict_season(two_seasons, 2020)
    altered = two_seasons.copy()
    last_round = altered["date"] == altered["date"].max()
    altered.loc[last_round, ["home_goals", "away_goals"]] = [[5, 0], [0, 5]]
    altered.loc[last_round, "result"] = ["H", "A"]
    changed = predict_season(altered, 2020)

    cols = ["p_home", "p_draw", "p_away", "p_over"]
    last_date = two_seasons["date"].max().date().isoformat()
    assert len(base) == 6
    pd.testing.assert_frame_equal(base[base["date"] == last_date][cols], changed[changed["date"] == last_date][cols])


def test_report_counts_every_match_with_odds(two_seasons):
    predictions = predict_season(two_seasons, 2020)
    odds = two_seasons[["season_code", "home_team", "away_team"]].assign(
        odds_home=2.0, odds_draw=3.5, odds_away=3.8, odds_over=1.9, odds_under=1.9
    )
    report = build_report(two_seasons, predictions, odds)
    season = report["periods"]["season"]
    assert season["n_matches"] == 6
    by_key = {s["key"]: s for s in season["strategies"]}
    assert by_key["fav_model"]["n_bets"] == 6
    assert by_key["goals_model"]["n_bets"] == 6
    assert len(report["rounds"]) == 3
    assert all(len(r["picks"]) == 2 for r in report["rounds"])
