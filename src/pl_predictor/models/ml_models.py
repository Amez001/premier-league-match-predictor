"""Random Forest and XGBoost classifiers, on the same engineered features as
the logistic regression baseline (see features/engineering.py). These are the
"throw more flexible models at it" comparison point in the backtest - the
interesting question is whether they actually beat Elo/Poisson out-of-sample,
or just overfit historical noise.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from pl_predictor.config import OUTCOME_LABELS
from pl_predictor.models.base import OutcomeModel

try:
    from xgboost import XGBClassifier

    _HAS_XGBOOST = True
except ImportError:
    _HAS_XGBOOST = False


class RandomForestOutcomeModel(OutcomeModel):
    name = "random_forest"

    def __init__(self, feature_columns: list[str], n_estimators: int = 400, max_depth: int = 5, random_state: int = 42):
        self.feature_columns = feature_columns
        self.clf = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_leaf=20,
            random_state=random_state,
            n_jobs=-1,
        )

    def fit(self, train_df: pd.DataFrame) -> "RandomForestOutcomeModel":
        self.clf.fit(train_df[self.feature_columns].to_numpy(), train_df["result"].to_numpy())
        return self

    def predict_proba(self, test_df: pd.DataFrame) -> np.ndarray:
        proba = self.clf.predict_proba(test_df[self.feature_columns].to_numpy())
        class_order = list(self.clf.classes_)
        idx = [class_order.index(label) for label in OUTCOME_LABELS]
        return proba[:, idx]


class XGBoostOutcomeModel(OutcomeModel):
    name = "xgboost"

    def __init__(self, feature_columns: list[str], n_estimators: int = 300, max_depth: int = 3,
                 learning_rate: float = 0.05, random_state: int = 42):
        if not _HAS_XGBOOST:
            raise ImportError("xgboost is not installed; `pip install xgboost` to use XGBoostOutcomeModel")
        self.feature_columns = feature_columns
        self._label_to_code = {"H": 0, "D": 1, "A": 2}
        self._code_to_label = {v: k for k, v in self._label_to_code.items()}
        self.clf = XGBClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            objective="multi:softprob",
            num_class=3,
            random_state=random_state,
            eval_metric="mlogloss",
        )

    def fit(self, train_df: pd.DataFrame) -> "XGBoostOutcomeModel":
        y = train_df["result"].map(self._label_to_code).to_numpy()
        self.clf.fit(train_df[self.feature_columns].to_numpy(), y)
        return self

    def predict_proba(self, test_df: pd.DataFrame) -> np.ndarray:
        proba = self.clf.predict_proba(test_df[self.feature_columns].to_numpy())
        # XGBClassifier orders columns by class code 0..2, which is already [H, D, A].
        return proba


def xgboost_available() -> bool:
    return _HAS_XGBOOST
