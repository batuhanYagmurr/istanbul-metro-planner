"""Text and small calculations for the panel, kept out of streamlit_app.py so they can be tested."""
from __future__ import annotations

import altair as alt
import pandas as pd

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

TRIPS_AXIS_TITLE = "Assumed trips per hour"
TOP_STATIONS = 20

# Solid cells (robust): tinted fill, dark text. Faded cells (depend on the assumptions): no fill, dashed
# border, text in the page's own colour, so they read clearly in light and dark themes. No opacity:
# it would fade the text too.
CARD_CSS = """<style>
table.card{border-collapse:separate;border-spacing:4px;width:100%}
table.card th{font-size:12px;font-weight:600;text-align:left;padding:2px 4px}
table.card td{border-radius:6px;padding:6px 8px;font-size:13px;vertical-align:top;height:58px}
table.card td span{font-size:11px;display:block;margin-top:2px}
table.card td.high{background:#fff1e5;color:#8a4500;border:2px solid #b35900}
table.card td.low{background:#e6f4fa;color:#0a5878;border:2px solid #0b6e99}
table.card td.typ{background:#eef0f2;color:#3d444d;border:2px solid #8c959f}
table.card td.weak{background:transparent;color:inherit;border-style:dashed}
</style>"""


def top_stations(line: dict, n: int = TOP_STATIONS) -> list[dict]:
    """The line's n busiest station units, busiest first, with a group name for every one."""
    rows = sorted(line["stations"], key=lambda s: s["boardings_day"], reverse=True)[:n]
    return [{**s, "group": s["group"] or "Too new to group"} for s in rows]


def monthly_trend_chart(line: dict) -> alt.Chart:
    """Boardings per trip by month (boardings per day for lines without trip data), one axis label per month."""
    mo = pd.DataFrame(line["monthly"])
    if line["has_trips"]:
        mo = mo.dropna(subset=["trips"]).assign(value=lambda d: d["boardings"] / d["trips"])
        ytitle = "Boardings per trip"
    else:
        mo = mo.assign(value=lambda d: d["boardings"] / pd.to_datetime(d["month"]).dt.days_in_month)
        ytitle = "Boardings per day (no trip data published)"
    # local-time timestamps (no "Z") so the points sit exactly on the local month-start ticks
    mo = mo.assign(month=mo["month"] + "-01T00:00:00")[["month", "value"]]
    ticks = [alt.DateTime(year=int(m[:4]), month=int(m[5:7]), date=1) for m in mo["month"]]
    return alt.Chart(mo).mark_line(point=True).encode(
        x=alt.X("month:T", title=None,
                axis=alt.Axis(values=ticks, format="%b %Y", labelOverlap=False, labelAngle=-45, grid=False)),
        y=alt.Y("value:Q", title=ytitle, scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("month:T", title="Month", format="%b %Y"),
                 alt.Tooltip("value:Q", title=ytitle, format=",.0f")])
