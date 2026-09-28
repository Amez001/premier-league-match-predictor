"""High-level "predict one match" API used by the dashboard.

Fits a Poisson goals model (for expected goals + full scoreline distribution)
and an Elo-based logistic model (for the headline H/D/A probabilities) on all
available history, then packages both into one human-readable dict - this is
what produces the "Arsenal vs Liverpool" style printout from the README.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from pl_predictor.config import OUTCOME_NAMES
from pl_predictor.data.load import get_current_season_teams
from pl_predictor.data.player_stats import load_latest_snapshot, load_previous_season_totals, load_previous_snapshot
from pl_predictor.features.elo import compute_running_elo
from pl_predictor.features.engineering import add_form_features
from pl_predictor.models.baseline_logreg import LogisticOutcomeModel
from pl_predictor.models.player_goals import credit_rates, predict_team_scorers, prepare_player_features
from pl_predictor.models.poisson_model import PoissonGoalsModel

logger = logging.getLogger(__name__)

SCORE_GRID_MAX_GOALS = 5


_LOAD_PLAYERS = object()  # sentinel: "load the latest player snapshot from disk"


def load_player_features() -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """(player features, last season's per-player totals) from disk.

    Best-effort: probable-scorer predictions are optional extra flavor, never
    something the rest of the app should crash over if the FBref scrape
    hasn't been run yet (see scripts/download_player_data.py) or failed.
    """
    try:
        latest = load_latest_snapshot()
    except FileNotFoundError:
        logger.info("no player data snapshot found; probable-scorer predictions disabled")
        return None, None
    previous = load_previous_snapshot()
    last_season = None
    if "season_start_year" in latest.columns:
        last_season = load_previous_season_totals(int(latest["season_start_year"].iloc[0]))
    return prepare_player_features(latest, previous, last_season), last_season


class MatchPredictor:
    """Fit once on full history, then call .predict(home, away) as many times as needed.

    `teams`, `player_df` and `last_season` default to the live setup (this
    season's clubs, latest player snapshot, last season's totals). The track
    record passes them explicitly to rebuild the predictor as it stood before
    a past matchweek: fitted on earlier matches only, with player totals
    rebuilt from earlier matches.
    """

    def __init__(
        self,
        matches: pd.DataFrame,
        teams: list[str] | None = None,
        player_df=_LOAD_PLAYERS,
        last_season: pd.DataFrame | None = None,
    ):
        with_elo, self.elo = compute_running_elo(matches)
        self.feature_df = add_form_features(with_elo)
        # Only the 20 clubs actually in the Premier League this season - not
        # every club that has passed through the division across 25 years.
        self.known_teams = teams if teams is not None else get_current_season_teams(matches)

        self.elo_model = LogisticOutcomeModel(feature_columns=["elo_diff"], name="elo_logistic")
        self.elo_model.fit(self.feature_df)

        self.poisson_model = PoissonGoalsModel()
        self.poisson_model.fit(self.feature_df)

        if player_df is _LOAD_PLAYERS:
            player_df, last_season = load_player_features()
        self.player_df = player_df
        self.last_season = last_season
        # Only the goals a club's own players score are split among its squad;
        # the rest (~4%) are the opponents' own goals.
        self.goal_credit_rate, self.assists_per_goal = credit_rates(matches, last_season, player_df)

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

        grid = self.poisson_model.score_matrix(home, away, max_goals=SCORE_GRID_MAX_GOALS)

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
            # P(home scores i, away scores j) for i, j in 0..5, for the scoreline heatmap
            "score_matrix": grid.tolist(),
            "elo_diff": elo_diff,
            "elo_home": self.elo.get(home),
            "elo_away": self.elo.get(away),
            "top_scorers_home": self._top_scorers(home, lam_home),
            "top_scorers_away": self._top_scorers(away, lam_away),
        }

    def _top_scorers(self, team: str, team_expected_goals: float, top_n: int = 5) -> list[dict]:
        if self.player_df is None:
            return []
        scorers = predict_team_scorers(self.player_df, team, team_expected_goals * self.goal_credit_rate, top_n=top_n)
        return scorers.to_dict(orient="records")


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

    if pred["top_scorers_home"] or pred["top_scorers_away"]:
        lines += ["", "Most likely scorers"]
        for label, scorers in ((pred["home_team"], pred["top_scorers_home"]), (pred["away_team"], pred["top_scorers_away"])):
            lines.append(f"{label}:")
            for s in scorers:
                lines.append(f"  {s['player']:<20}{s['scorer_probability']*100:5.1f}%")

    return "\n".join(lines)
