"""Formulas behind the panel's recommendation card. Plain Python so the panel needs only
streamlit and altair; the analysis package (metro/) uses the same band definitions.

A cell is (day_type, band). Load = boardings per trip in that cell. Trips per cell are an
assumption: the published data gives trips per month only, so they are spread over operating
hours, optionally with more service in weekday peaks and less at weekends.
"""
from __future__ import annotations

from itertools import product

Cell = tuple  # (day_type, band)

DAY_TYPES = ["weekday", "saturday", "sunday"]
BANDS = {"early": [6], "am_peak": [7, 8, 9], "midday": list(range(10, 16)),
         "pm_peak": [16, 17, 18, 19], "evening": [20, 21], "late": [22, 23]}
PEAK_BANDS = ("am_peak", "pm_peak")
CELLS = [(d, b) for d in DAY_TYPES for b in BANDS]

PEAK_GRID = (1.0, 1.25, 1.5, 1.75, 2.0)
WEEKEND_GRID = (0.6, 0.7, 0.8, 0.9, 1.0)


def band_boardings(hourly: dict) -> dict:
    """24 hourly values per day type -> boardings per day in each cell (hours 0-5 are left out)."""
    return {(d, b): float(sum(hourly[d][h] for h in hours)) for d in DAY_TYPES for b, hours in BANDS.items()}


def _weights(peak_mult: float, weekend_mult: float) -> dict:
    out = {}
    for d, (b, hours) in product(DAY_TYPES, BANDS.items()):
        w = len(hours)
        if d == "weekday" and b in PEAK_BANDS:
            w *= peak_mult
        if d != "weekday":
            w *= weekend_mult
        out[(d, b)] = w
    return out


def trips_per_cell(monthly_trips: float, days: dict, peak_mult: float = 1.0, weekend_mult: float = 1.0) -> dict:
    """Trips per day in each cell, scaled so that sum(days[d] * trips[(d, band)]) == monthly_trips."""
    w = _weights(peak_mult, weekend_mult)
    total = sum(days.get(d, 0) * v for (d, _), v in w.items())
    rate = monthly_trips / total if total > 0 else 0.0
    return {c: rate * v for c, v in w.items()}


def load_index(boardings: dict, trips: dict) -> dict:
    """Boardings per trip in each cell; 0 where a cell has no trips."""
    return {c: (boardings[c] / trips[c] if trips[c] > 0 else 0.0) for c in boardings}


def recommend(load: dict, trips: dict, add_at: float = 1.25, reduce_at: float = 0.6) -> dict:
    """'add' / 'keep' / 'reduce' relative to the line's own trip-weighted mean load."""
    total_trips = sum(trips[c] for c in load)
    if total_trips <= 0:
        return {c: "keep" for c in load}
    ref = sum(load[c] * trips[c] for c in load) / total_trips
    if ref <= 0:
        return {c: "keep" for c in load}
    return {c: "add" if v >= add_at * ref else "reduce" if v <= reduce_at * ref else "keep" for c, v in load.items()}


def labels_for(boardings: dict, monthly_trips: float, days: dict, peak_mult: float = 1.0,
               weekend_mult: float = 1.0) -> dict:
    trips = trips_per_cell(monthly_trips, days, peak_mult, weekend_mult)
    return recommend(load_index(boardings, trips), trips)


def robust(boardings: dict, monthly_trips: float, days: dict, peak_grid=PEAK_GRID, weekend_grid=WEEKEND_GRID) -> dict:
    """True for a cell whose label is the same under every combination of the two assumptions."""
    seen = {c: set() for c in boardings}
    for pm, wm in product(peak_grid, weekend_grid):
        for c, label in labels_for(boardings, monthly_trips, days, pm, wm).items():
            seen[c].add(label)
    return {c: len(s) == 1 for c, s in seen.items()}
