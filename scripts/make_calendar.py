"""Write data/calendar.csv: one row per day with day type and special-day category.

Dates were looked up, not computed; sources are listed in docs/data-notes.md.
Priority when a day qualifies for several: religious > public > school_break.
School breaks mark weekdays only.
"""
from pathlib import Path

import pandas as pd

START, END = "2023-01-01", "2024-12-31"

PUBLIC = {"01-01": "New Year's Day", "04-23": "National Sovereignty and Children's Day",
          "05-01": "Labour Day", "05-19": "Youth and Sports Day", "07-15": "Democracy and National Unity Day",
          "08-30": "Victory Day", "10-29": "Republic Day"}

RELIGIOUS = {  # eve is an official half-day
    "2023-04-20": "Ramazan Bayramı eve (half day)", "2023-04-21": "Ramazan Bayramı day 1",
    "2023-04-22": "Ramazan Bayramı day 2", "2023-04-23": "Ramazan Bayramı day 3",
    "2023-06-27": "Kurban Bayramı eve (half day)", "2023-06-28": "Kurban Bayramı day 1",
    "2023-06-29": "Kurban Bayramı day 2", "2023-06-30": "Kurban Bayramı day 3", "2023-07-01": "Kurban Bayramı day 4",
    "2024-04-09": "Ramazan Bayramı eve (half day)", "2024-04-10": "Ramazan Bayramı day 1",
    "2024-04-11": "Ramazan Bayramı day 2", "2024-04-12": "Ramazan Bayramı day 3",
    "2024-06-15": "Kurban Bayramı eve (half day)", "2024-06-16": "Kurban Bayramı day 1",
    "2024-06-17": "Kurban Bayramı day 2", "2024-06-18": "Kurban Bayramı day 3", "2024-06-19": "Kurban Bayramı day 4",
}

SCHOOL_BREAKS = [  # inclusive ranges, MEB calendars
    ("2023-01-23", "2023-02-17", "Semester break (extended to 20 Feb after the earthquake)"),
    ("2023-04-17", "2023-04-20", "Second-term mid-term break"),
    ("2023-06-19", "2023-09-08", "Summer break"),
    ("2023-11-13", "2023-11-17", "First-term mid-term break"),
    ("2024-01-22", "2024-02-02", "Semester break"),
    ("2024-04-08", "2024-04-12", "Second-term mid-term break"),
    ("2024-06-17", "2024-09-06", "Summer break"),
    ("2024-11-11", "2024-11-15", "First-term mid-term break"),
]


def build() -> pd.DataFrame:
    cal = pd.DataFrame({"date": pd.date_range(START, END, freq="D")})
    dow = cal.date.dt.day_of_week
    cal["day_type"] = dow.map(lambda d: "saturday" if d == 5 else "sunday" if d == 6 else "weekday")
    cal["special"], cal["label"] = "none", ""
    for a, b, label in SCHOOL_BREAKS:
        m = cal.date.between(a, b) & (cal.day_type == "weekday")
        cal.loc[m, ["special", "label"]] = ["school_break", label]
    for md, label in PUBLIC.items():
        m = cal.date.dt.strftime("%m-%d") == md
        cal.loc[m, ["special", "label"]] = ["public_holiday", label]
    for day, label in RELIGIOUS.items():
        cal.loc[cal.date == day, ["special", "label"]] = ["religious_holiday", label]
    return cal


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "data" / "calendar.csv"
    build().to_csv(out, index=False, date_format="%Y-%m-%d")
    print(f"wrote {out}")
