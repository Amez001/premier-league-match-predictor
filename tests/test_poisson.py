import numpy as np

from pl_predictor.models.poisson_model import PoissonGoalsModel


def test_score_matrix_sums_to_one(toy_matches):
    model = PoissonGoalsModel(alpha=1.0).fit(toy_matches)
    matrix = model.score_matrix("Arsenal", "Chelsea")
    assert matrix.shape == (model.max_goals + 1, model.max_goals + 1)
    assert np.isclose(matrix.sum(), 1.0, atol=1e-3)


def test_outcome_probabilities_sum_to_one(toy_matches):
    model = PoissonGoalsModel(alpha=1.0).fit(toy_matches)
    proba = model.predict_proba(toy_matches)
    assert proba.shape == (len(toy_matches), 3)
    assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-6)


def test_stronger_attacking_team_has_higher_expected_goals(toy_matches):
    model = PoissonGoalsModel(alpha=1.0).fit(toy_matches)
    # Liverpool scored 3+1+1=5 across matches, Everton scored 1+0+2=3 conceded a lot;
    # Liverpool should have a higher expected-goals estimate than Everton in the same fixture context.
    lam_liv, _ = model.expected_goals("Liverpool", "Everton")
    lam_eve, _ = model.expected_goals("Everton", "Liverpool")
    assert lam_liv > lam_eve
