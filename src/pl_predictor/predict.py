"""High-level "predict one match" API used by the dashboard.

Fits a Poisson goals model (for expected goals + full scoreline distribution)
and an Elo-based logistic model (for the headline H/D/A probabilities) on all
available history, then packages both into one human-readable dict - this is
what produces the "Arsenal vs Liverpool" style printout from the README.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pl_predictor.config import OUTCOME_NAMES
from pl_predictor.features.elo import compute_running_elo
from pl_predictor.features.engineering import add_form_features
from pl_predictor.models.baseline_logreg import LogisticOutcomeModel
from pl_predictor.models.poisson_model import PoissonGoalsModel


class MatchPredictor:
    """Fit once on full history, then call .predict(home, away) as many times as needed."""

    def __init__(self, matches: pd.DataFrame):
        with_elo, self.elo = compute_running_elo(matches)
        self.feature_df = add_form_features(with_elo)
        self.known_teams = sorted(set(matches["home_team"]) | set(matches["away_team"]))

        self.elo_model = LogisticOutcomeModel(feature_columns=["elo_diff"], name="elo_logistic")
        self.elo_model.fit(self.feature_df)

        self.poisson_model = PoissonGoalsModel()
        self.poisson_model.fit(self.feature_df)

    def latest_elo_diff(self, home: str, away: str) -> float:
        return self.elo.get(home) - self.elo.get(away)

    def predict(self, home: str, away: str, max_goals_shown: int = 3) -> dict:
        if home not in self.known_teams or away not in self.known_teams:
            unknown = [t for t in (home, away) if t not in self.known_teams]
            raise ValueError(f"Unknown team(s) not in historical data: {unknown}")

        elo_diff = self.latest_elo_diff(home, away)
        outcome_proba = self.elo_model.pipeline.predict_proba(np.array([[elo_diff]]))
        class_order = list(self.elo_model.pipeline.named_steps["clf"].classes_)
        idx = [class_order.index(label) for label in ("H", "D", "A")]
        home_p, draw_p, away_p = outcome_proba[0, idx]

        lam_home, lam_away = self.poisson_model.expected_goals(home, away)
        matrix = self.poisson_model.score_matrix(home, away)

        scores = []
        for i in range(max_goals_shown + 1):
            for j in range(max_goals_shown + 1):
                scores.append({"home_goals": i, "away_goals": j, "probability": float(matrix[i, j])})
        scores.sort(key=lambda s: s["probability"], reverse=True)

        predicted_idx = int(np.argmax([home_p, draw_p, away_p]))
        predicted_label = [f"{home} win", "Draw", f"{away} win"][predicted_idx]

        return {
            "home_team": home,
            "away_team": away,
            "home_win_proba": float(home_p),
            "draw_proba": float(draw_p),
            "away_win_proba": float(away_p),
            "predicted_result": predicted_label,
            "expected_goals_home": lam_home,
            "expected_goals_away": lam_away,
            "most_likely_scores": scores[:5],
            "elo_diff": elo_diff,
        }


def format_prediction(pred: dict) -> str:
    lines = [
        f"{pred['home_team']} vs {pred['away_team']}",
        "",
        f"{OUTCOME_NAMES['H']:<14}{pred['home_win_proba']*100:5.1f}%",
        f"{OUTCOME_NAMES['D']:<14}{pred['draw_proba']*100:5.1f}%",
        f"{OUTCOME_NAMES['A']:<14}{pred['away_win_proba']*100:5.1f}%",
        "",
        f"Predicted result: {pred['predicted_result']}",
        "",
        "Expected goals",
        f"{pred['home_team']:<14}{pred['expected_goals_home']:.2f}",
        f"{pred['away_team']:<14}{pred['expected_goals_away']:.2f}",
        "",
        "Most likely scores",
    ]
    for s in pred["most_likely_scores"]:
        score_str = f"{s['home_goals']}-{s['away_goals']}"
        lines.append(f"{score_str:<14}{s['probability']*100:5.1f}%")
    return "\n".join(lines)
