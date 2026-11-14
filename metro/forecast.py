"""Forecast = a unit's typical recent profile x a special-day factor.

Leakage rule: everything here takes a cut-off date and uses only rows strictly
before it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from metro.groups import OUTLIER

KEYS = ["line", "station"]
DAY_TYPES = ["weekday", "saturday", "sunday"]
SPECIALS = ["none", "public_holiday", "religious_holiday", "school_break"]
BANDS = {"early": [6], "am_peak": [7, 8, 9], "midday": list(range(10, 16)),
         "pm_peak": [16, 17, 18, 19], "evening": [20, 21], "late": [22, 23]}
HOUR_TO_BAND = {h: b for b, hs in BANDS.items() for h in hs}
BASELINE_DAYS = 28
# A normal day whose boardings fall below this share of the unit's median for that day type
# (computed only from earlier days) is treated as a closed-station day and left out of the
# profile and the special-day baseline. Real example: 1 May 2024 at Taksim, Sishane, Kabatas.
CLOSED_THRESHOLD = 0.2


def predictable_units(groups: pd.Series) -> pd.Index:
    """Units that get factors and forecasts: grouped and not event-driven."""
    return groups[groups != OUTLIER].index


def _with_calendar(df: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    return df.merge(calendar[["date", "day_type", "special"]], on="date", how="left")


def _span_matrix(hourly: pd.DataFrame, before) -> pd.DataFrame:
    """Units x dates before `before`: daily boardings, 0 on days inside a unit's first..last
    date with no rows (closed), NaN outside that span (not opened yet / gone)."""
    h = hourly[hourly["date"] < pd.Timestamp(before)]
    dates = sorted(h["date"].unique())
    m = h.groupby(KEYS + ["date"])["boardings"].sum().unstack("date").reindex(columns=dates)
    first = h.groupby(KEYS)["date"].min().reindex(m.index)
    last = h.groupby(KEYS)["date"].max().reindex(m.index)
    cols = pd.DatetimeIndex(dates).to_numpy()
    inside = (cols[None, :] >= first.to_numpy()[:, None]) & (cols[None, :] <= last.to_numpy()[:, None])
    return m.fillna(0.0).where(inside)


def closed_days(hourly: pd.DataFrame, calendar: pd.DataFrame, before, threshold: float = CLOSED_THRESHOLD) -> pd.DataFrame:
    """Normal days before `before` on which a unit had fewer than threshold x its median daily
    boardings for that day type (median over the unit's normal days before `before`)."""
    m = _span_matrix(hourly, before)
    cal = calendar.set_index("date").reindex(m.columns)
    out = []
    for dt in DAY_TYPES:
        cols = m.columns[((cal["special"] == "none") & (cal["day_type"] == dt)).to_numpy()]
        if len(cols) == 0:
            continue
        sub = m[cols]
        med = sub.median(axis=1, skipna=True)
        low = sub.lt(threshold * med, axis=0) & sub.notna() & (med > 0).to_numpy()[:, None]
        s = low.stack()
        out.append(s[s].reset_index()[KEYS + ["date"]])
    if not out:
        return pd.DataFrame({"line": pd.Series(dtype=str), "station": pd.Series(dtype=str),
                             "date": pd.Series(dtype="datetime64[ns]")})
    return pd.concat(out).sort_values(KEYS + ["date"]).reset_index(drop=True)


def typical_profile(hourly: pd.DataFrame, calendar: pd.DataFrame, as_of, n_weeks: int = 8,
                    closed_threshold: float | None = CLOSED_THRESHOLD) -> pd.DataFrame:
    """Mean boardings per day by unit, day type and hour over the normal days in the
    n_weeks*7 days strictly before as_of, leaving out closed-station days when
    closed_threshold is set. Every unit gets all 72 rows (0 where absent)."""
    as_of = pd.Timestamp(as_of)
    lo = as_of - pd.Timedelta(days=7 * n_weeks)
    units = hourly.loc[hourly["date"] < as_of, KEYS].drop_duplicates()
    win = _with_calendar(hourly[(hourly["date"] >= lo) & (hourly["date"] < as_of)], calendar)
    win = win[win["special"] == "none"]
    n_days = win.groupby("day_type")["date"].nunique()
    if closed_threshold is not None:
        cd = closed_days(hourly, calendar, as_of, closed_threshold)
        cd = _with_calendar(cd[cd["date"] >= lo], calendar)
        drop = pd.MultiIndex.from_frame(cd[KEYS + ["date"]])
        win = win[~pd.MultiIndex.from_frame(win[KEYS + ["date"]]).isin(drop)]
        n_closed = cd.groupby(KEYS + ["day_type"]).size().rename("n_closed")
    else:
        n_closed = pd.Series(dtype=float, name="n_closed")
    sums = win.groupby(KEYS + ["day_type", "hour"])["boardings"].sum().reset_index()
    sums = sums.merge(n_closed.reset_index(), on=KEYS + ["day_type"], how="left") if len(n_closed) else sums.assign(n_closed=0)
    divisor = sums["day_type"].map(n_days) - sums["n_closed"].fillna(0)
    sums["boardings"] = sums["boardings"] / divisor
    sums = sums.drop(columns="n_closed")
    grid = units.merge(pd.DataFrame({"day_type": DAY_TYPES}), how="cross").merge(
        pd.DataFrame({"hour": range(24)}), how="cross")
    out = grid.merge(sums, on=KEYS + ["day_type", "hour"], how="left")
    out["boardings"] = out["boardings"].fillna(0.0).astype(float)
    return out.sort_values(KEYS + ["day_type", "hour"]).reset_index(drop=True)


def _daily_matrix(hourly: pd.DataFrame, units: pd.Index, before) -> pd.DataFrame:
    """Units x dates (dates with data before `before`), daily boardings, 0 where absent."""
    h = hourly[hourly["date"] < pd.Timestamp(before)]
    daily = h.groupby(KEYS + ["date"])["boardings"].sum()
    m = daily.unstack("date").reindex(units).fillna(0.0)
    return m.reindex(columns=sorted(h["date"].unique()), fill_value=0.0)


def _ratios(hourly, calendar, groups, before, closed_threshold=CLOSED_THRESHOLD):
    """Per special day before `before`: actual and baseline daily boardings per unit."""
    units = predictable_units(groups)
    m = _daily_matrix(hourly, units, before)
    if closed_threshold is not None:
        cd = closed_days(hourly, calendar, before, closed_threshold)
        for (line, station), d in cd.groupby(KEYS)["date"]:
            if (line, station) in m.index:
                m.loc[(line, station), list(d)] = np.nan
    cal = calendar.set_index("date").reindex(m.columns)
    rows = []
    for d in m.columns[cal["special"].to_numpy() != "none"]:
        same = (cal["special"] == "none") & (cal["day_type"] == cal.at[d, "day_type"])
        win = same & (cal.index >= d - pd.Timedelta(days=BASELINE_DAYS)) & (cal.index < d)
        base = m.loc[:, win.to_numpy()].mean(axis=1, skipna=True) if win.any() else pd.Series(np.nan, index=m.index)
        rows.append(pd.DataFrame({"date": d, "special": cal.at[d, "special"], "actual": m[d], "baseline": base}))
    if not rows:
        return pd.DataFrame(columns=KEYS + ["date", "special", "actual", "baseline"])
    return pd.concat(rows).rename_axis(KEYS).reset_index()


def special_factors(hourly, calendar, groups: pd.Series, before, level: str,
                    closed_threshold: float | None = CLOSED_THRESHOLD) -> pd.DataFrame:
    """Factor per predictable unit and special category; see the plan for the definition.
    Missing, zero-baseline or non-finite cases give 1.0."""
    if level not in {"none", "station", "group"}:
        raise ValueError(f"unknown level {level!r}")
    units = predictable_units(groups)
    grid = pd.DataFrame(list(units), columns=KEYS).merge(pd.DataFrame({"special": SPECIALS}), how="cross")
    grid["factor"] = 1.0
    if level == "none":
        return grid
    r = _ratios(hourly, calendar, groups, before, closed_threshold)
    if level == "station":
        ok = r[r["baseline"] > 0]
        f = (ok["actual"] / ok["baseline"]).groupby([ok["line"], ok["station"], ok["special"]]).median()
        f = f.rename("f").reset_index()
    else:
        r = r.dropna(subset=["baseline"])
        r["group"] = [groups[(l, s)] for l, s in zip(r["line"], r["station"])]
        g = r.groupby(["group", "date", "special"])[["actual", "baseline"]].sum().reset_index()
        g = g[g["baseline"] > 0]
        g["ratio"] = g["actual"] / g["baseline"]
        gf = g.groupby(["group", "special"])["ratio"].median().rename("f").reset_index()
        u = pd.DataFrame(list(units), columns=KEYS)
        u["group"] = [groups[k] for k in units]
        f = u.merge(gf, on="group")[KEYS + ["special", "f"]]
    out = grid.merge(f, on=KEYS + ["special"], how="left")
    out["f"] = pd.to_numeric(out["f"], errors="coerce")  # no special days before the cut -> empty, untyped
    out["factor"] = out["f"].where(np.isfinite(out["f"]) & (out["special"] != "none"), 1.0)
    return out[KEYS + ["special", "factor"]]


def forecast(profile: pd.DataFrame, factors: pd.DataFrame, future_calendar: pd.DataFrame) -> pd.DataFrame:
    """Hourly forecast per unit for every date in future_calendar."""
    days = future_calendar[["date", "day_type", "special"]]
    out = days.merge(profile, on="day_type").merge(
        factors[KEYS + ["special", "factor"]], on=KEYS + ["special"], how="left")
    out["boardings"] = out["boardings"] * out["factor"].astype(float).fillna(1.0)
    return out[["date"] + KEYS + ["hour", "boardings"]].sort_values(["date"] + KEYS + ["hour"]).reset_index(drop=True)


def mape(actual: pd.Series, predicted: pd.Series) -> float:
    """Mean of |a - p| / a over rows with a > 0."""
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    ok = a > 0
    return float(np.mean(np.abs(a[ok] - p[ok]) / a[ok])) if ok.any() else float("nan")


def wape(actual: pd.Series, predicted: pd.Series) -> float:
    """Boardings-weighted error: sum |a - p| / sum a. A near-empty day (station closed) counts
    in proportion to its boardings instead of dominating the average."""
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    total = a.sum()
    return float(np.abs(a - p).sum() / total) if total > 0 else float("nan")
