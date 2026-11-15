import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from model import (BANDS, DAY_TYPES, PEAK_BANDS, band_boardings, load_index, recommend,  # noqa: E402
                   robust, trips_per_cell)

DAYS = {"weekday": 20, "saturday": 4, "sunday": 4}
CELLS = [(d, b) for d in DAY_TYPES for b in BANDS]


def test_bands_cover_operating_hours_once():
    hours = sorted(h for hs in BANDS.values() for h in hs)
    assert hours == list(range(6, 24)) and list(BANDS) == ["early", "am_peak", "midday", "pm_peak", "evening", "late"]
    assert DAY_TYPES == ["weekday", "saturday", "sunday"] and PEAK_BANDS == ("am_peak", "pm_peak")


def test_bands_match_the_analysis_package():
    from metro.forecast import BANDS as ANALYSIS_BANDS

    assert BANDS == ANALYSIS_BANDS


def test_model_does_not_need_pandas():
    src = (Path(__file__).resolve().parents[1] / "app" / "model.py").read_text()
    assert "pandas" not in src and "numpy" not in src


def test_band_boardings_sums_hours_and_drops_overnight():
    b = band_boardings({"weekday": [1.0] * 24, "saturday": [0.0] * 24, "sunday": [0.0] * 24})
    assert b[("weekday", "am_peak")] == 3 and b[("weekday", "midday")] == 6 and sum(b.values()) == 18
    assert len(b) == 18


def test_flat_trips_are_proportional_to_band_hours_and_sum_to_month():
    t = trips_per_cell(18 * 28 * 10, DAYS)  # 10 trips per operating hour
    assert t[("weekday", "am_peak")] == pytest.approx(30) and t[("sunday", "early")] == pytest.approx(10)
    assert sum(DAYS[d] * v for (d, _), v in t.items()) == pytest.approx(18 * 28 * 10)


def test_multipliers_shift_trips_but_keep_monthly_total():
    t = trips_per_cell(5040, DAYS, peak_mult=2.0, weekend_mult=0.6)
    assert sum(DAYS[d] * v for (d, _), v in t.items()) == pytest.approx(5040)
    assert t[("weekday", "am_peak")] / 3 == pytest.approx(2 * t[("weekday", "midday")] / 6)
    assert t[("saturday", "midday")] == pytest.approx(0.6 * t[("weekday", "midday")])
    assert t[("saturday", "am_peak")] / 3 == pytest.approx(t[("saturday", "midday")] / 6)  # no peak boost on weekends


def test_day_type_with_no_days_in_window_does_not_break_the_total():
    days = {"weekday": 22, "saturday": 0, "sunday": 4}
    t = trips_per_cell(1000, days)
    assert sum(days[d] * v for (d, _), v in t.items()) == pytest.approx(1000)


def test_load_index_is_boardings_per_trip():
    trips = trips_per_cell(18 * 28 * 10, DAYS)
    b = {c: 50.0 * trips[c] for c in CELLS}
    assert all(v == pytest.approx(50.0) for v in load_index(b, trips).values())


HIGH, LOW = ("weekday", "am_peak"), ("sunday", "late")


def test_recommend_labels_relative_to_line_mean():
    trips = {c: 10.0 for c in CELLS}
    load = {c: 100.0 for c in CELLS}
    load[HIGH], load[LOW] = 200.0, 40.0            # reference = (200 + 40 + 16 * 100) / 18 = 102.2
    labels = recommend(load, trips)
    assert labels[HIGH] == "add" and labels[LOW] == "reduce" and list(labels.values()).count("keep") == 16


def test_recommend_reference_is_trip_weighted():
    trips = {c: 1.0 for c in CELLS}
    trips[HIGH] = 100.0                              # a heavily served cell pulls the reference up
    load = {c: 100.0 for c in CELLS}
    load[HIGH] = 200.0                               # reference = (200*100 + 17*100) / 117 = 185.5
    labels = recommend(load, trips)
    assert labels[HIGH] == "keep" and labels[("weekday", "midday")] == "reduce"


def _robust_world():
    flat = trips_per_cell(5040, DAYS)
    per_trip = {c: 100.0 for c in CELLS}
    per_trip[("weekday", "am_peak")] = 400.0         # far above the rest: "add" at every assumption
    per_trip[("weekday", "pm_peak")] = 200.0         # "add" with flat service only (reference ~ 129 there)
    return {c: per_trip[c] * flat[c] for c in CELLS}


def test_robust_true_only_when_label_never_changes():
    b = _robust_world()
    r = robust(b, 5040, DAYS)
    assert r[("weekday", "am_peak")] is True and r[("weekday", "pm_peak")] is False
    base = recommend(load_index(b, trips_per_cell(5040, DAYS)), trips_per_cell(5040, DAYS))
    assert base[("weekday", "pm_peak")] == "add"
    hi = trips_per_cell(5040, DAYS, peak_mult=2.0)
    assert recommend(load_index(b, hi), hi)[("weekday", "pm_peak")] != "add"


def test_zero_trips_or_zero_boardings_do_not_crash():
    assert load_index({c: 0.0 for c in CELLS}, trips_per_cell(0, DAYS)) == {c: 0.0 for c in CELLS}
    assert set(recommend({c: 0.0 for c in CELLS}, trips_per_cell(0, DAYS)).values()) == {"keep"}
    assert set(robust({c: 0.0 for c in CELLS}, 0, DAYS).values()) == {True}


def test_slider_extremes_are_accepted():
    for pm, wm in [(1.0, 0.6), (2.0, 1.0), (2.0, 0.6)]:
        assert len(trips_per_cell(5040, DAYS, pm, wm)) == 18


# --- review: threshold edges and the weekend multiplier in robust() ---------------------------

def _boundary_loads(high, low):
    """18 cells with equal trips; the line mean is exactly 1600 when high=2000 and low=960."""
    trips = {c: 10.0 for c in CELLS}
    load = {c: 1615.0 for c in CELLS}
    load[CELLS[0]], load[CELLS[1]] = high, low
    return load, trips


def test_recommend_thresholds_are_inclusive_at_1_25_and_0_6():
    load, trips = _boundary_loads(2000.0, 960.0)          # exactly 1.25x and 0.6x the mean of 1600
    labels = recommend(load, trips)
    assert labels[CELLS[0]] == "add" and labels[CELLS[1]] == "reduce"


def test_recommend_just_inside_the_thresholds_is_keep():
    load, trips = _boundary_loads(1999.0, 961.0)
    ref = sum(load.values()) / len(load)
    assert load[CELLS[0]] < 1.25 * ref and load[CELLS[1]] > 0.6 * ref
    labels = recommend(load, trips)
    assert labels[CELLS[0]] == "keep" and labels[CELLS[1]] == "keep"


def test_robust_also_varies_the_weekend_multiplier():
    # Saturday midday 10% busier than its share: its label changes only as weekend service changes
    t = trips_per_cell(5040, DAYS)
    b = {c: v * 100 * (1.1 if c == ("saturday", "midday") else 1.0) for c, v in t.items()}
    c = ("saturday", "midday")
    assert robust(b, 5040, DAYS, weekend_grid=(1.0,))[c] is True     # peak multiplier alone: stable
    assert robust(b, 5040, DAYS, peak_grid=(1.0,))[c] is False       # weekend multiplier alone: changes
    assert robust(b, 5040, DAYS)[c] is False                          # the default grid includes it
