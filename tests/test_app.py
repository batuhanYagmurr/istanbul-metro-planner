import json
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app" / "streamlit_app.py")
DATA = json.loads((ROOT / "app" / "data.json").read_text())
sys.path.insert(0, str(ROOT / "app"))

import view  # noqa: E402


def run(line=None, peak=None, weekend=None):
    at = AppTest.from_file(APP, default_timeout=60).run()
    if line is not None:
        at.selectbox(key="line").set_value(line).run()
    if peak is not None:
        at.slider(key="peak").set_value(peak).run()
    if weekend is not None:
        at.slider(key="weekend").set_value(weekend).run()
    return at


def text_of(at):
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [i.value for i in at.info]
    return "\n".join(str(p) for p in parts)


# helpers in app/view.py ------------------------------------------------------

def test_error_label_is_the_weighted_backtest_error_with_one_decimal():
    assert view.error_label(DATA) == f'{DATA["meta"]["backtest"]["station_day_wape"] * 100:.1f}%'
    assert view.error_label(DATA) == "10.7%"


def test_august_check_reports_the_six_complete_days():
    over, n = view.august_over_forecast(DATA)
    assert n == 6 and over == pytest.approx(0.186, abs=0.001)


def test_summary_sentence_for_line_with_trips_is_measured_only():
    s = view.summary_sentence("M2", DATA["lines"]["M2"])
    assert s.startswith("In July 2024 M2 carried") and "boardings per trip" in s and "July 2023" in s
    assert "scenario" not in s.lower() and "forecast" not in s.lower()


def test_summary_sentence_for_line_without_trips_uses_boardings():
    s = view.summary_sentence("MARMARAY", DATA["lines"]["MARMARAY"])
    assert "boardings per day" in s and "July 2023" in s and "per trip" not in s


def test_card_words_describe_load_not_actions():
    words = " ".join(view.CELL_TEXT.values()).lower()
    assert "add" not in words and "reduce" not in words and "load per trip" in words


def test_assumed_trips_per_hour_sum_to_band_trips():
    import model

    L = DATA["lines"]["M2"]
    t = model.trips_per_cell(L["trips_month"], L["days"])
    per_hour = view.assumed_trips_per_hour(L, 1.0, 1.0, "weekday")
    assert len(per_hour) == 24 and sum(per_hour[h] for h in range(7, 10)) == pytest.approx(t[("weekday", "am_peak")])
    assert all(per_hour[h] == 0 for h in range(0, 6))


# the running app --------------------------------------------------------------

@pytest.mark.parametrize("line", sorted(DATA["lines"]))
def test_app_runs_for_every_line(line):
    at = run(line)
    assert not at.exception


def test_page_opens_with_measured_summary_then_scenario_disclaimer():
    at = run("M2")
    md = [m.value for m in at.markdown]
    first = next(i for i, v in enumerate(md) if "In July 2024 M2 carried" in v)
    second = next(i for i, v in enumerate(md) if "scenarios under an assumption" in v)
    assert first < second
    assert first <= 2


def test_panel_shows_error_scenario_and_six_day_note():
    t = text_of(run("M2"))
    assert view.error_label(DATA) in t and "Scenario" in t
    assert "6 complete August days" in t and "18.6%" in t
    assert "not occupancy" in t


def test_line_without_trips_shows_demand_only_note():
    no_trips = [l for l, d in DATA["lines"].items() if not d["has_trips"]]
    at = run(no_trips[0])
    assert any("demand view only" in i.value for i in at.info)


def test_slider_extremes_do_not_crash():
    assert not run("T1", peak=2.0, weekend=0.6).exception


def test_app_does_not_need_raw_data(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert not (tmp_path / "data" / "raw").exists()
    assert not run().exception
