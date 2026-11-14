"""Backtests. Profiles and factors always come from data strictly before the first scored day."""
from __future__ import annotations

import pandas as pd

from metro.forecast import (HOUR_TO_BAND, KEYS, forecast, mape, predictable_units, special_factors,
                            typical_profile, wape)
from metro.prep import complete_days

LEVELS = ["none", "station", "group"]


def _only(hourly: pd.DataFrame, units: pd.Index) -> pd.DataFrame:
    idx = pd.MultiIndex.from_frame(hourly[KEYS])
    return hourly[idx.isin(units)]


def _predict(h, calendar, groups, cut, days, level):
    profile = typical_profile(h, calendar, as_of=cut)
    factors = special_factors(h, calendar, groups, before=cut, level=level)
    future = calendar[calendar["date"].isin(days)]
    return forecast(profile, factors, future)


def _actual_grid(h, pred):
    """Actual hourly boardings on the forecast grid (0 where a unit had no row)."""
    act = h.groupby(["date"] + KEYS + ["hour"])["boardings"].sum().rename("actual").reset_index()
    out = pred.merge(act, on=["date"] + KEYS + ["hour"], how="left")
    out["actual"] = out["actual"].fillna(0.0)
    return out


def backtest_recent(hourly, calendar, groups, start="2024-04-01", end="2024-05-26", level="group") -> dict:
    """Hide start..end, forecast it from data before start, score at station-day and line-band level."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    h = _only(hourly, predictable_units(groups))
    days = sorted(d for d in h["date"].unique() if start <= d <= end)
    g = _actual_grid(h, _predict(h, calendar, groups, start, days, level))
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


def backtest_special(hourly, calendar, groups, year: int = 2024) -> pd.DataFrame:
    """Each special-day block of `year` is forecast from data before its first day, for each level."""
    h = _only(hourly, predictable_units(groups))
    scored = []
    for special, days in _blocks(calendar, set(h["date"].unique()), year):
        cut = days[0]
        for level in LEVELS:
            g = _actual_grid(h, _predict(h, calendar, groups, cut, days, level))
            sd = g.groupby(["date"] + KEYS)[["actual", "boardings"]].sum().reset_index()
            scored.append(sd.assign(special=special, level=level))
    if not scored:
        return pd.DataFrame(columns=["special", "level", "station_day_mape", "station_day_wape", "n_days"])
    s = pd.concat(scored)
    rows = [{"special": sp, "level": lv, "station_day_mape": mape(x["actual"], x["boardings"]),
             "station_day_wape": wape(x["actual"], x["boardings"]),
             "n_days": x["date"].nunique()} for (sp, lv), x in s.groupby(["special", "level"])]
    return pd.DataFrame(rows)


def compare_complete_days(hourly, calendar, groups, level: str, as_of="2024-08-01") -> pd.DataFrame:
    """Network daily total of predictable units: forecast from data before as_of vs the actual,
    for every complete day on or after as_of."""
    as_of = pd.Timestamp(as_of)
    h = hourly[hourly["date"].isin(complete_days(hourly))]
    h = _only(h, predictable_units(groups))
    days = sorted(d for d in h["date"].unique() if d >= as_of)
    pred = _predict(h[h["date"] < as_of], calendar, groups, as_of, days, level)
    f = pred.groupby("date")["boardings"].sum().rename("forecast")
    a = h[h["date"] >= as_of].groupby("date")["boardings"].sum().rename("actual")
    out = pd.concat([a, f], axis=1).reindex(days).reset_index().rename(columns={"index": "date"})
    out["ape"] = (out["actual"] - out["forecast"]).abs() / out["actual"]
    return out[["date", "actual", "forecast", "ape"]]
