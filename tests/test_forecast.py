import numpy as np
import pandas as pd
import pytest

from metro.forecast import forecast, mape, special_factors, typical_profile
from synth import calendar, hourly, set_day

AS_OF = pd.Timestamp("2024-03-25")  # Monday


def _profile_data():
    cal = calendar("2023-12-01", "2024-04-30", public_holidays=["2024-03-06"])
    early = hourly(cal, "M2", "A", weekday={8: 10}, weekend={12: 5}, end=AS_OF - pd.Timedelta(days=57))
    late = hourly(cal, "M2", "A", weekday={8: 20}, weekend={12: 5}, start=AS_OF - pd.Timedelta(days=56))
    h = set_day(pd.concat([early, late], ignore_index=True), "M2", "A", "2024-03-06", 500)
    return cal, h


def test_typical_profile_is_mean_of_last_n_weeks_non_special():
    cal, h = _profile_data()
    p = typical_profile(h, cal, as_of=AS_OF, n_weeks=8)
    assert p[(p.day_type == "weekday") & (p.hour == 8)].boardings.item() == pytest.approx(20)
    assert p[(p.day_type == "sunday") & (p.hour == 12)].boardings.item() == pytest.approx(5)
    assert len(p) == 72 and (p[(p.hour != 8) & (p.day_type == "weekday")].boardings == 0).all()


def test_typical_profile_ignores_data_on_and_after_as_of():
    cal, h = _profile_data()
    before = typical_profile(h, cal, as_of=AS_OF)
    later = h[h.date >= AS_OF].assign(boardings=10_000)
    after = typical_profile(pd.concat([h[h.date < AS_OF], later]), cal, as_of=AS_OF)
    pd.testing.assert_frame_equal(before, after)


FACTOR_AS_OF = pd.Timestamp("2023-10-02")
HOLS = ["2023-03-15", "2023-05-17", "2023-08-16"]  # Wednesdays


def _factor_data():
    cal = calendar("2023-01-01", "2023-12-31", public_holidays=HOLS + ["2023-10-25"])
    h = pd.concat([hourly(cal, "M2", "A", weekday={8: 100}, weekend={8: 40}),
                   hourly(cal, "M2", "B", weekday={8: 100}, weekend={8: 40})], ignore_index=True)
    for d, a in zip(HOLS, (50, 60, 100)):
        h = set_day(h, "M2", "A", d, a)
    h = set_day(h, "M2", "B", "2023-05-17", 10)
    h = set_day(h, "M2", "C", "2023-05-17", 30)   # C has no normal-day boardings: zero baseline
    groups = pd.Series({("M2", "A"): 0, ("M2", "B"): 0, ("M2", "C"): 1})
    groups.index.names = ["line", "station"]
    return cal, h, groups


def _factor(f, line, station, special):
    return f[(f.line == line) & (f.station == station) & (f.special == special)].factor.item()


def test_station_factor_is_median_ratio():
    cal, h, groups = _factor_data()
    f = special_factors(h, cal, groups, before=FACTOR_AS_OF, level="station")
    assert _factor(f, "M2", "A", "public_holiday") == pytest.approx(0.6)


def test_group_factor_pools_units():
    cal, h, groups = _factor_data()
    h = h[~h.date.isin(pd.to_datetime(["2023-03-15", "2023-08-16"]))]  # keep only the shared holiday
    h = set_day(h, "M2", "A", "2023-05-17", 50)                           # A: 50, B: 10, baselines 100 each
    f = special_factors(h, cal, groups, before=FACTOR_AS_OF, level="group")
    assert _factor(f, "M2", "A", "public_holiday") == pytest.approx(0.3)
    assert _factor(f, "M2", "B", "public_holiday") == pytest.approx(0.3)


def test_factor_falls_back_to_one():
    cal, h, groups = _factor_data()
    f = special_factors(h, cal, groups, before=FACTOR_AS_OF, level="station")
    assert np.isfinite(f.factor).all()
    assert f[f.special == "religious_holiday"].factor.eq(1.0).all()      # never seen
    assert _factor(f, "M2", "C", "public_holiday") == 1.0               # zero baseline
    assert set(f.special) == {"none", "public_holiday", "religious_holiday", "school_break"}


def test_factors_ignore_special_days_on_and_after_before():
    cal, h, groups = _factor_data()
    base = special_factors(h, cal, groups, before=FACTOR_AS_OF, level="station")
    spiked = set_day(h, "M2", "A", "2023-10-25", 100_000)   # a holiday after `before`
    pd.testing.assert_frame_equal(base, special_factors(spiked, cal, groups, before=FACTOR_AS_OF, level="station"))


def test_level_none_gives_all_ones():
    cal, h, groups = _factor_data()
    assert special_factors(h, cal, groups, before=FACTOR_AS_OF, level="none").factor.eq(1.0).all()


def test_event_driven_units_get_no_factor():
    cal, h, groups = _factor_data()
    groups[("M2", "A")] = -1
    f = special_factors(h, cal, groups, before=FACTOR_AS_OF, level="station")
    assert ("M2", "A") not in set(zip(f.line, f.station))


def test_forecast_applies_factor_on_special_day_only():
    profile = pd.DataFrame({"line": ["M2"], "station": ["A"], "day_type": ["weekday"], "hour": [8], "boardings": [20.0]})
    factors = pd.DataFrame({"line": ["M2", "M2"], "station": ["A", "A"], "special": ["none", "public_holiday"],
                            "factor": [1.0, 0.5]})
    future = pd.DataFrame({"date": pd.to_datetime(["2024-08-01", "2024-08-30"]), "day_type": ["weekday", "weekday"],
                           "special": ["none", "public_holiday"]})
    out = forecast(profile, factors, future)
    assert out[out.hour == 8].sort_values("date").boardings.tolist() == [20.0, 10.0]
    assert list(out.columns) == ["date", "line", "station", "hour", "boardings"]


def test_forecast_missing_factor_means_one():
    profile = pd.DataFrame({"line": ["M2"], "station": ["A"], "day_type": ["weekday"], "hour": [8], "boardings": [20.0]})
    factors = pd.DataFrame(columns=["line", "station", "special", "factor"])
    future = pd.DataFrame({"date": pd.to_datetime(["2024-08-30"]), "day_type": ["weekday"], "special": ["public_holiday"]})
    assert forecast(profile, factors, future).boardings.tolist() == [20.0]


def test_mape_ignores_zero_actuals():
    assert mape(pd.Series([100, 0, 50]), pd.Series([90, 5, 60])) == pytest.approx(0.15)


def test_wape_weights_errors_by_boardings():
    from metro.forecast import wape

    # a closed-station day (actual 2, forecast 3000) dominates mape but not wape
    a, p = pd.Series([1000, 1000, 2]), pd.Series([900, 1100, 3000])
    assert mape(a, p) > 100 and wape(a, p) == pytest.approx((100 + 100 + 2998) / 2002)
    assert np.isnan(wape(pd.Series([0, 0]), pd.Series([1, 1])))
