"""Bookmaker odds from the same football-data.co.uk season files as the results.

Each file carries the pre-match odds of a dozen bookmakers (collected on
Friday afternoons for weekend games, Tuesdays for midweek ones) plus market
aggregates. We use the market *average*, the one aggregate available for
every season of the betting backtest (2013-14 onward), under two successive
names:

- 2005-06 to 2018-19: BbAv* (Betbrain average across ~40 bookmakers);
- 2019-20 onward: Avg* (football-data.co.uk's own average).

The average is a realistic price for a bettor with one or two accounts: the
best price on the market (Max*) is often from a bookmaker that limits
winning customers, and a single bookmaker's odds can be a little worse.
"""
from __future__ import annotations

import pandas as pd

from pl_predictor.data.load import TEAM_NAME_FIXES, load_raw_matches

# clean name -> raw columns, newest naming first
ODDS_COLUMNS = {
    "odds_home": ("AvgH", "BbAvH"),
    "odds_draw": ("AvgD", "BbAvD"),
    "odds_away": ("AvgA", "BbAvA"),
    "odds_over": ("Avg>2.5", "BbAv>2.5"),
    "odds_under": ("Avg<2.5", "BbAv<2.5"),
}


def match_odds(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per match: season_code, home_team, away_team and the odds
    columns of ODDS_COLUMNS (NaN when a season or match has none)."""
    out = pd.DataFrame(
        {
            "season_code": raw["season_code"],
            "home_team": raw["HomeTeam"].astype(str).str.strip().replace(TEAM_NAME_FIXES),
            "away_team": raw["AwayTeam"].astype(str).str.strip().replace(TEAM_NAME_FIXES),
        }
    )
    for name, sources in ODDS_COLUMNS.items():
        values = pd.Series(float("nan"), index=raw.index)
        for col in sources:
            if col in raw.columns:
                values = values.fillna(pd.to_numeric(raw[col], errors="coerce"))
        # decimal odds below 1.01 are data-entry errors, not prices
        out[name] = values.where(values > 1.01)
    keys = ["season_code", "home_team", "away_team"]
    return out[raw["HomeTeam"].notna()].drop_duplicates(keys).reset_index(drop=True)


def load_odds() -> pd.DataFrame:
    return match_odds(load_raw_matches())
