"""Monte Carlo projection of the season's top scorer and top assist provider.

Same machinery as the team-level season simulation (simulation.py), pushed
down to players:

1. Every club's expected goals over its *remaining* fixtures come from the
   time-decayed Poisson goals model: Lambda_club = sum of its per-fixture
   lambdas, so the club's future goals ~ Poisson(Lambda_club).
2. Each future goal is credited to a player with probability
   credit_rate x share_i, where share_i is the shrunk goal share from
   player_goals.py (assist_share for assists) and credit_rate is measured on
   last season (`credit_rates`): the fraction of team goals credited to a
   scorer (the rest are own goals), or assists per team goal. The Match
   page's probable scorers use the same goal credit rate.
3. Poisson thinning: splitting a Poisson(Lambda) count at random with
   probabilities p_i gives *independent* Poisson(Lambda * p_i) counts. So
   each player's future tally can be drawn directly and independently -
   exact under the model, no need to simulate goal by goal.
4. Final tally = goals already scored (all clubs, for a player who moved)
   + simulated future goals (current club only). P(top scorer) = share of
   simulations where the player has the most; a tie is a shared award, so
   tied players split that simulation's credit.

Same caveats as the team simulation: shares and strengths stay fixed for
the rest of the season (no injuries, rotation or transfers), so leaders'
odds are somewhat overconfident early on.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pl_predictor.data.load import get_current_season_teams
from pl_predictor.models.player_goals import credit_rates, player_identity
from pl_predictor.models.poisson_model import PoissonGoalsModel
from pl_predictor.simulation import DEFAULT_N_SIMS, remaining_fixtures

TOP_N_RETURNED = 10


def remaining_expected_goals(matches: pd.DataFrame, model: PoissonGoalsModel) -> pd.Series:
    """Each current club's total expected goals over its remaining fixtures."""
    season = int(matches["season_start_year"].max())
    teams = get_current_season_teams(matches)
    played = matches[matches["season_start_year"] == season]
    fixtures = remaining_fixtures(played, teams)
    totals = pd.Series(0.0, index=teams)
    if fixtures.empty:
        return totals
    lam_h, lam_a = model.expected_goals_many(
        fixtures["home_team"].to_numpy(), fixtures["away_team"].to_numpy(), np.full(len(fixtures), season)
    )
    totals = totals.add(pd.Series(lam_h).groupby(fixtures["home_team"].to_numpy()).sum(), fill_value=0.0)
    totals = totals.add(pd.Series(lam_a).groupby(fixtures["away_team"].to_numpy()).sum(), fill_value=0.0)
    return totals


def _award_race(
    per_player: pd.DataFrame,
    current_col: str,
    future_lambda: np.ndarray,
    n_sims: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    current = per_player[current_col].to_numpy(dtype=float)
    future = rng.poisson(future_lambda, size=(n_sims, len(per_player)))
    final = current[None, :] + future

    # Ties share the award: each tied player gets 1/k of that simulation.
    leaders = final == final.max(axis=1, keepdims=True)
    credit = leaders / leaders.sum(axis=1, keepdims=True)

    out = per_player[["player", "team", "position"]].copy()
    out["current"] = current.astype(int)
    out["expected_final"] = final.mean(axis=0)
    out["p10"] = np.percentile(final, 10, axis=0)
    out["p90"] = np.percentile(final, 90, axis=0)
    out["p_top"] = credit.mean(axis=0)
    return (
        out.sort_values(["p_top", "expected_final"], ascending=False)
        .head(TOP_N_RETURNED)
        .reset_index(drop=True)
    )


def project_awards(
    matches: pd.DataFrame,
    player_df: pd.DataFrame,
    model: PoissonGoalsModel,
    last_season: pd.DataFrame | None = None,
    n_sims: int = DEFAULT_N_SIMS,
    seed: int | None = 42,
) -> dict:
    """Top-scorer and top-assist races. `player_df` must come from
    prepare_player_features (attack_share, assist_share, is_current_club);
    `last_season` (per-player totals) sets the goal credit and assist rates."""
    goal_credit_rate, assists_per_goal = credit_rates(matches, last_season, player_df)

    club_lambda = remaining_expected_goals(matches, model)

    # Future goals only at the current club; a departed player's old row
    # keeps his past goals but gets no share of the old club's future.
    df = player_df.copy()
    df["id"] = player_identity(df)
    current = df[df["is_current_club"]].copy()
    for col in ("attack_share", "assist_share"):
        current[col] = current[col] / current.groupby("team")[col].transform("sum")
    current["lambda_goals"] = current["team"].map(club_lambda).fillna(0.0) * goal_credit_rate * current["attack_share"]
    current["lambda_assists"] = (
        current["team"].map(club_lambda).fillna(0.0) * assists_per_goal * current["assist_share"]
    )

    totals = df.groupby("id")[["season_goals", "season_assists"]].sum()
    per_player = current.set_index("id")[["player", "team", "position", "lambda_goals", "lambda_assists"]].join(totals)
    per_player = per_player.reset_index(drop=True)

    rng = np.random.default_rng(seed)
    scorers = _award_race(per_player, "season_goals", per_player["lambda_goals"].to_numpy(), n_sims, rng)
    assisters = _award_race(per_player, "season_assists", per_player["lambda_assists"].to_numpy(), n_sims, rng)

    return {
        "n_sims": n_sims,
        "goal_credit_rate": goal_credit_rate,
        "assists_per_goal": assists_per_goal,
        "top_scorer": scorers.to_dict(orient="records"),
        "top_assister": assisters.to_dict(orient="records"),
    }
