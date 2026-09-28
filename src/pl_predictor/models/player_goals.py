"""Probable goalscorers for a given fixture.

We deliberately do NOT fit a separate Poisson GLM per player: most players
score too few goals in a season for an individual model to be anything but
noise, and opponent strength is already well captured by the team-level
PoissonGoalsModel (see poisson_model.py). Instead:

  1. Get the team's overall expected goals for the match from the already
     validated team Poisson model (this bakes in the opponent's defense).
  2. Keep only the part its own players can score: some of a club's goals
     are the opponents' own goals, credited to no one in the club
     (`credit_rates`, ~96%).
  3. Split that across the squad by each player's shrunk share of the team's
     goals ("attack_share", see `_shrunk_share`). The shares sum to 1, so the
     players' expected goals add back up to the team's.
  4. P(player scores >= 1) = 1 - exp(-lambda_player) (Poisson).

An earlier version also scaled shares by a "recent form" multiplier (goals
per 90 since last week's snapshot vs the season rate, clipped to x0.5-x1.8).
It was never validated, and the season's track record (track_record.py)
showed favourite scorers scoring *less* often than predicted - below the
80% range - with it, and back inside the range without it. A week of games
is too small a sample for a hot streak to mean much; it was removed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Weight of the prior in "pseudo-events" (goals or assists): with 8, a club's
# first 8 goals of the season count as much as the prior, and by midseason
# (~30 goals) the real shares dominate. A judgment call - there's no
# multi-season player history in this project to tune it on - chosen so that
# 4 goals in 5 games no longer hands one striker ~60% of his team's attack.
SHARE_PRIOR_WEIGHT = 8.0
# How much of last season a player needs before his own per-90 rate outweighs
# his position's league rate in the prior: with 10, a regular starter (~30
# full matches) is ~75% his own record, a squad player (~5) mostly his
# position's.
LAST_SEASON_PRIOR_90S = 10.0
# Fallbacks for `credit_rates` when no season has both player and team
# totals yet - the 2025-26 values.
TYPICAL_GOAL_CREDIT_RATE = 0.96
TYPICAL_ASSISTS_PER_GOAL = 0.66


def _primary_position(position: pd.Series) -> pd.Series:
    """FBref lists hybrids like "FW,MF"; the first listed role is the main one."""
    return position.fillna("MF").astype(str).str.split(",").str[0].str.strip()


def player_identity(df: pd.DataFrame) -> pd.Series:
    """A player who changed clubs mid-season has one FBref row per club; name
    + birth year + nationality identifies him across both (and across
    seasons) without merging two different players who happen to share a name."""
    parts = [df["player"].astype(str)]
    if "born" in df.columns:
        # CSV round-trips can turn 2001 into 2001.0 - normalize before comparing
        parts.append(pd.to_numeric(df["born"], errors="coerce").astype("Int64").astype(str))
    if "nation" in df.columns:
        parts.append(df["nation"].fillna("").astype(str))
    return pd.concat(parts, axis=1).agg("|".join, axis=1)


def _shrunk_share(df: pd.DataFrame, value_col: str, last_season: pd.DataFrame | None = None) -> pd.Series:
    """Each player's share of his team's total `value_col` (goals or assists),
    shrunk toward a prior (see compute_attack_shares for the rationale):

        share = (value + K * prior_share) / (team_total + K)

    which sums to exactly 1 within each team. The prior is playing time x an
    expected per-90 rate: the player's own rate last season when available,
    itself shrunk toward his position's league-wide rate - so a proven scorer
    starts the season with a big slice, a newcomer with his position's average.
    """
    pos = _primary_position(df["position"])
    pos_rate = pos.map(
        df.groupby(pos)[value_col].sum() / df.groupby(pos)["minutes_90s"].sum().replace(0, np.nan)
    ).fillna(0.0)

    rate = pos_rate
    if last_season is not None and not last_season.empty:
        prev = last_season.assign(_id=player_identity(last_season)).groupby("_id")[["minutes_90s", value_col]].sum()
        ident = player_identity(df)
        prev_90s = ident.map(prev["minutes_90s"]).fillna(0.0)
        prev_value = ident.map(prev[value_col]).fillna(0.0)
        m0 = LAST_SEASON_PRIOR_90S
        rate = (prev_value + m0 * pos_rate) / (prev_90s + m0)

    prior_value = df["minutes_90s"] * rate

    team_prior = prior_value.groupby(df["team"]).transform("sum")
    team_minutes = df.groupby("team")["minutes_90s"].transform("sum")
    with np.errstate(invalid="ignore", divide="ignore"):
        prior_share = np.where(team_prior > 0, prior_value / team_prior, df["minutes_90s"] / team_minutes)
    prior_share = np.nan_to_num(prior_share)

    team_total = df.groupby("team")[value_col].transform("sum")
    k = SHARE_PRIOR_WEIGHT
    return (df[value_col] + k * prior_share) / (team_total + k)


def compute_attack_shares(player_df: pd.DataFrame, last_season: pd.DataFrame | None = None) -> pd.DataFrame:
    """Add an `attack_share` column: each player's expected share of his team's goals.

    Raw season goal shares are extremely noisy early on (one striker scoring
    4 of his team's 7 goals would get 57% of every future goal). So shares
    are shrunk toward a prior built from playing time x the league-wide
    scoring rate of the player's position (forwards score far more per 90
    than defenders) or, better, the player's own rate last season - see
    `_shrunk_share`.
    """
    df = player_df.copy()
    df["attack_share"] = _shrunk_share(df, "season_goals", last_season)
    return df


def compute_assist_shares(player_df: pd.DataFrame, last_season: pd.DataFrame | None = None) -> pd.DataFrame:
    """Same shrinkage as `compute_attack_shares`, applied to assists instead
    of goals - used to project the top assist provider (see season_awards.py).
    """
    df = player_df.copy()
    df["assist_share"] = _shrunk_share(df, "season_assists", last_season)
    return df


def mark_current_club(latest_df: pd.DataFrame, previous_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Add `is_current_club`: False on the row of a club a player has left.

    Season totals can't say which club came last, so: the club where the
    player's minutes grew since the previous snapshot wins; without one (or
    if neither moved), the club where he has played the most this season.
    """
    df = latest_df.copy()
    df["is_current_club"] = True
    identity = player_identity(df)
    moved = identity.duplicated(keep=False)
    if not moved.any():
        return df

    recent = pd.Series(0.0, index=df.index)
    if previous_df is not None:
        prev = previous_df.assign(_id=player_identity(previous_df)).set_index(["_id", "team"])["minutes_90s"]
        keys = list(zip(identity, df["team"]))
        prev_minutes = pd.Series([prev.get(k, 0.0) for k in keys], index=df.index)
        recent = (df["minutes_90s"] - prev_minutes).clip(lower=0)

    ranked = df.assign(_id=identity, _recent=recent).sort_values(["_recent", "minutes_90s"], ascending=False)
    current_rows = ranked.drop_duplicates("_id", keep="first").index
    df.loc[moved & ~df.index.isin(current_rows), "is_current_club"] = False
    return df


def credit_rates(
    matches: pd.DataFrame,
    last_season: pd.DataFrame | None = None,
    current_players: pd.DataFrame | None = None,
) -> tuple[float, float]:
    """(goal_credit_rate, assists_per_goal).

    goal_credit_rate: the share of a club's goals credited to one of its own
    players. The rest are the opponents' own goals, which no player of the
    club scores - so they must not be handed out to its forwards.
    assists_per_goal: assists per team goal (not every goal has one).

    Measured on last season when its per-player totals are available: a full
    season (~1,000 goals, ~40 own goals) is a far steadier estimate than the
    first weeks of this one. Otherwise on the current season so far, else
    typical league values.
    """

    def measured(players: pd.DataFrame | None, season: int) -> tuple[float, float] | None:
        if players is None or players.empty:
            return None
        played = matches[matches["season_start_year"] == season]
        team_goals = float((played["home_goals"] + played["away_goals"]).sum())
        if team_goals <= 0:
            return None
        return (
            min(1.0, float(players["season_goals"].sum()) / team_goals),
            min(1.0, float(players["season_assists"].sum()) / team_goals),
        )

    if last_season is not None and "season_start_year" in last_season.columns and not last_season.empty:
        rates = measured(last_season, int(last_season["season_start_year"].iloc[0]))
        if rates:
            return rates
    rates = measured(current_players, int(matches["season_start_year"].max()))
    return rates or (TYPICAL_GOAL_CREDIT_RATE, TYPICAL_ASSISTS_PER_GOAL)


def prepare_player_features(
    latest_df: pd.DataFrame,
    previous_df: pd.DataFrame | None,
    last_season: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Full pipeline: raw FBref snapshot(s) -> attack_share, assist_share and
    is_current_club.

    previous_df is the previous *snapshot* of this season (it tells which club
    a player who moved mid-season is playing for now); last_season is last
    season's per-player totals (share priors).
    """
    with_shares = compute_assist_shares(compute_attack_shares(latest_df, last_season), last_season)
    return mark_current_club(with_shares, previous_df)


def predict_team_scorers(player_df: pd.DataFrame, team: str, team_expected_goals: float, top_n: int = 5) -> pd.DataFrame:
    """Distribute the goals a team's own players are expected to score across
    its squad and rank by scorer probability.

    `team_expected_goals` should already exclude own goals (team expected
    goals x goal credit rate, see `credit_rates`). `player_df` must have an
    `attack_share` column (see prepare_player_features). Returns the top_n
    players sorted by scorer probability, with columns: player, position,
    lambda_goals, scorer_probability.
    """
    squad = player_df[player_df["team"] == team]
    if "is_current_club" in squad.columns:
        squad = squad[squad["is_current_club"]]  # a player who has left can't score for them
    squad = squad.copy()
    if squad.empty:
        return squad.assign(lambda_goals=[], scorer_probability=[])

    weight = squad["attack_share"]
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
