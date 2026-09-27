"""Metrics for evaluating probabilistic 3-class predictions.

Accuracy alone can't tell "Arsenal 51% / Draw 25% / Away 24%" apart from a
blunt "Arsenal win" - both count as one correct prediction if Arsenal wins.
Log loss and the Brier score both reward well-calibrated probabilities and
punish confident wrong predictions much harder than accuracy does, which is
why they're the primary metrics here (see README for a worked example).
"""
from __future__ import annotations

import numpy as np

from pl_predictor.config import OUTCOME_TO_IDX


def _y_true_idx(y_true) -> np.ndarray:
    return np.array([OUTCOME_TO_IDX[label] for label in y_true])


def accuracy(y_true, proba: np.ndarray) -> float:
    y_idx = _y_true_idx(y_true)
    preds = np.argmax(proba, axis=1)
    return float(np.mean(preds == y_idx))


def multiclass_log_loss(y_true, proba: np.ndarray, eps: float = 1e-15) -> float:
    """-1/N * sum_i log P(y_i), with proba columns in [H, D, A] order.

    Implemented by hand (rather than sklearn.metrics.log_loss) because sklearn
    silently re-sorts a custom `labels` list alphabetically internally, which
    would misalign our [H, D, A] column order - see the discussion in
    tests/test_metrics.py.
    """
    y_idx = _y_true_idx(y_true)
    picked = np.clip(proba[np.arange(len(y_idx)), y_idx], eps, 1.0)
    return float(-np.mean(np.log(picked)))


def multiclass_brier_score(y_true, proba: np.ndarray) -> float:
    """Mean squared error between predicted probabilities and the one-hot outcome,
    summed across the 3 classes for each match (the standard multiclass Brier score).
    Ranges from 0 (perfect) to 2 (maximally wrong and confident).
    """
    y_idx = _y_true_idx(y_true)
    one_hot = np.zeros_like(proba)
    one_hot[np.arange(len(y_idx)), y_idx] = 1.0
    return float(np.mean(np.sum((proba - one_hot) ** 2, axis=1)))


def evaluate(y_true, proba: np.ndarray) -> dict:
    return {
        "accuracy": accuracy(y_true, proba),
        "log_loss": multiclass_log_loss(y_true, proba),
        "brier_score": multiclass_brier_score(y_true, proba),
        "n_matches": len(y_true),
    }
