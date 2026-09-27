"""Central configuration: paths and constants shared across the project."""
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_RAW_DIR = ROOT_DIR / "data" / "raw"
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
REPORTS_DIR = ROOT_DIR / "reports"
ARTIFACTS_DIR = ROOT_DIR / "models_artifacts"

for _d in (DATA_RAW_DIR, DATA_PROCESSED_DIR, REPORTS_DIR, ARTIFACTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# football-data.co.uk division code for the Premier League
FD_DIVISION = "E0"
FD_BASE_URL = "https://www.football-data.co.uk/mmz4281"

# Default range of seasons to download/train on. "2000" means the 2000-01 season.
DEFAULT_START_YEAR = 2000
DEFAULT_END_YEAR = 2025  # 2025-26 season

# Outcome label encoding used everywhere in the project.
# Kept in this order so probability arrays are always [Home, Draw, Away].
OUTCOME_LABELS = ["H", "D", "A"]
OUTCOME_NAMES = {"H": "Home win", "D": "Draw", "A": "Away win"}
OUTCOME_TO_IDX = {label: i for i, label in enumerate(OUTCOME_LABELS)}

# First season used as a test season in the walk-forward backtest.
# Everything before it is used purely as training history.
DEFAULT_FIRST_TEST_SEASON_START_YEAR = 2013


def season_code(start_year: int) -> str:
    """2000 -> '0001' (the football-data.co.uk season code for 2000-01)."""
    y1 = start_year % 100
    y2 = (start_year + 1) % 100
    return f"{y1:02d}{y2:02d}"


def season_label(start_year: int) -> str:
    """2000 -> '2000-01' (human readable season label)."""
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def season_codes(start_year: int = DEFAULT_START_YEAR, end_year: int = DEFAULT_END_YEAR):
    return [season_code(y) for y in range(start_year, end_year + 1)]
