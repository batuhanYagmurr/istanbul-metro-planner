import numpy as np
import pandas as pd
import pytest

from metro.backtest import backtest_recent, backtest_special, compare_complete_days
from synth import calendar, hourly, set_day

RELIGIOUS = (list(pd.date_range("2023-04-21", "2023-04-23")) + list(pd.date_range("2023-06-28", "2023-07-01"))
             + list(pd.date_range("2024-04-10", "2024-04-12")) + list(pd.date_range("2024-06-16", "2024-06-19")))
PROFILE = dict(weekday={8: 100, 17: 100}, weekend={12: 50})
UNITS = [("M2", "A", 0), ("M2", "B", 0), ("M4", "C", 1), ("M4", "D", 1)]


def _world(end="2024-07-31"):
    cal = calendar("2023-01-01", end, religious=RELIGIOUS)
    h = pd.concat([hourly(cal, l, s, **PROFILE) for l, s, _ in UNITS], ignore_index=True)
    rel = h.date.isin(RELIGIOUS)
    h.loc[rel, ["boardings", "passengers"]] *= 0.4
    groups = pd.Series({(l, s): g for l, s, g in UNITS})
    groups.index.names = ["line", "station"]
    return cal, h, groups


def test_backtest_special_prefers_right_level_on_synthetic_data():
    cal, h, groups = _world()
    r = backtest_special(h, cal, groups).set_index(["special", "level"])
    assert r.loc[("religious_holiday", "group"), "station_day_mape"] < 0.05 < r.loc[("religious_holiday", "none"), "station_day_mape"]
    assert r.loc[("religious_holiday", "none"), "n_days"] == 7
    assert set(r.index.get_level_values("level")) == {"none", "station", "group"}


def test_backtest_recent_returns_both_levels_of_error():
    cal, h, groups = _world()
    r = backtest_recent(h, cal, groups)
    assert set(r) == {"station_day_mape", "line_band_mape", "station_day_wape", "line_band_wape"}
    assert all(np.isfinite(v) for v in r.values())
    assert r["station_day_mape"] < 0.05   # stable synthetic world, religious factor learned from 2023


def test_backtest_recent_excludes_event_driven_units():
    cal, h, groups = _world()
    noisy = hourly(cal, "M9", "STADIUM", weekday={21: 1}, weekend={})
    noisy.loc[noisy.date.dt.day == 15, "boardings"] = 5_000
    groups[("M9", "STADIUM")] = -1
    r = backtest_recent(pd.concat([h, noisy], ignore_index=True), cal, groups)
    assert r["station_day_mape"] < 0.05


def test_compare_complete_days_skips_thin_days_and_uses_only_earlier_data():
    cal = calendar("2023-01-01", "2024-08-31")
    h = hourly(cal, "M2", "A", weekday={8: 750_000}, weekend={8: 750_000}, end="2024-07-31")
    h = set_day(h, "M2", "A", "2024-08-25", 1_500_000)
    h = set_day(h, "M2", "A", "2024-08-26", 500)
    event = hourly(cal, "M9", "STADIUM", weekday={21: 10}, weekend={21: 10}, end="2024-07-31")
    h = set_day(pd.concat([h, event], ignore_index=True), "M9", "STADIUM", "2024-08-25", 900_000)
    groups = pd.Series({("M2", "A"): 0, ("M9", "STADIUM"): -1})
    groups.index.names = ["line", "station"]
    r = compare_complete_days(h, cal, groups, level="none")
    assert r.date.dt.strftime("%Y-%m-%d").tolist() == ["2024-08-25"]
    assert r.actual.item() == 1_500_000 and r.ape.item() == pytest.approx(0.5)


def test_backtest_special_reports_weighted_error_too():
    cal, h, groups = _world()
    r = backtest_special(h, cal, groups)
    assert "station_day_wape" in r.columns and r.station_day_wape.notna().all()
