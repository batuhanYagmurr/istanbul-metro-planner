import numpy as np
import pandas as pd
import pytest

from metro.features import FEATURE_COLS, station_features
from synth import calendar, hourly

CAL = calendar("2023-01-01", "2024-02-29")  # 14 months
COMMUTER = dict(weekday={8: 100, 12: 50, 17: 50}, weekend={12: 20})


def test_feature_cols_order():
    assert FEATURE_COLS == ["weekend_ratio", "am_share", "midday_share", "pm_share", "late_share",
                            "discount_share", "transfer_share"]


def test_features_on_synthetic_commuter_station():
    h = hourly(CAL, "M2", "A", discount=0.1, **COMMUTER)
    f = station_features(h, CAL).loc[("M2", "A")]
    assert f.am_share == pytest.approx(0.5) and f.midday_share == pytest.approx(0.25) and f.pm_share == pytest.approx(0.25)
    assert f.late_share == 0 and f.weekend_ratio == pytest.approx(0.1)
    assert f.discount_share == pytest.approx(0.1) and f.months_active == 14 and f.eligible


def test_short_history_is_not_eligible():
    h = pd.concat([hourly(CAL, "M2", "A", **COMMUTER),
                   hourly(CAL, "M9", "NEW", start="2023-10-01", **COMMUTER)])
    f = station_features(h, CAL)
    assert f.loc[("M9", "NEW")].months_active == 5 and not f.loc[("M9", "NEW")].eligible
    assert f.loc[("M2", "A")].eligible


def test_special_days_do_not_enter_profile_shares():
    hols = ["2023-05-01", "2023-05-19", "2024-01-01"]
    cal = calendar("2023-01-01", "2024-02-29", public_holidays=hols)
    h = hourly(cal, "M2", "A", **COMMUTER)
    spike = pd.DataFrame([(pd.Timestamp(d), 23, "M2", "A", 1000, 1000, 1000, 0, 0, 0) for d in hols], columns=h.columns)
    f = station_features(pd.concat([h, spike]), cal).loc[("M2", "A")]
    assert f.late_share == 0 and f.am_share == pytest.approx(0.5)


def test_station_with_no_weekday_boardings_gets_nan_free_row():
    h = pd.concat([hourly(CAL, "M2", "A", **COMMUTER), hourly(CAL, "TF1", "W", weekend={14: 30})])
    f = station_features(h, CAL)
    row = f.loc[("TF1", "W")]
    assert row.weekend_ratio == 10.0
    assert (row[["am_share", "midday_share", "pm_share", "late_share"]] == 0).all()
    assert not f[FEATURE_COLS].isna().any().any() and np.isfinite(f[FEATURE_COLS].to_numpy()).all()


def test_late_share_covers_evening_and_overnight_hours():
    h = hourly(CAL, "M2", "A", weekday={8: 50, 20: 10, 22: 10, 3: 30}, weekend={12: 5})
    f = station_features(h, CAL).loc[("M2", "A")]
    assert f.late_share == pytest.approx(0.5) and f.am_share == pytest.approx(0.5)
