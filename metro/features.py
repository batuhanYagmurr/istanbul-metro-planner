"""Station features: how each line-station unit's ridership is shaped over the day and week."""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_COLS = ["weekend_ratio", "am_share", "midday_share", "pm_share", "late_share",
                "discount_share", "transfer_share"]
WEEKEND_RATIO_CAP = 10.0

AM_PEAK = range(7, 10)
MIDDAY = range(10, 16)
PM_PEAK = range(16, 20)
LATE = [20, 21, 22, 23, 0, 1, 2, 3, 4, 5]  # evening + late + overnight


def _active_day_counts(units: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    """Number of non-special weekdays and weekend days inside each unit's first..last date."""
    normal = calendar[calendar["special"] == "none"]
    out = []
    for (line, station), d0, d1 in zip(units.index, units["first"], units["last"]):
        span = normal[(normal["date"] >= d0) & (normal["date"] <= d1)]
        wd = int((span["day_type"] == "weekday").sum())
        out.append((line, station, wd, len(span) - wd))
    return pd.DataFrame(out, columns=["line", "station", "n_weekday", "n_weekend"]).set_index(["line", "station"])


def station_features(hourly: pd.DataFrame, calendar: pd.DataFrame, min_months: int = 12) -> pd.DataFrame:
    """One row per (line, station): FEATURE_COLS plus months_active and eligible.

    Profile features use non-special days only; months_active counts every month with boardings.
    """
    keys = ["line", "station"]
    span = hourly.groupby(keys).agg(first=("date", "min"), last=("date", "max"))
    months = hourly.assign(m=hourly["date"].dt.to_period("M")).groupby(keys)["m"].nunique()

    cal = calendar[["date", "day_type", "special"]]
    h = hourly.merge(cal, on="date", how="left")
    h = h[h["special"] == "none"]
    is_wd = h["day_type"] == "weekday"
    wd = h[is_wd]

    def band(hours):
        return wd[wd["hour"].isin(list(hours))].groupby(keys)["boardings"].sum()

    f = pd.DataFrame(index=span.index)
    wd_total = wd.groupby(keys)["boardings"].sum().reindex(f.index, fill_value=0)
    we_total = h[~is_wd].groupby(keys)["boardings"].sum().reindex(f.index, fill_value=0)
    days = _active_day_counts(span, calendar).reindex(f.index)
    wd_mean = wd_total / days["n_weekday"].replace(0, np.nan)
    we_mean = we_total / days["n_weekend"].replace(0, np.nan)
    ratio = (we_mean / wd_mean.replace(0, np.nan)).clip(upper=WEEKEND_RATIO_CAP)
    ratio[wd_mean.fillna(0) == 0] = WEEKEND_RATIO_CAP
    f["weekend_ratio"] = ratio.fillna(WEEKEND_RATIO_CAP)

    safe_wd = wd_total.replace(0, np.nan)
    for name, hours in (("am_share", AM_PEAK), ("midday_share", MIDDAY), ("pm_share", PM_PEAK), ("late_share", LATE)):
        f[name] = (band(hours).reindex(f.index, fill_value=0) / safe_wd).fillna(0.0)

    tot = h.groupby(keys)[["boardings", "b_discount", "b_transfer"]].sum().reindex(f.index, fill_value=0)
    safe_tot = tot["boardings"].replace(0, np.nan)
    f["discount_share"] = (tot["b_discount"] / safe_tot).fillna(0.0)
    f["transfer_share"] = (tot["b_transfer"] / safe_tot).fillna(0.0)

    f["months_active"] = months.reindex(f.index).astype(int)
    f["eligible"] = f["months_active"] >= min_months
    return f
