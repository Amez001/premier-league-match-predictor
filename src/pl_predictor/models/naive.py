"""Sanity-check baseline: always predict the training set's historical H/D/A frequency.

Any model that can't beat this on log loss / Brier score isn't adding value -
it's the equivalent of "home teams win about 45% of the time" with no
per-match information at all.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pl_predictor.config import OUTCOME_LABELS
from pl_predictor.models.base import OutcomeModel


class ConstantFrequencyModel(OutcomeModel):
    name = "naive_base_rate"

    def __init__(self):
        self.proba_: np.ndarray | None = None

    def fit(self, train_df: pd.DataFrame) -> "ConstantFrequencyModel":
        counts = train_df["result"].value_counts(normalize=True)
        self.proba_ = np.array([counts.get(label, 0.0) for label in OUTCOME_LABELS])
        return self

    def predict_proba(self, test_df: pd.DataFrame) -> np.ndarray:
        assert self.proba_ is not None, "call fit() first"
        return np.tile(self.proba_, (len(test_df), 1))
