"""Common interface every model in this project implements.

Keeping this tiny and uniform is what lets scripts/run_backtest.py loop over
Elo, logistic regression, Poisson and the tree ensembles identically.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class OutcomeModel(ABC):
    """A model that predicts P(Home win), P(Draw), P(Away win) for matches."""

    name: str = "base"

    @abstractmethod
    def fit(self, train_df: pd.DataFrame) -> "OutcomeModel":
        """Fit on a dataframe of past matches (already feature-engineered)."""

    @abstractmethod
    def predict_proba(self, test_df: pd.DataFrame) -> np.ndarray:
        """Return an (n_matches, 3) array of probabilities, columns [H, D, A]."""

    def predict(self, test_df: pd.DataFrame) -> np.ndarray:
        proba = self.predict_proba(test_df)
        labels = np.array(["H", "D", "A"])
        return labels[np.argmax(proba, axis=1)]
