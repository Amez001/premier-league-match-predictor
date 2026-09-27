"""Probable goalscorers for a given fixture.

We deliberately do NOT fit a separate Poisson GLM per player: most players
score too few goals in a season for an individual model to be anything but
noise, and opponent strength is already well captured by the team-level
PoissonGoalsModel (see poisson_model.py). Instead:

  1. Get the team's overall expected goals for the match from the already
     validated team Poisson model (this bakes in the opponent's defense).
  2. Split that total across the squad by each player's historical share of
     the team's goals ("attack_share"), adjusted by a "recent form"
     multiplier - since a player who's been on a hot streak the last couple
     of weeks should get a bigger slice than their season-long average alone
     would suggest.
  3. Re-normalize so the player-level expected goals still sum to the team's
     expected goals - the team total is the thing that's actually been
     backtested, so the player split must not change it.
  4. P(player scores >= 1) = 1 - exp(-lambda_player) (Poisson).

FORM_MULTIPLIER_BOUNDS clips the recent-form adjustment: comparing two
snapshots a week apart means very small sample sizes (a player can look like
a "hat-trick machine" off a single lucky match), so an unclipped ratio would
make the whole thing noisier than just using the season rate.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FORM_MULTIPLIER_BOUNDS = (0.5, 1.8)
MIN_90S_FOR_RECENT_FORM = 0.5  # below this, there isn't enough recent playing time to trust a delta
# Weight of the prior in "pseudo-goals": with 8, a club's first 8 goals of the
# season count as much as the prior, and by midseason (~30 goals) the real
# goal shares dominate. A judgment call - there's no multi-season player
# history in this project to tune it on - chosen so that 4 goals in 5 games
# no longer hands one striker ~60% of his team's attack.
SHARE_PRIOR_PSEUDO_GOALS = 8.0


def _primary_position(position: pd.Series) -> pd.Series:
    """FBref lists hybrids like "FW,MF"; the first listed role is the main one."""
    return position.fillna("MF").astype(str).str.split(",").str[0].str.strip()


def compute_attack_shares(player_df: pd.DataFrame) -> pd.DataFrame:
    """Add an `attack_share` column: each player's expected share of his team's goals.

    Raw season goal shares are extremely noisy early on (one striker scoring
    4 of his team's 7 goals would get 57% of every future goal). So shares
    are shrunk toward a prior built from playing time x the league-wide
    scoring rate of the player's position (forwards score far more per 90
    than defenders), estimated from all current-season players pooled:

        share = (goals + K * prior_share) / (team_goals + K)

    which still sums to exactly 1 within each team.
    """
    df = player_df.copy()
    pos = _primary_position(df["position"])
    league_rate = df.groupby(pos)["season_goals"].sum() / df.groupby(pos)["minutes_90s"].sum().replace(0, np.nan)
    prior_goals = df["minutes_90s"] * pos.map(league_rate).fillna(0.0)

    team_prior = prior_goals.groupby(df["team"]).transform("sum")
    team_minutes = df.groupby("team")["minutes_90s"].transform("sum")
    with np.errstate(invalid="ignore", divide="ignore"):
        prior_share = np.where(team_prior > 0, prior_goals / team_prior, df["minutes_90s"] / team_minutes)
    prior_share = np.nan_to_num(prior_share)

    team_goals = df.groupby("team")["season_goals"].transform("sum")
    k = SHARE_PRIOR_PSEUDO_GOALS
    df["attack_share"] = (df["season_goals"] + k * prior_share) / (team_goals + k)
    return df


def compute_recent_form_multiplier(latest_df: pd.DataFrame, previous_df: pd.DataFrame | None) -> pd.DataFrame:
    """Add a `recent_form_multiplier` column from the delta between two snapshots.

    multiplier = (goals/90 over the delta window) / (season-long goals/90),
    clipped to FORM_MULTIPLIER_BOUNDS. Defaults to 1.0 (neutral - i.e. "just
    use the season rate") whenever there isn't a previous snapshot yet, or a
    player barely played in the delta window.
    """
    df = latest_df.copy()
    df["recent_form_multiplier"] = 1.0

    if previous_df is None:
        return df

    prev = previous_df[["team", "player", "season_goals", "minutes_90s"]].rename(
        columns={"season_goals": "prev_goals", "minutes_90s": "prev_90s"}
    )
    merged = df.merge(prev, on=["team", "player"], how="left")
    merged["prev_goals"] = merged["prev_goals"].fillna(0.0)
    merged["prev_90s"] = merged["prev_90s"].fillna(0.0)

    delta_goals = (merged["season_goals"] - merged["prev_goals"]).clip(lower=0)
    delta_90s = (merged["minutes_90s"] - merged["prev_90s"]).clip(lower=0)

    with np.errstate(invalid="ignore", divide="ignore"):
        recent_goals_per90 = np.where(delta_90s >= MIN_90S_FOR_RECENT_FORM, delta_goals / delta_90s, np.nan)
        ratio = recent_goals_per90 / merged["season_goals_per90"].replace(0, np.nan)

    multiplier = pd.Series(ratio, index=df.index).fillna(1.0)
    df["recent_form_multiplier"] = multiplier.clip(*FORM_MULTIPLIER_BOUNDS)
    return df


def prepare_player_features(latest_df: pd.DataFrame, previous_df: pd.DataFrame | None) -> pd.DataFrame:
    """Full pipeline: raw FBref snapshot(s) -> attack_share + recent_form_multiplier."""
    with_shares = compute_attack_shares(latest_df)
    return compute_recent_form_multiplier(with_shares, previous_df)


def predict_team_scorers(player_df: pd.DataFrame, team: str, team_expected_goals: float, top_n: int = 5) -> pd.DataFrame:
    """Distribute a team's expected goals across its squad and rank by scorer probability.

    `player_df` must already have `attack_share` and `recent_form_multiplier`
    columns (see prepare_player_features). Returns the top_n players sorted
    by scorer probability, with columns: player, position, lambda_goals,
    scorer_probability.
    """
    squad = player_df[player_df["team"] == team].copy()
    if squad.empty:
        return squad.assign(lambda_goals=[], scorer_probability=[])

    weight = squad["attack_share"] * squad["recent_form_multiplier"]
    total_weight = weight.sum()

    if total_weight <= 0:
        # Nobody has scored or played enough minutes to have a share yet
        # (very early season): fall back to a uniform split among anyone
        # who has actually played, rather than dividing by zero.
        played = squad["minutes_90s"] > 0
        weight = played.astype(float)
        total_weight = weight.sum()
        if total_weight <= 0:
            weight = pd.Series(1.0, index=squad.index)
            total_weight = weight.sum()

    squad["lambda_goals"] = team_expected_goals * weight / total_weight
    squad["scorer_probability"] = 1 - np.exp(-squad["lambda_goals"])

    return (
        squad.sort_values("scorer_probability", ascending=False)
        .head(top_n)[["player", "position", "lambda_goals", "scorer_probability"]]
        .reset_index(drop=True)
    )
