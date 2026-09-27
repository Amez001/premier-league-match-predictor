"""Optional: fetch upcoming Premier League fixtures for the live dashboard.

Wraps https://github.com/tarun7r/Premier-League-API (an unofficial client around
the official PL website's data endpoints). This is only used to populate the
"upcoming fixtures" dropdown in the dashboard with real, current matches -
all training/backtesting uses the football-data.co.uk historical CSVs instead,
since this API does not offer a full historical archive.

The wrapped project is a Python package you install separately:
    pip install git+https://github.com/tarun7r/Premier-League-API

If it isn't installed, everything here degrades gracefully (the dashboard falls
back to letting the user pick any two teams from the historical data instead).
"""
from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


def is_available() -> bool:
    try:
        import premier_league  # noqa: F401
        return True
    except ImportError:
        return False


def get_upcoming_fixtures(limit: int = 20) -> pd.DataFrame:
    """Return a dataframe [date, home_team, away_team] of upcoming PL fixtures.

    Returns an empty dataframe (never raises) if the optional dependency isn't
    installed or the upstream site can't be reached - callers should treat
    that as "no live fixtures available" and fall back to manual team pickers.
    """
    empty = pd.DataFrame(columns=["date", "home_team", "away_team"])
    try:
        from premier_league import Fixtures
    except ImportError:
        logger.info("premier_league package not installed; skipping live fixtures")
        return empty

    try:
        fixtures = Fixtures().get_fixtures()
    except Exception as exc:  # noqa: BLE001 - third-party client, be defensive
        logger.warning("could not fetch live fixtures: %s", exc)
        return empty

    rows = []
    for fx in fixtures[:limit]:
        try:
            rows.append(
                {
                    "date": fx.get("date") or fx.get("kickoff") or datetime.now().isoformat(),
                    "home_team": fx.get("home_team") or fx.get("homeTeam"),
                    "away_team": fx.get("away_team") or fx.get("awayTeam"),
                }
            )
        except AttributeError:
            continue

    return pd.DataFrame(rows) if rows else empty
