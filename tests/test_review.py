"""Tests added after the external review: leakage, hand-checked errors, regrouping per cut, closed-station days."""
import numpy as np
import pandas as pd
import pytest

from metro.forecast import special_factors, typical_profile
from synth import calendar, hourly, set_day
from test_backtest import _world
from test_forecast import _factor, _factor_data

START, END = "2024-04-01", "2024-05-26"


# (1) leakage -----------------------------------------------------------------

def test_backtest_predictions_unchanged_when_hidden_window_changes():
    from metro.backtest import backtest_predictions

    cal, h, groups = _world()
    base = backtest_predictions(h, cal, groups, start=START, end=END, level="station")
    inside = h.date.between(START, END)
    mutated = h.copy()
    mutated.loc[inside, "boardings"] *= 10
    again = backtest_predictions(mutated, cal, groups, start=START, end=END, level="station")
    pd.testing.assert_series_equal(base["boardings"], again["boardings"])
    assert not np.allclose(base["actual"], again["actual"])


def _one_holiday():
    """Only one public holiday (2023-05-17: A 60, B 10 against baselines of 100) before 2023-10-25,
    so a single leaked holiday would move the median."""
    cal, h, groups = _factor_data()
    h = h[~h.date.isin(pd.to_datetime(["2023-03-15", "2023-08-16"]))]
    return cal, h, groups


EXPECTED = {"station": 0.6, "group": 0.35}


@pytest.mark.parametrize("level", ["station", "group"])
def test_factors_ignore_a_special_day_exactly_on_before(level):
    cal, h, groups = _one_holiday()
    before = pd.Timestamp("2023-10-25")  # itself a public holiday
    spiked = set_day(set_day(h, "M2", "A", "2023-10-25", 100_000), "M2", "B", "2023-10-25", 100_000)
    for data in (h, spiked):
        f = special_factors(data, cal, groups, before=before, level=level)
        assert _factor(f, "M2", "A", "public_holiday") == pytest.approx(EXPECTED[level])


def test_group_factors_ignore_special_days_after_before():
    cal, h, groups = _one_holiday()
    before = pd.Timestamp("2023-10-02")
    spiked = set_day(set_day(h, "M2", "A", "2023-10-25", 100_000), "M2", "B", "2023-10-25", 100_000)
    base = special_factors(h, cal, groups, before=before, level="group")
    assert _factor(base, "M2", "B", "public_holiday") == pytest.approx(0.35)
    pd.testing.assert_frame_equal(base, special_factors(spiked, cal, groups, before=before, level="group"))


def test_backtest_errors_match_hand_computed_mape_and_wape():
    from metro.backtest import backtest_recent

    cal = calendar("2024-01-01", "2024-05-31")
    h = hourly(cal, "M2", "A", weekday={8: 100}, weekend={}, end="2024-03-31")
    days = [d for d, t in zip(cal.date, cal.day_type) if START <= d.strftime("%Y-%m-%d") <= END and t == "weekday"]
    actual = [80 if i % 2 == 0 else 120 for i in range(len(days))]
    for d, a in zip(days, actual):
        h = set_day(h, "M2", "A", d, a)
    groups = pd.Series({("M2", "A"): 0})
    groups.index.names = ["line", "station"]
    r = backtest_recent(h, cal, groups, start=START, end=END, level="none")
    a = np.array(actual, dtype=float)
    hand_mape = np.mean(np.abs(a - 100) / a)
    hand_wape = np.abs(a - 100).sum() / a.sum()
    assert r["station_day_mape"] == pytest.approx(hand_mape) and r["station_day_wape"] == pytest.approx(hand_wape)
    assert r["line_band_mape"] == pytest.approx(hand_mape) and r["line_band_wape"] == pytest.approx(hand_wape)


# (2) groups rebuilt from data before each cut --------------------------------

def _two_behaviours():
    """Six morning-departure and six evening-departure stations, distinct enough to cluster."""
    cal = calendar("2023-01-01", "2024-07-31")
    parts = []
    for i in range(6):
        parts.append(hourly(cal, "M2", f"AM{i}", weekday={8: 100 + 5 * i, 17: 30}, weekend={12: 40 + i}))
        parts.append(hourly(cal, "M4", f"PM{i}", weekday={8: 30, 17: 100 + 5 * i}, weekend={12: 70 + i}))
    h = pd.concat(parts, ignore_index=True)
    groups = pd.Series({k: 0 for k in h.groupby(["line", "station"]).size().index})
    groups.index.names = ["line", "station"]
    return cal, h, groups


def test_groups_before_uses_only_data_before_cut():
    from metro.backtest import groups_before

    cal, h, _ = _two_behaviours()
    cut = pd.Timestamp(START)
    base = groups_before(h, cal, cut, k_values=(2,))
    assert base.nunique() == 2 and (base != -1).all()
    mutated = h.copy()
    late = mutated.date >= cut
    mutated.loc[late & (mutated.hour == 8), "boardings"] *= 50
    pd.testing.assert_series_equal(base, groups_before(mutated, cal, cut, k_values=(2,)))


def test_regrouped_backtest_predictions_ignore_hidden_window():
    from metro.backtest import backtest_predictions

    cal, h, groups = _two_behaviours()
    kw = dict(start=START, end=END, level="group", regroup=True, k_values=(2,))
    base = backtest_predictions(h, cal, groups, **kw)
    mutated = h.copy()
    mutated.loc[mutated.date.between(START, END), "boardings"] *= 10
    pd.testing.assert_series_equal(base["boardings"], backtest_predictions(mutated, cal, groups, **kw)["boardings"])


# (3) closed-station days ------------------------------------------------------

def _closed_world():
    cal = calendar("2024-01-01", "2024-04-30")
    h = hourly(cal, "M2", "A", weekday={8: 100}, weekend={8: 40})
    return cal, set_day(h, "M2", "A", "2024-03-13", 2)   # Wednesday, station closed


def test_profile_skips_closed_station_days():
    cal, h = _closed_world()
    as_of = pd.Timestamp("2024-03-25")
    p = typical_profile(h, cal, as_of=as_of, closed_threshold=0.2)
    assert p[(p.day_type == "weekday") & (p.hour == 8)].boardings.item() == pytest.approx(100)
    old = typical_profile(h, cal, as_of=as_of, closed_threshold=None)
    assert old[(old.day_type == "weekday") & (old.hour == 8)].boardings.item() < 99


def test_baseline_skips_closed_station_days():
    cal = calendar("2024-01-01", "2024-04-30", public_holidays=["2024-03-20"])
    h = hourly(cal, "M2", "A", weekday={8: 100}, weekend={8: 40})
    h = set_day(set_day(h, "M2", "A", "2024-03-13", 2), "M2", "A", "2024-03-20", 50)
    groups = pd.Series({("M2", "A"): 0})
    groups.index.names = ["line", "station"]
    before = pd.Timestamp("2024-04-01")
    new = special_factors(h, cal, groups, before=before, level="station", closed_threshold=0.2)
    old = special_factors(h, cal, groups, before=before, level="station", closed_threshold=None)
    assert _factor(new, "M2", "A", "public_holiday") == pytest.approx(0.5)
    assert _factor(old, "M2", "A", "public_holiday") > 0.5


def test_closed_days_use_only_earlier_data():
    from metro.forecast import closed_days

    cal, h = _closed_world()
    before = pd.Timestamp("2024-03-25")
    base = closed_days(h, cal, before=before, threshold=0.2)
    assert list(base.itertuples(index=False, name=None)) == [("M2", "A", pd.Timestamp("2024-03-13"))]
    mutated = h.copy()
    mutated.loc[mutated.date >= before, "boardings"] = 1   # later days would drag the median down
    pd.testing.assert_frame_equal(base, closed_days(mutated, cal, before=before, threshold=0.2))


def test_station_that_has_not_opened_yet_is_not_closed():
    from metro.forecast import closed_days

    cal = calendar("2024-01-01", "2024-04-30")
    h = hourly(cal, "M2", "NEW", weekday={8: 100}, weekend={8: 40}, start="2024-03-01")
    assert closed_days(h, cal, before=pd.Timestamp("2024-04-01"), threshold=0.2).empty


@pytest.mark.parametrize("level", ["station", "group"])
def test_no_special_days_before_cut_gives_ones(level):
    cal, h, groups = _two_behaviours()
    f = special_factors(h, cal, groups, before=pd.Timestamp("2024-04-01"), level=level)
    assert f.factor.eq(1.0).all() and len(f) == 12 * 4
