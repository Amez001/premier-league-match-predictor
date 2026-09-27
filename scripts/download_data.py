#!/usr/bin/env python
"""CLI: download all historical Premier League season CSVs from football-data.co.uk.

Usage:
    python scripts/download_data.py
    python scripts/download_data.py --start-year 2010 --end-year 2024
    python scripts/download_data.py --force   # re-download even if files already exist
"""
import argparse
import logging

from pl_predictor.config import DATA_RAW_DIR, DEFAULT_END_YEAR, DEFAULT_START_YEAR
from pl_predictor.data.download import download_all


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    saved = download_all(start_year=args.start_year, end_year=args.end_year, force=args.force)
    print(f"\nDownloaded/verified {len(saved)} season(s) into {DATA_RAW_DIR}")
    if not saved:
        print("No files saved - check your internet connection or try a narrower --start-year/--end-year range.")


if __name__ == "__main__":
    main()
