"""A from-scratch Elo rating system for football teams.

Standard chess-style Elo, adapted for football with:
  - a home-advantage bonus added to the home team's rating before computing
    the expected score (teams are simply stronger at home on average), and
  - an optional margin-of-victory multiplier so a 4-0 moves ratings more than
    a 1-0 (the "World Football Elo" approach), which helps distinguish
    "scraped past them" from "thrashed them" - both are wins, but they carry
    different information about relative strength.

Update rule, applied after every match:
    E_home = 1 / (1 + 10 ** (-(elo_home + home_advantage - elo_away) / 400))
    Elo_home_new = Elo_home_old + K * multiplier * (S_home - E_home)
    Elo_away_new = Elo_away_old + K * multiplier * (S_away - E_away)
where S_home in {1, 0.5, 0} is the match result from the home team's
perspective and E_away = 1 - E_home, S_away = 1 - S_home.
"""
from __future__ import annotations

import math
from collections import defaultdict

import pandas as pd

DEFAULT_INITIAL_RATING = 1500.0


class EloRatings:
    def __init__(
        self,
        k: float = 20.0,
        home_advantage: float = 60.0,
        initial_rating: float = DEFAULT_INITIAL_RATING,
        use_margin_multiplier: bool = True,
    ):
        self.k = k
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.use_margin_multiplier = use_margin_multiplier
        self.ratings: dict[str, float] = defaultdict(lambda: initial_rating)

    def get(self, team: str) -> float:
        return self.ratings[team]

    def expected_home_score(self, home: str, away: str) -> float:
        diff = (self.ratings[home] + self.home_advantage) - self.ratings[away]
        return 1.0 / (1.0 + 10 ** (-diff / 400.0))

    @staticmethod
    def _result_score(home_goals: int, away_goals: int) -> float:
        if home_goals > away_goals:
            return 1.0
        if home_goals < away_goals:
            return 0.0
        return 0.5

    def _margin_multiplier(self, home_goals: int, away_goals: int, pre_diff: float) -> float:
        if not self.use_margin_multiplier:
            return 1.0
        margin = abs(home_goals - away_goals)
        if margin == 0:
            return 1.0
        # Damped so a big rating gap winning big doesn't get an inflated boost
        # (a strong team beating a weak one 4-0 is expected, not surprising).
        return math.log(margin + 1) * (2.2 / (abs(pre_diff) * 0.001 + 2.2))

    def update(self, home: str, away: str, home_goals: int, away_goals: int) -> tuple[float, float]:
        """Apply one match result. Returns (elo_home_pre, elo_away_pre)."""
        elo_home_pre = self.ratings[home]
        elo_away_pre = self.ratings[away]

        expected_home = self.expected_home_score(home, away)
        actual_home = self._result_score(home_goals, away_goals)
        multiplier = self._margin_multiplier(home_goals, away_goals, elo_home_pre - elo_away_pre)

        delta = self.k * multiplier * (actual_home - expected_home)
        self.ratings[home] = elo_home_pre + delta
        self.ratings[away] = elo_away_pre - delta

        return elo_home_pre, elo_away_pre

    def as_table(self) -> pd.DataFrame:
        return (
            pd.DataFrame({"team": list(self.ratings.keys()), "elo": list(self.ratings.values())})
            .sort_values("elo", ascending=False)
            .reset_index(drop=True)
        )


def compute_running_elo(matches: pd.DataFrame, **elo_kwargs) -> pd.DataFrame:
    """Replay every match chronologically, returning matches + pre-match Elo columns.

    Crucial for avoiding leakage: elo_home_pre/elo_away_pre for a given match
    only reflect results from strictly earlier matches, so these columns are
    safe to use as training features regardless of how you later split by date.
    """
    matches = matches.sort_values(["date", "match_id"]).reset_index(drop=True)
    elo = EloRatings(**elo_kwargs)

    home_pre, away_pre = [], []
    for row in matches.itertuples(index=False):
        h_pre, a_pre = elo.update(row.home_team, row.away_team, row.home_goals, row.away_goals)
        home_pre.append(h_pre)
        away_pre.append(a_pre)

    out = matches.copy()
    out["elo_home_pre"] = home_pre
    out["elo_away_pre"] = away_pre
    out["elo_diff"] = out["elo_home_pre"] - out["elo_away_pre"]
    return out, elo
