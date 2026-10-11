from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from pl_predictor.betting_search import (
    MIN_BETS,
    Search,
    luck_benchmark,
    search_report,
    simulate_outcomes,
    walk_forward,
)


@pytest.fixture(scope="module")
def book() -> pd.DataFrame:
    """Five synthetic seasons of 10 rounds x 6 matches, with our probabilities,
    bookmaker odds (5% margin) and results."""
    rng = np.random.default_rng(0)
    rows = []
    for season in range(2013, 2018):
        for r in range(10):
            start = (pd.Timestamp(f"{season}-08-02") + pd.Timedelta(days=7 * r)).date().isoformat()
            for m in range(6):
                market = rng.dirichlet([5, 3, 3.5])
                ours = rng.dirichlet(market * 40)
                home_goals, away_goals = int(rng.poisson(1.5)), int(rng.poisson(1.1))
                over = rng.uniform(0.35, 0.65)
                rows.append(
                    {
                        "season_start_year": season,
                        "round_start": start,
                        "date": start,
                        "home_team": f"H{m}",
                        "away_team": f"A{m}",
                        "p_home": ours[0],
                        "p_draw": ours[1],
                        "p_away": ours[2],
                        "p_over": float(np.clip(over + rng.normal(0, 0.05), 0.05, 0.95)),
                        "odds_home": 1 / (market[0] * 1.05),
                        "odds_draw": 1 / (market[1] * 1.05),
                        "odds_away": 1 / (market[2] * 1.05),
                        "odds_over": 1 / (over * 1.05),
                        "odds_under": 1 / ((1 - over) * 1.05),
                        "home_goals": home_goals,
                        "away_goals": away_goals,
                        "result": "H" if home_goals > away_goals else "A" if home_goals < away_goals else "D",
                    }
                )
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def search(book) -> Search:
    return Search(book)


def _total(search: Search, name: str) -> float:
    actual = search.cand["won"].to_numpy()
    return float(search.profit_by_season(actual).sum(axis=1)[search.names.index(name)])


def test_every_match_offers_five_bets_and_exactly_two_win(search, book):
    assert len(search.cand) == 5 * len(book)
    won_per_match = search.cand.groupby(["match", "market"])["won"].sum()
    assert (won_per_match == 1).all()  # one result and one goal line per match


def test_a_single_bet_combination_is_settled_at_its_odds(search, book):
    home = book["result"] == "H"
    expected = np.where(home, book["odds_home"] - 1, -1.0).sum()
    assert _total(search, "Victoire à domicile") == pytest.approx(expected)
    under = (book["home_goals"] + book["away_goals"]) < 2.5
    short = book["odds_under"] < 1.8
    expected = np.where(under, book["odds_under"] - 1, -1.0)[short].sum()
    assert _total(search, "Moins de 2,5 buts · cote < 1,8") == pytest.approx(expected)


def test_an_accumulator_pays_only_when_all_its_picks_win(search, book):
    expected = 0.0
    for _, rnd in book.groupby("round_start"):
        probs = rnd[["p_home", "p_draw", "p_away"]].to_numpy()
        fav = probs.argmax(axis=1)
        top = np.argsort(-probs.max(axis=1), kind="stable")[:2]
        odds = rnd[["odds_home", "odds_draw", "odds_away"]].to_numpy()[top, fav[top]]
        won = (rnd["result"].to_numpy()[top] == np.array(["H", "D", "A"])[fav[top]]).all()
        expected += odds.prod() - 1 if won else -1
    assert _total(search, "Combiné de 2 · favoris de notre modèle") == pytest.approx(expected)


def test_walk_forward_only_looks_at_earlier_seasons():
    # strategy 0 wins the first three seasons then loses, strategy 1 the opposite
    by_season = np.array([[5.0, 5.0, 5.0, -4.0, -4.0], [-1.0, -1.0, -1.0, 9.0, 9.0]])
    fake = SimpleNamespace(seasons=[2013, 2014, 2015, 2016, 2017], names=["early", "late"],
                           n_bets=np.full((2, 5), MIN_BETS, dtype=float))
    picks = walk_forward(fake, by_season)["seasons"]
    # 2016: only 2013-15 known -> "early" (and it loses); 2017: early 11 vs late 6 -> still "early"
    assert [(p["season"], p["name"], p["profit"]) for p in picks] == [(2016, "early", -4.0), (2017, "early", -4.0)]


def test_simulated_seasons_follow_the_market(search, book):
    won = simulate_outcomes(book, search.cand, 2000, np.random.default_rng(1))
    result = (search.cand["market"] == "result").to_numpy()
    per_match = won[result].reshape(3, len(book), -1).sum(axis=0)
    assert (per_match == 1).all()  # exactly one result per match, every season
    home = (search.cand["side"] == "H").to_numpy()
    fair = search.cand.loc[home, "fair"].to_numpy()
    assert won[home].mean(axis=1) == pytest.approx(fair, abs=0.05)


def test_report_ranks_distinct_combinations_with_enough_bets(book):
    report = search_report(book)
    profits = [t["profit"] for t in report["top"]]
    assert profits == sorted(profits, reverse=True)
    assert all(t["n_bets"] >= MIN_BETS for t in report["top"])
    assert len({(t["n_bets"], round(t["profit"], 6)) for t in report["top"]}) == len(report["top"])
    luck = report["luck"]
    assert 0 <= luck["share_as_good"] <= 1
    assert luck == luck_benchmark(Search(book), report["top"][0]["profit"])  # seeded: same every run
