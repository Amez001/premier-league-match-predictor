"""Load the raw football-data.co.uk season CSVs into one clean, sorted matches table."""
from __future__ import annotations

import io
import logging
import re

import numpy as np
import pandas as pd

from pl_predictor.config import DATA_RAW_DIR, FD_DIVISION

logger = logging.getLogger(__name__)

# Columns we keep from the raw files, mapped to clean names.
# Not every season has every shot/card column (older seasons are sparser), so
# everything besides the core score/result columns is optional.
COLUMN_MAP = {
    "Date": "date",
    "HomeTeam": "home_team",
    "AwayTeam": "away_team",
    "FTHG": "home_goals",
    "FTAG": "away_goals",
    "FTR": "result",  # H / D / A
    "HS": "home_shots",
    "AS": "away_shots",
    "HST": "home_shots_target",
    "AST": "away_shots_target",
    "HC": "home_corners",
    "AC": "away_corners",
}

REQUIRED = ["date", "home_team", "away_team", "home_goals", "away_goals", "result"]

# A handful of club names changed spelling across the 25 years of files
# (or are abbreviated differently by football-data.co.uk over time).
TEAM_NAME_FIXES = {
    "Middlesboro": "Middlesbrough",
    "Nott'm Forest": "Nottm Forest",
}


def _season_code_from_filename(path) -> str:
    match = re.search(r"_(\d{4})\.csv$", str(path))
    return match.group(1) if match else "unknown"


def _parse_dates(raw: pd.Series) -> pd.Series:
    # Older files use dd/mm/yy, newer ones dd/mm/yyyy. dayfirst=True handles both;
    # pandas infers the 2-digit-year century (>=70 -> 1900s, else 2000s) which is
    # correct for our 1993-2025 range.
    return pd.to_datetime(raw, dayfirst=True, format="mixed", errors="coerce")


def _read_season_csv(path) -> pd.DataFrame:
    """Read one football-data.co.uk season file, tolerating its ragged rows.

    A number of older season files have stray trailing commas on some rows
    (extra empty betting-odds columns that don't exist in the header), which
    makes those rows "wider" than the header and breaks pandas' C parser.
    Since the columns we actually use are always the first ones (Div, Date,
    teams, score, ...), we defensively truncate/pad every row to the header's
    column count before handing the text to pandas.
    """
    try:
        raw_text = path.read_text(encoding="latin1")
    except UnicodeDecodeError:
        raw_text = path.read_text(encoding="utf-8", errors="ignore")

    lines = [line for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return pd.DataFrame()

    n_cols = len(lines[0].split(","))
    fixed_lines = [lines[0]]
    for line in lines[1:]:
        fields = line.split(",")
        if len(fields) > n_cols:
            fields = fields[:n_cols]
        elif len(fields) < n_cols:
            fields = fields + [""] * (n_cols - len(fields))
        fixed_lines.append(",".join(fields))

    return pd.read_csv(io.StringIO("\n".join(fixed_lines)))


def load_raw_matches() -> pd.DataFrame:
    """Concatenate every season CSV in data/raw into one raw (uncleaned) dataframe."""
    files = sorted(DATA_RAW_DIR.glob(f"{FD_DIVISION}_*.csv"))
    if not files:
        raise FileNotFoundError(
            f"No raw data found in {DATA_RAW_DIR}. Run `python scripts/download_data.py` first."
        )

    frames = []
    for f in files:
        try:
            df = _read_season_csv(f)
        except Exception as exc:  # noqa: BLE001 - be defensive across 25 years of file quirks
            logger.warning("could not read %s (%s), skipping", f, exc)
            continue
        df = df.dropna(how="all")
        df["season_code"] = _season_code_from_filename(f)
        frames.append(df)

    return pd.concat(frames, ignore_index=True, sort=False)


def clean_matches(raw: pd.DataFrame) -> pd.DataFrame:
    """Select/rename columns, parse dates, drop invalid rows, sort chronologically."""
    available = {src: dst for src, dst in COLUMN_MAP.items() if src in raw.columns}
    df = raw[list(available.keys()) + ["season_code"]].rename(columns=available)

    for col in REQUIRED:
        if col not in df.columns:
            raise ValueError(f"raw data is missing required column mapped to '{col}'")

    df["date"] = _parse_dates(df["date"])
    df = df.dropna(subset=["date", "home_team", "away_team", "result"])

    df["home_goals"] = pd.to_numeric(df["home_goals"], errors="coerce")
    df["away_goals"] = pd.to_numeric(df["away_goals"], errors="coerce")
    df = df.dropna(subset=["home_goals", "away_goals"])
    df["home_goals"] = df["home_goals"].astype(int)
    df["away_goals"] = df["away_goals"].astype(int)

    df["result"] = df["result"].str.strip().str.upper()
    df = df[df["result"].isin(["H", "D", "A"])]

    for col in ("home_team", "away_team"):
        df[col] = df[col].str.strip().replace(TEAM_NAME_FIXES)

    # Derive the season's start year from the football-data.co.uk season code
    # embedded in the filename (e.g. "0304" -> 2003), not from the match date:
    # seasons disrupted by fixture pile-ups (2019-20 ran into July 2020 because
    # of the COVID-19 postponement) would otherwise get their late matches
    # mislabeled into the following season by a naive "month >= 7" cutoff.
    def _start_year_from_code(code: str) -> int:
        first_two = int(code[:2])
        return 2000 + first_two if first_two <= 30 else 1900 + first_two

    df["season_start_year"] = df["season_code"].map(_start_year_from_code)

    df = df.sort_values(["date", "home_team"]).reset_index(drop=True)
    df["match_id"] = df.index

    keep = [
        "match_id",
        "date",
        "season_start_year",
        "season_code",
        "home_team",
        "away_team",
        "home_goals",
        "away_goals",
        "result",
    ] + [c for c in ("home_shots", "away_shots", "home_shots_target", "away_shots_target",
                     "home_corners", "away_corners") if c in df.columns]
    return df[keep].reset_index(drop=True)


def load_clean_matches() -> pd.DataFrame:
    """Convenience one-shot: load raw CSVs + clean them."""
    return clean_matches(load_raw_matches())


if __name__ == "__main__":
    matches = load_clean_matches()
    print(matches.shape)
    print(matches.head())
    print(matches["season_start_year"].value_counts().sort_index())
