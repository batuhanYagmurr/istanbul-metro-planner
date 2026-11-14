"""Backtests. Profiles, factors and (with regroup=True) groups always come from data strictly
before the first scored day."""
from __future__ import annotations

import pandas as pd

from metro.features import station_features
from metro.forecast import (CLOSED_THRESHOLD, HOUR_TO_BAND, KEYS, forecast, mape, predictable_units,
                            special_factors, typical_profile, wape)
from metro.groups import discover_groups
from metro.prep import complete_days

LEVELS = ["none", "station", "group"]
K_VALUES = (4, 5, 6)


def groups_before(hourly, calendar, cut, k_values=K_VALUES) -> pd.Series:
    """Groups rebuilt from data strictly before `cut` only."""
    return discover_groups(station_features(hourly[hourly["date"] < pd.Timestamp(cut)], calendar), k_values=k_values)


def _only(hourly: pd.DataFrame, units: pd.Index) -> pd.DataFrame:
    idx = pd.MultiIndex.from_frame(hourly[KEYS])
    return hourly[idx.isin(units)]


def _predict(h, calendar, groups, cut, days, level, closed_threshold):
    train = h[h["date"] < pd.Timestamp(cut)]
    profile = typical_profile(train, calendar, as_of=cut, closed_threshold=closed_threshold)
    factors = special_factors(train, calendar, groups, before=cut, level=level, closed_threshold=closed_threshold)
    future = calendar[calendar["date"].isin(days)]
    return forecast(profile, factors, future)


def _actual_grid(h, pred):
    """Actual hourly boardings on the forecast grid (0 where a unit had no row)."""
    act = h.groupby(["date"] + KEYS + ["hour"])["boardings"].sum().rename("actual").reset_index()
    out = pred.merge(act, on=["date"] + KEYS + ["hour"], how="left")
    out["actual"] = out["actual"].fillna(0.0)
    return out


def _scored(hourly, calendar, groups, cut, days, level, closed_threshold, regroup, k_values):
    if regroup:
        groups = groups_before(hourly, calendar, cut, k_values)
    h = _only(hourly, predictable_units(groups))
    return _actual_grid(h, _predict(h, calendar, groups, cut, days, level, closed_threshold))


def backtest_predictions(hourly, calendar, groups, start="2024-04-01", end="2024-05-26", level="group",
                         closed_threshold: float | None = CLOSED_THRESHOLD, regroup: bool = False,
                         k_values=K_VALUES) -> pd.DataFrame:
    """Hourly forecast (`boardings`) and `actual` per unit for start..end, built from data before start."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    days = sorted(d for d in hourly["date"].unique() if start <= d <= end)
    return _scored(hourly, calendar, groups, start, days, level, closed_threshold, regroup, k_values)


def backtest_recent(hourly, calendar, groups, start="2024-04-01", end="2024-05-26", level="group",
                    closed_threshold: float | None = CLOSED_THRESHOLD, regroup: bool = False,
                    k_values=K_VALUES) -> dict:
    """Hide start..end, forecast it from data before start, score at station-day and line-band level.
    Station-day totals include hours 0-5; line-band totals cover the card's bands (06-23) only."""
    g = backtest_predictions(hourly, calendar, groups, start, end, level, closed_threshold, regroup, k_values)
    sd = g.groupby(["date"] + KEYS)[["actual", "boardings"]].sum()
    b = g.assign(band=g["hour"].map(HOUR_TO_BAND)).dropna(subset=["band"])
    lb = b.groupby(["date", "line", "band"])[["actual", "boardings"]].sum()
    return {"station_day_mape": mape(sd["actual"], sd["boardings"]),
            "line_band_mape": mape(lb["actual"], lb["boardings"]),
            "station_day_wape": wape(sd["actual"], sd["boardings"]),
            "line_band_wape": wape(lb["actual"], lb["boardings"])}


def _blocks(calendar, dates, year):
    """Runs of consecutive calendar days with the same special category, within `dates`."""
    cal = calendar[(calendar["date"].dt.year == year) & calendar["date"].isin(dates)].sort_values("date")
    cal = cal[cal["special"] != "none"]
    blocks, cur = [], []
    for d, s in zip(cal["date"], cal["special"]):
        if cur and (s != cur[-1][1] or d - cur[-1][0] != pd.Timedelta(days=1)):
            blocks.append(cur)
            cur = []
        cur.append((d, s))
    if cur:
        blocks.append(cur)
    return [(b[0][1], [d for d, _ in b]) for b in blocks]


def backtest_special(hourly, calendar, groups, year: int = 2024,
                     closed_threshold: float | None = CLOSED_THRESHOLD, regroup: bool = False,
                     k_values=K_VALUES) -> pd.DataFrame:
    """Each special-day block of `year` is forecast from data before its first day, for each level."""
    scored = []
    for special, days in _blocks(calendar, set(hourly["date"].unique()), year):
        for level in LEVELS:
            g = _scored(hourly, calendar, groups, days[0], days, level, closed_threshold, regroup, k_values)
            sd = g.groupby(["date"] + KEYS)[["actual", "boardings"]].sum().reset_index()
            scored.append(sd.assign(special=special, level=level))
    if not scored:
        return pd.DataFrame(columns=["special", "level", "station_day_mape", "station_day_wape", "n_days"])
    s = pd.concat(scored)
    rows = [{"special": sp, "level": lv, "station_day_mape": mape(x["actual"], x["boardings"]),
             "station_day_wape": wape(x["actual"], x["boardings"]),
             "n_days": x["date"].nunique()} for (sp, lv), x in s.groupby(["special", "level"])]
    return pd.DataFrame(rows)


def compare_complete_days(hourly, calendar, groups, level: str, as_of="2024-08-01",
                          closed_threshold: float | None = CLOSED_THRESHOLD, regroup: bool = False,
                          k_values=K_VALUES) -> pd.DataFrame:
    """Network daily total of predictable units: forecast from data before as_of vs the actual,
    for every complete day on or after as_of."""
    as_of = pd.Timestamp(as_of)
    h = hourly[hourly["date"].isin(complete_days(hourly))]
    days = sorted(d for d in h["date"].unique() if d >= as_of)
    g = _scored(h, calendar, groups, as_of, days, level, closed_threshold, regroup, k_values)
    out = g.groupby("date")[["actual", "boardings"]].sum().reindex(days).reset_index()
    out = out.rename(columns={"index": "date", "boardings": "forecast"})
    out["ape"] = (out["actual"] - out["forecast"]).abs() / out["actual"]
    return out[["date", "actual", "forecast", "ape"]]
