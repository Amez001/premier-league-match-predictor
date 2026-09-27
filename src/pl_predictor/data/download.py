"""Download historical Premier League match data from football-data.co.uk.

Each season is a single CSV (e.g. https://www.football-data.co.uk/mmz4281/2324/E0.csv)
with one row per match: date, teams, full/half-time score, shots, cards, referee,
and bookmaker odds. No API key required.
"""
from __future__ import annotations

import logging
import time

import requests

from pl_predictor.config import (
    DATA_RAW_DIR,
    DEFAULT_END_YEAR,
    DEFAULT_START_YEAR,
    FD_BASE_URL,
    FD_DIVISION,
    season_code,
)

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (premier-league-match-predictor)"}


def download_season(start_year: int, force: bool = False, timeout: int = 20) -> bool:
    """Download one season's CSV. Returns True if the file is present after the call."""
    code = season_code(start_year)
    dest = DATA_RAW_DIR / f"{FD_DIVISION}_{code}.csv"
    if dest.exists() and not force:
        logger.info("season %s already downloaded, skipping", code)
        return True

    url = f"{FD_BASE_URL}/{code}/{FD_DIVISION}.csv"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("failed to download season %s from %s: %s", code, url, exc)
        return False

    if len(resp.content) < 200:
        # football-data.co.uk returns a tiny/empty body for seasons that don't exist yet.
        logger.warning("season %s looks empty (%d bytes), not saving", code, len(resp.content))
        return False

    dest.write_bytes(resp.content)
    logger.info("saved %s (%d bytes)", dest.name, len(resp.content))
    return True


def download_all(
    start_year: int = DEFAULT_START_YEAR,
    end_year: int = DEFAULT_END_YEAR,
    force: bool = False,
    pause_seconds: float = 0.5,
) -> list[str]:
    """Download every season in [start_year, end_year]. Returns the list of season codes saved."""
    saved = []
    for year in range(start_year, end_year + 1):
        if download_season(year, force=force):
            saved.append(season_code(year))
        time.sleep(pause_seconds)
    return saved


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    downloaded = download_all()
    print(f"Downloaded {len(downloaded)} seasons into {DATA_RAW_DIR}")
