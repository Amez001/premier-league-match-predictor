"""Baseline feature engineering: rolling form, goals, and season-table position.

Every feature here is computed as a single chronological pass over the matches,
using only information strictly before the match being featurized - so, just
like elo.compute_running_elo, the resulting columns are leakage-safe no matter
how you later slice the data by date for train/test.
"""
from __future__ import annotations

from collections import defaultdict, deque

import numpy as np
import pandas as pd

FORM_WINDOW = 5


def _points(goals_for: int, goals_against: int) -> int:
    if goals_for > goals_against:
        return 3
    if goals_for == goals_against:
        return 1
    return 0


class _TeamState:
    """Rolling match history for one team, used to derive form features."""

    def __init__(self, window: int = FORM_WINDOW):
        self.all_results: deque = deque(maxlen=window)  # (points, gf, ga) any venue
        self.venue_results: dict[str, deque] = {
            "home": deque(maxlen=window),
            "away": deque(maxlen=window),
        }

    def features(self, venue: str) -> dict:
        n = len(self.all_results)
        if n == 0:
            form_points, gf_avg, ga_avg = 1.0, 1.0, 1.0  # neutral prior for a team's first match
        else:
            form_points = sum(p for p, _, _ in self.all_results) / n
            gf_avg = sum(g for _, g, _ in self.all_results) / n
            ga_avg = sum(g for _, _, g in self.all_results) / n

        venue_hist = self.venue_results[venue]
        vn = len(venue_hist)
        if vn == 0:
            venue_form_points = form_points
        else:
            venue_form_points = sum(p for p, _, _ in venue_hist) / vn

        return {
            "form_points_avg": form_points,
            "form_goals_for_avg": gf_avg,
            "form_goals_against_avg": ga_avg,
            "form_venue_points_avg": venue_form_points,
        }

    def update(self, venue: str, goals_for: int, goals_against: int):
        pts = _points(goals_for, goals_against)
        self.all_results.append((pts, goals_for, goals_against))
        self.venue_results[venue].append((pts, goals_for, goals_against))


class _SeasonTable:
    """Season-to-date league table, used for a lightweight position/points-per-game feature."""

    def __init__(self):
        self.played = defaultdict(int)
        self.points = defaultdict(int)
        self.goal_diff = defaultdict(int)

    def features(self, team: str) -> dict:
        played = self.played[team]
        ppg = self.points[team] / played if played else 1.0  # neutral prior
        gd_pg = self.goal_diff[team] / played if played else 0.0

        # Rank among teams that have played at least one match this season so far.
        active_teams = [t for t, p in self.played.items() if p > 0]
        if team in active_teams and len(active_teams) > 1:
            ranked = sorted(active_teams, key=lambda t: (self.points[t], self.goal_diff[t]), reverse=True)
            rank = ranked.index(team) + 1
        else:
            rank = (len(active_teams) + 1) / 2 or 10  # mid-table prior when no history yet

        return {"season_points_per_game": ppg, "season_goal_diff_per_game": gd_pg, "season_rank": rank}

    def update(self, team: str, goals_for: int, goals_against: int):
        self.played[team] += 1
        self.points[team] += _points(goals_for, goals_against)
        self.goal_diff[team] += goals_for - goals_against


def add_form_features(matches: pd.DataFrame, window: int = FORM_WINDOW) -> pd.DataFrame:
    """Add rolling form + season-table features for both home and away teams."""
    matches = matches.sort_values(["date", "match_id"]).reset_index(drop=True)

    team_states: dict[str, _TeamState] = defaultdict(lambda: _TeamState(window))
    season_tables: dict[int, _SeasonTable] = defaultdict(_SeasonTable)

    rows = []
    for row in matches.itertuples(index=False):
        season = row.season_start_year
        table = season_tables[season]

        home_feat = {f"home_{k}": v for k, v in team_states[row.home_team].features("home").items()}
        away_feat = {f"away_{k}": v for k, v in team_states[row.away_team].features("away").items()}
        home_table_feat = {f"home_{k}": v for k, v in table.features(row.home_team).items()}
        away_table_feat = {f"away_{k}": v for k, v in table.features(row.away_team).items()}

        rows.append({**home_feat, **away_feat, **home_table_feat, **away_table_feat})

        team_states[row.home_team].update("home", row.home_goals, row.away_goals)
        team_states[row.away_team].update("away", row.away_goals, row.home_goals)
        table.update(row.home_team, row.home_goals, row.away_goals)
        table.update(row.away_team, row.away_goals, row.home_goals)

    feat_df = pd.DataFrame(rows)
    out = pd.concat([matches.reset_index(drop=True), feat_df], axis=1)

    out["form_points_diff"] = out["home_form_points_avg"] - out["away_form_points_avg"]
    out["form_goal_diff_diff"] = (
        out["home_form_goals_for_avg"] - out["home_form_goals_against_avg"]
    ) - (out["away_form_goals_for_avg"] - out["away_form_goals_against_avg"])
    out["season_rank_diff"] = out["away_season_rank"] - out["home_season_rank"]  # positive favors home
    out["season_ppg_diff"] = out["home_season_points_per_game"] - out["away_season_points_per_game"]

    return out


BASELINE_FEATURE_COLUMNS = [
    "elo_diff",
    "form_points_diff",
    "form_goal_diff_diff",
    "season_rank_diff",
    "season_ppg_diff",
    "home_form_venue_points_avg",
    "away_form_venue_points_avg",
]


def build_feature_table(matches: pd.DataFrame, elo_kwargs: dict | None = None) -> pd.DataFrame:
    """Full pipeline: raw clean matches -> matches with Elo + form features attached."""
    from pl_predictor.features.elo import compute_running_elo

    with_elo, _elo = compute_running_elo(matches, **(elo_kwargs or {}))
    with_form = add_form_features(with_elo)
    return with_form
