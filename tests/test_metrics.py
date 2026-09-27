import numpy as np

from pl_predictor.evaluation.metrics import accuracy, multiclass_brier_score, multiclass_log_loss


def test_perfect_predictions_have_zero_loss():
    y_true = ["H", "D", "A"]
    proba = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
    assert accuracy(y_true, proba) == 1.0
    assert multiclass_brier_score(y_true, proba) == 0.0
    assert multiclass_log_loss(y_true, proba) < 1e-10


def test_confident_wrong_prediction_is_penalized_more_than_uncertain_one():
    y_true = ["H"]
    confident_wrong = np.array([[0.01, 0.01, 0.98]])
    uncertain_wrong = np.array([[0.30, 0.35, 0.35]])
    assert multiclass_log_loss(y_true, confident_wrong) > multiclass_log_loss(y_true, uncertain_wrong)
    assert multiclass_brier_score(y_true, confident_wrong) > multiclass_brier_score(y_true, uncertain_wrong)


def test_naive_uniform_prediction_has_known_brier_score():
    y_true = ["H"]
    uniform = np.array([[1 / 3, 1 / 3, 1 / 3]])
    # Brier = (2/3)^2 + (1/3)^2 + (1/3)^2 = 4/9 + 1/9 + 1/9 = 6/9
    assert abs(multiclass_brier_score(y_true, uniform) - 6 / 9) < 1e-9
