"""Load and validate the hand-maintained special-day calendar."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "calendar.csv"
DAY_TYPES = {"weekday", "saturday", "sunday"}
SPECIALS = {"none", "public_holiday", "religious_holiday", "school_break"}


def load_calendar(path: Path = DEFAULT_PATH) -> pd.DataFrame:
    """Columns: date (datetime64), day_type, special, label."""
    cal = pd.read_csv(path, parse_dates=["date"], keep_default_na=False)
    for col, allowed in (("day_type", DAY_TYPES), ("special", SPECIALS)):
        bad = set(cal[col]) - allowed
        if bad:
            raise ValueError(f"calendar column '{col}' has unknown values: {sorted(bad)}")
    return cal.sort_values("date").reset_index(drop=True)
