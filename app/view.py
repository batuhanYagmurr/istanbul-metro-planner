"""Text and small calculations for the panel, kept out of streamlit_app.py so they can be tested."""
from __future__ import annotations

import model

CELL_TEXT = {"add": "Load per trip high in this band",
             "reduce": "Load per trip low in this band",
             "keep": "Near the line's average"}
CELL_CLASS = {"add": "high", "reduce": "low", "keep": "typ"}
DAY_NAMES = {"weekday": "Weekday", "saturday": "Saturday", "sunday": "Sunday"}
BAND_NAMES = {"early": "06", "am_peak": "07–09", "midday": "10–15", "pm_peak": "16–19", "evening": "20–21", "late": "22–23"}


def error_label(data: dict) -> str:
    """The headline forecast error, formatted the same way everywhere (panel and README)."""
    return f'{data["meta"]["backtest"]["station_day_wape"] * 100:.1f}%'


def august_over_forecast(data: dict) -> tuple[float, int]:
    """How far the network forecast ran above the actual on the complete August 2024 days."""
    days = [r for r in data["meta"]["backtest"]["complete_days"] if r["date"].startswith("2024-08")]
    if not days:
        return 0.0, 0
    return sum(r["forecast"] for r in days) / sum(r["actual"] for r in days) - 1, len(days)


def _month(line: dict, month: str):
    return next((r for r in line["monthly"] if r["month"] == month), None)


def _change(new: float, old: float) -> str:
    x = new / old - 1
    if abs(x) < 0.005:
        return "about the same as"
    return f"{abs(x) * 100:.0f}% {'more' if x > 0 else 'fewer'} than"


def summary_sentence(name: str, line: dict) -> str:
    """One measured finding for the line: July 2024 against July 2023."""
    now, before = _month(line, "2024-07"), _month(line, "2023-07")
    if line["has_trips"] and now and now["trips"]:
        bpt = now["boardings"] / now["trips"]
        s = f"In July 2024 {name} carried {bpt:,.0f} boardings per trip"
        if before and before["trips"]:
            old = before["boardings"] / before["trips"]
            return s + f", {_change(bpt, old)} in July 2023 ({old:,.0f})."
        return s + " (no July 2023 figure to compare)."
    if now:
        per_day = now["boardings"] / 31
        s = f"In July 2024 {name} had {per_day:,.0f} boardings per day"
        if before:
            return s + f", {_change(per_day, before['boardings'] / 31)} in July 2023."
        return s + " (no July 2023 figure to compare)."
    return f"No complete July 2024 data for {name}."


def assumed_trips_per_hour(line: dict, peak_mult: float, weekend_mult: float, day_type: str) -> list[float]:
    """The assumed trips in each hour of one day type (0 outside operating hours)."""
    t = model.trips_per_cell(line["trips_month"], line["days"], peak_mult, weekend_mult)
    out = [0.0] * 24
    for band, hours in model.BANDS.items():
        for h in hours:
            out[h] = t[(day_type, band)] / len(hours)
    return out
