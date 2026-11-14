"""Synthetic hourly frames and calendars for tests."""
import pandas as pd

COLS = ["date", "hour", "line", "station", "boardings", "passengers", "b_full", "b_discount", "b_free", "b_transfer"]


def calendar(start="2023-01-01", end="2024-07-31", public_holidays=()):
    cal = pd.DataFrame({"date": pd.date_range(start, end, freq="D")})
    dow = cal.date.dt.day_of_week
    cal["day_type"] = dow.map(lambda d: "saturday" if d == 5 else "sunday" if d == 6 else "weekday")
    cal["special"] = "none"
    cal.loc[cal.date.isin(pd.to_datetime(list(public_holidays))), "special"] = "public_holiday"
    cal["label"] = ""
    return cal


def hourly(cal, line, station, weekday=None, weekend=None, start=None, end=None, discount=0.0, transfer=0.0):
    """weekday/weekend: dict hour -> boardings per day. Rows for every date in cal (or start..end)."""
    rows = []
    days = cal
    if start is not None:
        days = days[days.date >= pd.Timestamp(start)]
    if end is not None:
        days = days[days.date <= pd.Timestamp(end)]
    for d, dt in zip(days.date, days.day_type):
        prof = (weekday if dt == "weekday" else weekend) or {}
        for h, b in prof.items():
            rows.append((d, h, line, station, b, b, b * (1 - discount), b * discount, 0, b * transfer))
    return pd.DataFrame(rows, columns=COLS)
