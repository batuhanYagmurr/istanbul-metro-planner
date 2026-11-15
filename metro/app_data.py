"""Everything the panel needs, as one JSON-ready dict. The panel reads only this."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from metro import backtest as bt
from metro.features import FEATURE_COLS, station_features
from metro.forecast import (CLOSED_THRESHOLD, DAY_TYPES, KEYS, forecast, predictable_units, special_factors,
                            typical_profile, wape)
from metro.groups import OUTLIER, discover_groups, fit_rule, rule_agreement
from metro.prep import ANALYSIS_END, STRAY_LINES, analysis_hourly

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import model  # noqa: E402

EVENT_NAME = "Event-driven (unpredictable)"
DATA_START = "2023-01-01"
FORECAST_START, FORECAST_END = "2024-08-01", "2024-08-31"
FORECAST_MONTH = "2024-08"
MAIN = ("2024-04-01", "2024-05-26")
EXTRA = ("2024-06-03", "2024-07-28")
LEVELS = ["none", "station", "group"]
SIMPLER = {"none": 0, "group": 1, "station": 2}
RECENT_DAYS = 56


def _r(x, nd=4):
    x = float(x)
    return round(x, nd) if np.isfinite(x) else None


def choose_level(special: pd.DataFrame, main: dict) -> str:
    """Lowest boardings-weighted error on the special-day backtest (days-weighted over categories);
    falls back to the main window when there are no special days. Ties go to the simpler level."""
    if len(special):
        s = special.assign(w=special["station_day_wape"] * special["n_days"])
        score = (s.groupby("level")["w"].sum() / s.groupby("level")["n_days"].sum()).to_dict()
    else:
        score = {lv: main[lv]["station_day_wape"] for lv in LEVELS}
    return min(LEVELS, key=lambda lv: (round(score[lv], 9), SIMPLER[lv]))


def _trips_for(trips: pd.DataFrame, line: str):
    t = trips[(trips["line"] == line) & (trips["month"] <= FORECAST_MONTH)].sort_values("month")
    if t.empty:
        return None, None, False
    row = t[t["month"] == FORECAST_MONTH]
    if len(row):
        return float(row["trips"].iloc[0]), FORECAST_MONTH, False
    return float(t["trips"].iloc[-1]), t["month"].iloc[-1], True


def _examples(features: pd.DataFrame, labels: pd.Series, volume: pd.Series, n: int = 5) -> dict:
    """Per group: the n busiest units among the half closest to the group's mean features."""
    f = features.loc[labels.index, FEATURE_COLS]
    sd = f.std().replace(0, 1)
    out = {}
    for g, idx in labels.groupby(labels).groups.items():
        d = f.loc[idx]
        dist = ((d - d.mean()) / sd).pow(2).sum(axis=1)
        close = dist[dist <= dist.median()].index
        top = volume.reindex(close).sort_values(ascending=False).head(n).index
        out[g] = [f"{l} {s}" for l, s in top]
    return out


def build_app_data(hourly, calendar, trips, group_names: dict, groups: pd.Series | None = None,
                   rule: str = "", k_values=(4, 5, 6), min_size: int = 5,
                   closed_threshold: float | None = CLOSED_THRESHOLD) -> dict:
    full = hourly[~hourly["line"].isin(STRAY_LINES)]
    h = analysis_hourly(full)
    features = station_features(h, calendar)
    if groups is None:
        groups = discover_groups(features, k_values=k_values, min_size=min_size)
    names = {**group_names, OUTLIER: EVENT_NAME}

    # backtests ---------------------------------------------------------------
    kw = dict(closed_threshold=closed_threshold)
    main = {lv: bt.backtest_recent(h, calendar, groups, *MAIN, level=lv, **kw) for lv in LEVELS}
    extra = {lv: bt.backtest_recent(h, calendar, groups, *EXTRA, level=lv, **kw) for lv in LEVELS}
    special = bt.backtest_special(h, calendar, groups, **kw)
    level = choose_level(special, main)
    complete = {lv: bt.compare_complete_days(full, calendar, groups, level=lv, **kw) for lv in LEVELS}
    cu = complete[level]

    # August forecast (summer scenario) --------------------------------------
    cut = pd.Timestamp(FORECAST_START)
    units = predictable_units(groups)
    hp = bt._only(h, units)
    profile = typical_profile(hp, calendar, as_of=cut, closed_threshold=closed_threshold)
    factors = special_factors(hp, calendar, groups, before=cut, level=level, closed_threshold=closed_threshold)
    future = calendar[(calendar["date"] >= cut) & (calendar["date"] <= pd.Timestamp(FORECAST_END))]
    fc = forecast(profile, factors, future)
    fc = fc.merge(future[["date", "day_type", "special"]], on="date")
    days = {d: int((future["day_type"] == d).sum()) for d in DAY_TYPES}

    recent = h[h["date"] >= cut - pd.Timedelta(days=RECENT_DAYS)]
    n_recent = recent["date"].nunique()
    unit_day = recent.groupby(KEYS)["boardings"].sum() / max(n_recent, 1)
    labels = groups[groups.index.isin(features.index)]
    lab_ok = labels[labels != OUTLIER]
    tree_agree = rule_agreement(fit_rule(features, labels), features, labels) if labels.nunique() > 1 else 1.0
    volume = h.groupby(KEYS)["boardings"].sum()
    examples = _examples(features, lab_ok, volume) if len(lab_ok) else {}

    lines = {}
    for line in sorted(h["line"].unique()):
        lf = fc[fc["line"] == line]
        per_hour = lf.groupby(["date", "day_type", "hour"])["boardings"].sum().reset_index()
        hourly_fc = {}
        for d in DAY_TYPES:
            x = per_hour[per_hour["day_type"] == d].groupby("hour")["boardings"].sum() / max(days[d], 1)
            hourly_fc[d] = [_r(v, 1) for v in x.reindex(range(24), fill_value=0.0)]
        daily = lf.groupby("date")["boardings"].sum().reindex(future["date"], fill_value=0.0)
        spec = future.set_index("date")["special"]
        lh = h[h["line"] == line]
        meas = typical_profile(lh, calendar, as_of=cut, closed_threshold=None)
        measured = {d: [_r(v, 1) for v in meas[meas["day_type"] == d].groupby("hour")["boardings"].sum()
                        .reindex(range(24), fill_value=0.0)] for d in DAY_TYPES}
        monthly_b = lh.assign(month=lh["date"].dt.strftime("%Y-%m")).groupby("month")["boardings"].sum()
        tline = trips[trips["line"] == line].set_index("month")["trips"]
        t_month, t_used, fallback = _trips_for(trips, line)
        in_fc = set(units)
        line_units = sorted(set(map(tuple, lh[KEYS].drop_duplicates().to_numpy())))
        stations = []
        for key in line_units:
            g = groups.get(key)
            stations.append({"station": key[1],
                             "group": None if g is None or pd.isna(g) else names.get(int(g), str(g)),
                             "in_forecast": key in in_fc,
                             "boardings_day": _r(unit_day.get(key, 0.0), 1)})
        covered = sum(unit_day.get(k, 0.0) for k in line_units if k in in_fc)
        total = sum(unit_day.get(k, 0.0) for k in line_units)
        lines[line] = {
            "has_trips": t_month is not None, "trips_month": t_month, "trips_month_used": t_used,
            "trips_month_is_fallback": fallback,
            "has_forecast": bool(len(lf)), "forecast_coverage": _r(covered / total if total else 0.0),
            "monthly": [{"month": m, "boardings": int(b),
                         "trips": (float(tline[m]) if m in tline.index else None)} for m, b in monthly_b.items()],
            "days": days, "hourly": hourly_fc, "measured_hourly": measured,
            "stations": stations,
            "daily": [{"date": d.strftime("%Y-%m-%d"), "boardings": _r(v, 1), "special": spec[d]}
                      for d, v in daily.items()],
        }

    def block(res):
        return {lv: {k: _r(v) for k, v in res[lv].items()} for lv in LEVELS}

    return {
        "meta": {
            "data_start": DATA_START, "data_end": ANALYSIS_END,
            "forecast_start": FORECAST_START, "forecast_end": FORECAST_END, "scenario": "summer",
            "closed_threshold": closed_threshold, "add_at": 1.25, "reduce_at": 0.6,
            "backtest": {
                "level_used": level,
                "window": f"{MAIN[0]}..{MAIN[1]}",
                "station_day_wape": _r(main[level]["station_day_wape"]),
                "station_day_mape": _r(main[level]["station_day_mape"]),
                "line_band_wape": _r(main[level]["line_band_wape"]),
                "line_band_mape": _r(main[level]["line_band_mape"]),
                "main": block(main),
                "extra": {"window": f"{EXTRA[0]}..{EXTRA[1]}", **block(extra)},
                "special": [{k: (_r(v) if isinstance(v, float) else v) for k, v in r.items()}
                            for r in special.to_dict("records")],
                "complete_days": [{"date": r.date.strftime("%Y-%m-%d"), "actual": int(r.actual),
                                   "forecast": _r(r.forecast, 1),
                                   "ape": {lv: _r(complete[lv].set_index("date").at[r.date, "ape"]) for lv in LEVELS}}
                                  for r in cu.itertuples()],
                "complete_days_wape": _r(wape(cu["actual"], cu["forecast"])) if len(cu) else None,
                "complete_days_mape": _r(cu["ape"].mean()) if len(cu) else None,
                "complete_days_by_level": {lv: {"wape": _r(wape(c["actual"], c["forecast"])) if len(c) else None,
                                                "mape": _r(c["ape"].mean()) if len(c) else None,
                                                "n_days": int(len(c))} for lv, c in complete.items()},
            },
            "rule_agreement": _r(tree_agree), "rule": rule,
            "event_units": [{"line": k[0], "station": k[1], "late_share": _r(features.at[k, "late_share"])}
                            for k in sorted(groups[groups == OUTLIER].index) if k in features.index],
        },
        "groups": [{"name": names[g], "n_stations": int((groups == g).sum()), "examples": examples.get(g, [])}
                   for g in sorted(set(groups.dropna().astype(int)), key=lambda g: (g == OUTLIER, g))],
        "lines": lines,
    }


def recommendation_rows(data: dict, peak_mult: float = 1.0, weekend_mult: float = 1.0) -> pd.DataFrame:
    """The card for every line with trips and a forecast, at the given assumptions."""
    rows = []
    for line, d in data["lines"].items():
        if not (d["has_trips"] and d["has_forecast"]):
            continue
        b = model.band_boardings(d["hourly"])
        t = model.trips_per_cell(d["trips_month"], d["days"], peak_mult, weekend_mult)
        load = model.load_index(b, t)
        labels = model.recommend(load, t)
        rob = model.robust(b, d["trips_month"], d["days"])
        for c in model.CELLS:
            rows.append({"line": line, "day_type": c[0], "band": c[1], "boardings_per_day": round(b[c], 1),
                         "trips_per_day": round(t[c], 2), "load": round(load[c], 1), "label": labels[c],
                         "robust": bool(rob[c])})
    cols = ["line", "day_type", "band", "boardings_per_day", "trips_per_day", "load", "label", "robust"]
    return pd.DataFrame(rows, columns=cols).astype({"robust": bool})
