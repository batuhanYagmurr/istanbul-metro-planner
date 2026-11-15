import json
from pathlib import Path

import pandas as pd
import pytest

from metro.app_data import EVENT_NAME, build_app_data
from synth import calendar, hourly

ROOT = Path(__file__).resolve().parents[1]
NAMES = {0: "Morning", 1: "Evening"}
OPTS = dict(k_values=(2,), min_size=1)


@pytest.fixture(scope="module")
def world():
    cal = calendar("2023-06-01", "2024-08-31")
    parts = []
    for i, st in enumerate(("A", "B")):
        parts.append(hourly(cal, "M1", st, weekday={7: 4000, 8: 20000 + 100 * i, 17: 6000}, weekend={12: 30000}, end="2024-07-31"))
        parts.append(hourly(cal, "MX", st, weekday={8: 6000, 17: 20000 + 100 * i}, weekend={13: 30000}, end="2024-07-31"))
    stadium = hourly(cal, "MX", "STADIUM", weekday={21: 50}, weekend={21: 10}, end="2024-07-31")
    h = pd.concat(parts + [stadium], ignore_index=True)
    trips = pd.DataFrame([{"month": m, "line": "M1", "trips": 9000.0}
                          for m in pd.period_range("2023-06", "2024-07", freq="M").astype(str)])
    return h, cal, trips


@pytest.fixture(scope="module")
def data(world):
    h, cal, trips = world
    groups = pd.Series({("M1", "A"): 0, ("M1", "B"): 0, ("MX", "A"): 1, ("MX", "B"): 1, ("MX", "STADIUM"): -1})
    groups.index.names = ["line", "station"]
    return build_app_data(h, cal, trips, NAMES, groups=groups, **OPTS)


def test_schema_and_window(data):
    m = data["meta"]
    assert m["forecast_start"] == "2024-08-01" and m["forecast_end"] == "2024-08-31"
    assert m["data_end"] == "2024-07-31" and m["scenario"] == "summer"
    m1 = data["lines"]["M1"]
    assert sum(m1["days"].values()) == 31 and len(m1["daily"]) == 31
    assert all(len(v) == 24 for v in m1["hourly"].values())
    assert {"meta", "groups", "lines"} <= set(data)


def test_line_without_trips_is_demand_only(data):
    mx = data["lines"]["MX"]
    assert mx["has_trips"] is False and mx["trips_month"] is None and mx["trips_month_used"] is None


def test_missing_forecast_month_falls_back_and_is_flagged(data):
    m1 = data["lines"]["M1"]
    assert m1["has_trips"] is True and m1["trips_month"] == 9000.0
    assert m1["trips_month_used"] == "2024-07" and m1["trips_month_is_fallback"] is True


def test_no_nan_or_inf_anywhere_and_json_serializable(data):
    json.dumps(data, allow_nan=False)


def test_daily_forecast_matches_hourly_profile_and_day_counts(data):
    m1 = data["lines"]["M1"]
    from_hourly = sum(sum(m1["hourly"][d]) * n for d, n in m1["days"].items())
    assert sum(r["boardings"] for r in m1["daily"]) == pytest.approx(from_hourly)
    assert from_hourly > 0


def test_event_driven_station_is_demand_only(data):
    st = {s["station"]: s for s in data["lines"]["MX"]["stations"]}
    assert st["STADIUM"]["group"] == EVENT_NAME and st["STADIUM"]["in_forecast"] is False
    assert st["A"]["in_forecast"] is True and st["A"]["group"] == "Evening"
    # the stadium's evening boardings are not in the line forecast
    assert max(data["lines"]["MX"]["hourly"]["weekday"][21:22]) == 0


def test_event_driven_units_are_listed_with_their_late_share(data):
    # the README quotes this share; it must come from the data, not be typed in
    assert data["meta"]["event_units"] == [{"line": "MX", "station": "STADIUM", "late_share": 1.0}]


def test_backtest_block_reports_weighted_and_unweighted_errors_for_every_level(data):
    b = data["meta"]["backtest"]
    assert b["level_used"] in {"none", "station", "group"}
    for key in ("main", "extra"):
        for lv in ("none", "station", "group"):
            assert {"station_day_wape", "station_day_mape", "line_band_wape", "line_band_mape"} <= set(b[key][lv])
    assert b["station_day_wape"] == b["main"][b["level_used"]]["station_day_wape"]
    assert {"wape", "mape", "n_days"} <= set(b["complete_days_by_level"]["station"])


def test_recommendation_rows_only_for_lines_with_trips(world):
    from metro.app_data import recommendation_rows

    h, cal, trips = world
    groups = pd.Series({("M1", "A"): 0, ("M1", "B"): 0, ("MX", "A"): 1, ("MX", "B"): 1})
    groups.index.names = ["line", "station"]
    d = build_app_data(h, cal, trips, NAMES, groups=groups, **OPTS)
    rows = recommendation_rows(d)
    assert set(rows.line) == {"M1"} and len(rows) == 18
    assert set(rows.label) <= {"add", "keep", "reduce"} and rows.robust.dtype == bool
    assert list(rows.columns) == ["line", "day_type", "band", "boardings_per_day", "trips_per_day", "load", "label", "robust"]


def test_complete_month_series_stops_at_july_2024(data):
    months = [r["month"] for r in data["lines"]["M1"]["monthly"]]
    assert months[0] == "2023-06" and months[-1] == "2024-07"


def test_committed_data_json_matches_schema():
    path = ROOT / "app" / "data.json"
    d = json.loads(path.read_text())
    assert {"meta", "groups", "lines"} <= set(d) and any(l["has_trips"] for l in d["lines"].values())
    assert 0 < d["meta"]["backtest"]["station_day_wape"] < 1
    assert path.stat().st_size < 1_000_000
