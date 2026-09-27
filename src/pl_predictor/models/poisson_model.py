"""Independent-Poisson goals model (Maher 1982 / Dixon-Coles 1997 style).

    Goals_home ~ Poisson(lambda_home)
    Goals_away ~ Poisson(lambda_away)

    log(lambda_home) = mu + home_adv + attack_home - defense_away + promoted terms
    log(lambda_away) = mu +            attack_away - defense_home + promoted terms

Fitted as a single Poisson GLM on "long format" data (two rows per match: one
for the home team's goals, one for the away team's), with one attack and one
defense indicator per team. Three details matter a lot in practice, and all
three were validated on held-out seasons (see scripts/tune_poisson.py):

1. Time decay (Dixon & Coles, 1997). A match played `age` days before the
   most recent training match gets weight 0.5 ** (age / half_life_days).
   Without it, a club's strength is averaged over 25 years: Coventry would be
   rated on its last Premier League season... in 2000-01.

2. Full one-hot team effects + L2 shrinkage toward the league average.
   Dropping a "reference" team (the textbook approach) silently makes the
   L2 penalty pull every poorly-identified team toward *that* team -
   alphabetically first, i.e. Arsenal - which rated newly promoted clubs far
   too strongly. With all teams encoded and an intercept, shrinkage goes
   toward the average instead.

3. An optional "promoted this season" effect for the team and its opponent.
   Intuitively promoted clubs should be weaker than their sparse, heavily
   down-weighted history suggests - but on the validation seasons it made no
   measurable difference once (1) and (2) were in place (log loss 0.9810 vs
   0.9803 without it), so it's off by default rather than kept on a hunch.

Once we have both lambdas, the full scoreline distribution is the product of
two Poisson pmfs, and P(Home win) / P(Draw) / P(Away win) are simple sums.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.linear_model import PoissonRegressor

from pl_predictor.models.base import OutcomeModel

DEFAULT_MAX_GOALS = 8
# Chosen on the 2008-09 -> 2012-13 validation seasons, which come *before*
# every season used in the reported backtest (see scripts/tune_poisson.py).
# The half-life comes from the pre-season walk-forward; alpha from the
# in-season rolling evaluation (weekly refits), because that's how the live
# app uses the model - and where weak shrinkage hurts: alpha=0.001 scored a
# log loss of 0.999 on early-season matches vs 0.980 for alpha=0.01.
DEFAULT_ALPHA = 0.01
DEFAULT_HALF_LIFE_DAYS = 365.0


class PoissonGoalsModel(OutcomeModel):
    name = "poisson"

    def __init__(
        self,
        alpha: float = DEFAULT_ALPHA,
        half_life_days: float | None = DEFAULT_HALF_LIFE_DAYS,
        use_promoted_effect: bool = False,
        max_goals: int = DEFAULT_MAX_GOALS,
    ):
        self.alpha = alpha
        self.half_life_days = half_life_days
        self.use_promoted_effect = use_promoted_effect
        self.max_goals = max_goals
        self.teams_: list[str] = []
        self.team_to_idx_: dict[str, int] = {}
        self.season_teams_: dict[int, set[str]] = {}
        self.latest_season_: int | None = None
        self.model_: PoissonRegressor | None = None

    # -- promoted-club bookkeeping --------------------------------------------
    def _is_promoted(self, teams: np.ndarray, season: np.ndarray) -> np.ndarray:
        """1.0 where the club wasn't in the division the season before, else 0.0.

        Only needs the *previous* season's teams, so it works for a test season
        that isn't in the training data yet (the walk-forward backtest) as well
        as for the in-progress season (live predictions and simulations).
        """
        out = np.zeros(len(teams))
        for i, (team, s) in enumerate(zip(teams, season)):
            prev = self.season_teams_.get(int(s) - 1)
            if prev is not None and team not in prev:
                out[i] = 1.0
        return out

    # -- design matrix -------------------------------------------------------
    def _design(self, team: np.ndarray, opponent: np.ndarray, is_home: np.ndarray, season: np.ndarray) -> np.ndarray:
        """Columns: [is_home, attack one-hot (n), defense one-hot (n), team_promoted, opp_promoted].

        A team never seen in training gets all-zero indicators, i.e. league
        average - plus the promoted effect, which is exactly the right prior
        for a club arriving from the Championship.
        """
        n = len(self.teams_)
        X = np.zeros((len(team), 1 + 2 * n + 2))
        X[:, 0] = is_home
        rows = np.arange(len(team))
        t_idx = np.array([self.team_to_idx_.get(t, -1) for t in team])
        o_idx = np.array([self.team_to_idx_.get(o, -1) for o in opponent])
        known_t, known_o = t_idx >= 0, o_idx >= 0
        X[rows[known_t], 1 + t_idx[known_t]] = 1.0
        X[rows[known_o], 1 + n + o_idx[known_o]] = 1.0
        if self.use_promoted_effect:
            X[:, 1 + 2 * n] = self._is_promoted(team, season)
            X[:, 2 + 2 * n] = self._is_promoted(opponent, season)
        return X

    def _long_format(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        home, away = df["home_team"].to_numpy(), df["away_team"].to_numpy()
        season = df["season_start_year"].to_numpy()
        m = len(df)
        X = np.vstack(
            [
                self._design(home, away, np.ones(m), season),
                self._design(away, home, np.zeros(m), season),
            ]
        )
        y = np.concatenate([df["home_goals"].to_numpy(), df["away_goals"].to_numpy()]).astype(float)

        if self.half_life_days is None:
            w = np.ones(m)
        else:
            dates = pd.to_datetime(df["date"])
            age_days = (dates.max() - dates).dt.days.to_numpy()
            w = 0.5 ** (age_days / self.half_life_days)
        return X, y, np.concatenate([w, w])

    # -- OutcomeModel interface ------------------------------------------------
    def fit(self, train_df: pd.DataFrame) -> "PoissonGoalsModel":
        self.teams_ = sorted(set(train_df["home_team"]) | set(train_df["away_team"]))
        self.team_to_idx_ = {t: i for i, t in enumerate(self.teams_)}
        self.season_teams_ = {
            int(s): set(g["home_team"]) | set(g["away_team"]) for s, g in train_df.groupby("season_start_year")
        }
        self.latest_season_ = max(self.season_teams_)

        X, y, w = self._long_format(train_df)
        self.model_ = PoissonRegressor(alpha=self.alpha, max_iter=1000)
        self.model_.fit(X, y, sample_weight=w)
        return self

    def expected_goals_many(
        self, home: np.ndarray, away: np.ndarray, season: np.ndarray | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Vectorized lambdas for many fixtures at once (used by the season simulator)."""
        assert self.model_ is not None, "call fit() first"
        home, away = np.asarray(home), np.asarray(away)
        if season is None:
            season = np.full(len(home), self.latest_season_)
        m = len(home)
        lam_home = self.model_.predict(self._design(home, away, np.ones(m), season))
        lam_away = self.model_.predict(self._design(away, home, np.zeros(m), season))
        return lam_home, lam_away

    def expected_goals(self, home: str, away: str, season: int | None = None) -> tuple[float, float]:
        s = None if season is None else np.array([season])
        lam_home, lam_away = self.expected_goals_many(np.array([home]), np.array([away]), s)
        return float(lam_home[0]), float(lam_away[0])

    def score_matrix(self, home: str, away: str, max_goals: int | None = None) -> np.ndarray:
        """P(home scores i, away scores j) for i, j in [0, max_goals]."""
        lam_home, lam_away = self.expected_goals(home, away)
        return self._matrix(lam_home, lam_away, max_goals or self.max_goals)

    @staticmethod
    def _matrix(lam_home: float, lam_away: float, max_goals: int) -> np.ndarray:
        goals = np.arange(max_goals + 1)
        return np.outer(poisson.pmf(goals, lam_home), poisson.pmf(goals, lam_away))

    @staticmethod
    def outcome_probs_from_matrix(matrix: np.ndarray) -> tuple[float, float, float]:
        home_win = np.tril(matrix, k=-1).sum()  # row i (home goals) > col j (away goals)
        draw = np.trace(matrix)
        away_win = np.triu(matrix, k=1).sum()
        return float(home_win), float(draw), float(away_win)

    def predict_proba(self, test_df: pd.DataFrame) -> np.ndarray:
        lam_home, lam_away = self.expected_goals_many(
            test_df["home_team"].to_numpy(),
            test_df["away_team"].to_numpy(),
            test_df["season_start_year"].to_numpy(),
        )
        out = np.array(
            [self.outcome_probs_from_matrix(self._matrix(lh, la, self.max_goals)) for lh, la in zip(lam_home, lam_away)]
        )
        # normalize away any tiny mass truncated by max_goals
        return out / out.sum(axis=1, keepdims=True)
