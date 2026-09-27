"""Independent-Poisson goals model (Maher, 1982 style).

    Goals_home ~ Poisson(lambda_home)
    Goals_away ~ Poisson(lambda_away)

    log(lambda_home) = intercept + home_advantage + attack_home - defense_away
    log(lambda_away) = intercept +                  attack_away - defense_home

We fit this as a single Poisson GLM on "long format" data (two rows per match:
one for the home team's goals, one for the away team's), where each team gets
one attack dummy and one defense dummy. This is exactly a Poisson regression
with team fixed effects; the attack/defense terms above fall out of the
learned per-team dummy coefficients, sign included, with no manual bookkeeping
needed.

Once we have lambda_home and lambda_away for a fixture, the full scoreline
distribution is just the product of two Poisson pmfs (independence
assumption), from which P(Home win) / P(Draw) / P(Away win) are simple sums.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.linear_model import PoissonRegressor

from pl_predictor.models.base import OutcomeModel

DEFAULT_MAX_GOALS = 8


class PoissonGoalsModel(OutcomeModel):
    name = "poisson"

    def __init__(self, alpha: float = 0.005, max_goals: int = DEFAULT_MAX_GOALS):
        self.alpha = alpha
        self.max_goals = max_goals
        self.teams_: list[str] = []
        self.team_to_idx_: dict[str, int] = {}
        self.model_: PoissonRegressor | None = None

    # -- design matrix -----------------------------------------------------
    def _n_teams(self) -> int:
        return len(self.teams_)

    def _row(self, team: str, opponent: str, is_home: int) -> np.ndarray:
        n = self._n_teams()
        # columns: [is_home, attack_dummies(n-1), defense_dummies(n-1)]; team[0] is the reference.
        x = np.zeros(1 + 2 * (n - 1))
        x[0] = is_home
        t_idx = self.team_to_idx_.get(team)
        o_idx = self.team_to_idx_.get(opponent)
        if t_idx is not None and t_idx > 0:
            x[t_idx] = 1.0  # attack dummy block starts at column 1
        if o_idx is not None and o_idx > 0:
            x[(n - 1) + o_idx] = 1.0  # defense dummy block starts after attack block
        return x

    def _long_format(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        rows, goals = [], []
        for r in df.itertuples(index=False):
            rows.append(self._row(r.home_team, r.away_team, is_home=1))
            goals.append(r.home_goals)
            rows.append(self._row(r.away_team, r.home_team, is_home=0))
            goals.append(r.away_goals)
        return np.vstack(rows), np.array(goals, dtype=float)

    # -- OutcomeModel interface ---------------------------------------------
    def fit(self, train_df: pd.DataFrame) -> "PoissonGoalsModel":
        self.teams_ = sorted(set(train_df["home_team"]) | set(train_df["away_team"]))
        self.team_to_idx_ = {t: i for i, t in enumerate(self.teams_)}

        X, y = self._long_format(train_df)
        self.model_ = PoissonRegressor(alpha=self.alpha, max_iter=500)
        self.model_.fit(X, y)
        return self

    def expected_goals(self, home: str, away: str) -> tuple[float, float]:
        assert self.model_ is not None, "call fit() first"
        lam_home = self.model_.predict(self._row(home, away, is_home=1).reshape(1, -1))[0]
        lam_away = self.model_.predict(self._row(away, home, is_home=0).reshape(1, -1))[0]
        return float(lam_home), float(lam_away)

    def score_matrix(self, home: str, away: str, max_goals: int | None = None) -> np.ndarray:
        """P(home scores i, away scores j) for i, j in [0, max_goals]."""
        max_goals = max_goals or self.max_goals
        lam_home, lam_away = self.expected_goals(home, away)
        home_probs = poisson.pmf(np.arange(max_goals + 1), lam_home)
        away_probs = poisson.pmf(np.arange(max_goals + 1), lam_away)
        return np.outer(home_probs, away_probs)

    def outcome_probs_from_matrix(self, matrix: np.ndarray) -> tuple[float, float, float]:
        home_win = np.tril(matrix, k=-1).sum()  # row i (home goals) > col j (away goals)
        draw = np.trace(matrix)
        away_win = np.triu(matrix, k=1).sum()
        return float(home_win), float(draw), float(away_win)

    def predict_proba(self, test_df: pd.DataFrame) -> np.ndarray:
        out = np.zeros((len(test_df), 3))
        for i, r in enumerate(test_df.itertuples(index=False)):
            matrix = self.score_matrix(r.home_team, r.away_team)
            out[i] = self.outcome_probs_from_matrix(matrix)
        # normalize away any tiny mass truncated by max_goals
        out = out / out.sum(axis=1, keepdims=True)
        return out
