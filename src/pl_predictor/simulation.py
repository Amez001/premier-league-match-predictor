"""Monte Carlo simulation of the rest of the season -> title / top-4 / relegation odds.

1. Build the current league table from the matches already played.
2. Derive the remaining fixtures without any external calendar: a Premier
   League season is a double round-robin, so every ordered pair (home, away)
   of the 20 clubs is played exactly once; remaining = all pairs - played.
3. For each remaining fixture, get (lambda_home, lambda_away) from the
   time-decayed Poisson goals model, and draw n_sims independent scorelines.
4. Add the simulated points / goals to the real table and rank each
   simulated final table (points, then goal difference, then goals scored,
   then a coin flip - the real rules go on to head-to-head, which is too rare
   to matter here).
5. Probabilities = share of simulations where the event happened.

Known limitation (also shown on the website): team strengths are held fixed
for the whole simulation. Injuries, transfers and form swings aren't modeled,
and uncertainty about the strengths themselves isn't propagated, so the odds
for the favourite are somewhat overconfident, especially early in the season.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from pl_predictor.data.load import get_current_season_teams
from pl_predictor.models.poisson_model import PoissonGoalsModel

DEFAULT_N_SIMS = 10_000
TOP_N = 4  # Champions League places (the extra 5th "European performance" spot varies by year)
RELEGATION_SPOTS = 3


def league_table(season_matches: pd.DataFrame, teams: list[str]) -> pd.DataFrame:
    """Standard league table (played, W/D/L, GF/GA/GD, points) for `teams`."""
    rows = {t: dict(played=0, won=0, drawn=0, lost=0, goals_for=0, goals_against=0) for t in teams}
    for r in season_matches.itertuples(index=False):
        for team, gf, ga in ((r.home_team, r.home_goals, r.away_goals), (r.away_team, r.away_goals, r.home_goals)):
            row = rows[team]
            row["played"] += 1
            row["goals_for"] += gf
            row["goals_against"] += ga
            row["won" if gf > ga else "drawn" if gf == ga else "lost"] += 1

    table = pd.DataFrame.from_dict(rows, orient="index").rename_axis("team").reset_index()
    table["goal_diff"] = table["goals_for"] - table["goals_against"]
    table["points"] = 3 * table["won"] + table["drawn"]
    return table.sort_values(["points", "goal_diff", "goals_for"], ascending=False).reset_index(drop=True)


def remaining_fixtures(season_matches: pd.DataFrame, teams: list[str]) -> pd.DataFrame:
    played = set(zip(season_matches["home_team"], season_matches["away_team"]))
    fixtures = [(h, a) for h in teams for a in teams if h != a and (h, a) not in played]
    return pd.DataFrame(fixtures, columns=["home_team", "away_team"])


@dataclass
class SeasonSimulation:
    season_start_year: int
    n_sims: int
    matches_played: int
    matches_remaining: int
    current_table: pd.DataFrame
    # one row per team: current + expected points, title/top-4/relegation odds,
    # and position_probs (list of 20 probabilities, 1st place first)
    projections: pd.DataFrame

    def to_dict(self) -> dict:
        return {
            "season_start_year": self.season_start_year,
            "n_sims": self.n_sims,
            "matches_played": self.matches_played,
            "matches_remaining": self.matches_remaining,
            "current_table": self.current_table.to_dict(orient="records"),
            "projections": self.projections.to_dict(orient="records"),
        }


def simulate_season(
    matches: pd.DataFrame,
    model: PoissonGoalsModel,
    n_sims: int = DEFAULT_N_SIMS,
    seed: int | None = 42,
) -> SeasonSimulation:
    """`model` must already be fitted on history including the current season's played matches."""
    season = int(matches["season_start_year"].max())
    teams = get_current_season_teams(matches)
    n_teams = len(teams)
    idx = {t: i for i, t in enumerate(teams)}

    played = matches[matches["season_start_year"] == season]
    table = league_table(played, teams)
    fixtures = remaining_fixtures(played, teams)
    rng = np.random.default_rng(seed)

    # --- simulate every remaining fixture n_sims times, fully vectorized ------
    pts = np.zeros((n_sims, n_teams))
    gf = np.zeros((n_sims, n_teams))
    ga = np.zeros((n_sims, n_teams))
    if len(fixtures):
        lam_h, lam_a = model.expected_goals_many(
            fixtures["home_team"].to_numpy(), fixtures["away_team"].to_numpy(), np.full(len(fixtures), season)
        )
        hg = rng.poisson(lam_h, size=(n_sims, len(fixtures)))
        ag = rng.poisson(lam_a, size=(n_sims, len(fixtures)))
        home_pts = 3 * (hg > ag) + (hg == ag)
        away_pts = 3 * (ag > hg) + (hg == ag)

        # (fixtures x teams) incidence matrices turn per-fixture results into
        # per-team totals with two matrix products instead of a Python loop.
        H = np.zeros((len(fixtures), n_teams))
        A = np.zeros((len(fixtures), n_teams))
        H[np.arange(len(fixtures)), fixtures["home_team"].map(idx).to_numpy()] = 1
        A[np.arange(len(fixtures)), fixtures["away_team"].map(idx).to_numpy()] = 1
        pts = home_pts @ H + away_pts @ A
        gf = hg @ H + ag @ A
        ga = ag @ H + hg @ A

    by_team = table.set_index("team").loc[teams]
    final_pts = pts + by_team["points"].to_numpy()
    final_gd = (gf - ga) + by_team["goal_diff"].to_numpy()
    final_gf = gf + by_team["goals_for"].to_numpy()

    # --- rank every simulated table ---------------------------------------------
    # Lexicographic (points, GD, GF, random) packed into one sortable float;
    # the offsets keep GD non-negative and each component in its own range.
    score = final_pts * 1e7 + (final_gd + 1000) * 1e3 + final_gf + rng.random(final_pts.shape)
    order = np.argsort(-score, axis=1)
    position = np.empty_like(order)
    np.put_along_axis(position, order, np.arange(n_teams)[None, :].repeat(n_sims, axis=0), axis=1)

    position_probs = np.stack([(position == k).mean(axis=0) for k in range(n_teams)], axis=1)  # teams x positions

    projections = pd.DataFrame(
        {
            "team": teams,
            "current_points": by_team["points"].to_numpy(),
            "played": by_team["played"].to_numpy(),
            "expected_points": final_pts.mean(axis=0),
            "expected_goal_diff": final_gd.mean(axis=0),
            "p_title": (position == 0).mean(axis=0),
            "p_top4": (position < TOP_N).mean(axis=0),
            "p_relegation": (position >= n_teams - RELEGATION_SPOTS).mean(axis=0),
            "expected_position": position.mean(axis=0) + 1,
            "position_probs": [row.tolist() for row in position_probs],
        }
    ).sort_values(["expected_points", "p_title"], ascending=False, ignore_index=True)

    return SeasonSimulation(
        season_start_year=season,
        n_sims=n_sims,
        matches_played=len(played),
        matches_remaining=len(fixtures),
        current_table=table,
        projections=projections,
    )
