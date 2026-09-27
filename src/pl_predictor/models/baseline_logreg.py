"""Multinomial logistic regression: P(Y=k | X) for Y in {Home win, Draw, Away win}.

Used both as the plain "baseline" model (form + table features) and as the
"Elo model" (elo_diff as the sole regressor) - see scripts/run_backtest.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from pl_predictor.config import OUTCOME_LABELS
from pl_predictor.models.base import OutcomeModel


class LogisticOutcomeModel(OutcomeModel):
    def __init__(self, feature_columns: list[str], name: str = "logistic_regression", C: float = 1.0):
        self.feature_columns = feature_columns
        self.name = name
        self.pipeline = Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "clf",
                    # lbfgs fits a genuine multinomial (softmax) model for >2 classes
                    # by default in modern scikit-learn (the old multi_class= flag
                    # was removed after being deprecated).
                    LogisticRegression(
                        solver="lbfgs",
                        C=C,
                        max_iter=2000,
                    ),
                ),
            ]
        )

    def fit(self, train_df: pd.DataFrame) -> "LogisticOutcomeModel":
        X = train_df[self.feature_columns].to_numpy()
        y = train_df["result"].to_numpy()
        self.pipeline.fit(X, y)
        return self

    def predict_proba(self, test_df: pd.DataFrame) -> np.ndarray:
        X = test_df[self.feature_columns].to_numpy()
        proba = self.pipeline.predict_proba(X)
        # sklearn orders classes alphabetically (A, D, H) - reindex to our [H, D, A] convention.
        class_order = list(self.pipeline.named_steps["clf"].classes_)
        idx = [class_order.index(label) for label in OUTCOME_LABELS]
        return proba[:, idx]
