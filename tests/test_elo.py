from pl_predictor.features.elo import EloRatings, compute_running_elo


def test_winner_gains_rating_loser_loses_it():
    elo = EloRatings(k=20, home_advantage=0, use_margin_multiplier=False)
    pre_home = elo.get("A")
    pre_away = elo.get("B")
    elo.update("A", "B", home_goals=2, away_goals=0)
    assert elo.get("A") > pre_home
    assert elo.get("B") < pre_away


def test_ratings_are_zero_sum_without_home_advantage():
    elo = EloRatings(k=20, home_advantage=0, use_margin_multiplier=False)
    elo.update("A", "B", home_goals=1, away_goals=0)
    elo.update("B", "A", home_goals=2, away_goals=2)
    total = elo.get("A") + elo.get("B")
    assert abs(total - 2 * elo.initial_rating) < 1e-9


def test_compute_running_elo_is_leakage_safe(toy_matches):
    out, elo = compute_running_elo(toy_matches)
    # first match of the tournament: both teams must still be at the initial rating
    first = out.iloc[0]
    assert first["elo_home_pre"] == elo.initial_rating
    assert first["elo_away_pre"] == elo.initial_rating
    # a later match's pre-ratings must differ from the initial rating (history accrued)
    last = out.iloc[-1]
    assert last["elo_home_pre"] != elo.initial_rating
