import pandas as pd

from metro.calendar import load_calendar


def test_calendar_covers_period_without_gaps():
    cal = load_calendar()
    assert cal.date.min() == pd.Timestamp("2023-01-01")
    assert cal.date.max() >= pd.Timestamp("2024-11-30")
    assert cal.date.is_unique and (cal.date.diff().dropna() == pd.Timedelta(days=1)).all()


def test_calendar_values():
    cal = load_calendar()
    assert set(cal.day_type) == {"weekday", "saturday", "sunday"}
    assert set(cal.special) == {"none", "public_holiday", "religious_holiday", "school_break"}
    expected = cal.date.dt.day_of_week.map(lambda d: "saturday" if d == 5 else "sunday" if d == 6 else "weekday")
    assert (cal.day_type == expected).all()


def test_known_days():
    cal = load_calendar().set_index("date")
    assert cal.loc["2024-10-29", "special"] == "public_holiday"      # Republic Day
    assert cal.loc["2024-04-10", "special"] == "religious_holiday"   # Ramazan Bayramı day 1
    assert cal.loc["2024-06-16", "special"] == "religious_holiday"   # Kurban Bayramı day 1
    assert cal.loc["2023-04-21", "special"] == "religious_holiday"   # Ramazan Bayramı day 1
    assert cal.loc["2024-10-15", "special"] == "none"


def test_priority_and_school_breaks():
    cal = load_calendar().set_index("date")
    assert cal.loc["2023-04-23", "special"] == "religious_holiday"   # also 23 April: religious wins
    assert cal.loc["2024-01-24", "special"] == "school_break"        # semester break
    assert cal.loc["2024-07-15", "special"] == "public_holiday"      # inside summer break: public wins
    assert cal.loc["2024-07-20", "special"] == "none"                # Saturday in summer: breaks mark weekdays only
    assert cal.loc["2024-11-12", "special"] == "school_break"        # November 2024 mid-term break (forecast window)
    assert cal.loc["2023-02-15", "special"] == "school_break"        # semester break extended after the earthquake


def test_invalid_special_value_is_rejected(tmp_path):
    import pytest

    bad = tmp_path / "cal.csv"
    bad.write_text("date,day_type,special,label\n2024-01-01,weekday,holiday,\n")
    with pytest.raises(ValueError, match="special"):
        load_calendar(bad)
