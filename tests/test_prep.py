import datetime
from pathlib import Path

import openpyxl
import pytest

from metro.prep import aggregate_rail_month, load_hourly, load_trips

FIXTURE = Path(__file__).parent / "fixtures" / "hourly_sample.csv"


def _build(tmp_path):
    n = aggregate_rail_month(FIXTURE, tmp_path / "202410.parquet")
    return n, load_hourly(tmp_path)


def test_aggregate_keeps_only_rail_and_sums(tmp_path):
    n, df = _build(tmp_path)
    assert n == len(df) == 5
    assert set(df["line"]) == {"M2", "M4"}
    row = df[(df.line == "M2") & (df.station == "LEVENT") & (df.hour == 8) & (df.date == "2024-10-01")].iloc[0]
    assert (row.boardings, row.passengers) == (23, 21)
    assert (row.b_full, row.b_discount, row.b_free, row.b_transfer) == (14, 6, 2, 4)


def test_station_names_are_trimmed_and_uppercased(tmp_path):
    _, df = _build(tmp_path)
    row = df[(df.line == "M2") & (df.hour == 9)].iloc[0]
    assert row.station == "LEVENT" and row.b_discount == 7


def test_blank_station_is_kept_as_unknown(tmp_path):
    _, df = _build(tmp_path)
    assert df[(df.line == "M4") & (df.station == "UNKNOWN")].boardings.sum() == 5


def test_hour_text_becomes_int(tmp_path):
    _, df = _build(tmp_path)
    assert df[df.station == "KOZYATAGI"].hour.tolist() == [0]


def test_total_boardings_match_raw_rail_rows(tmp_path):
    _, df = _build(tmp_path)
    assert df.boardings.sum() == 46


def test_expected_month_accepts_matching_month(tmp_path):
    assert aggregate_rail_month(FIXTURE, tmp_path / "202410.parquet", expected_month="2024-10") == 5


def test_dates_outside_expected_month_raise(tmp_path):
    out = tmp_path / "202409.parquet"
    with pytest.raises(ValueError, match="2024-09"):
        aggregate_rail_month(FIXTURE, out, expected_month="2024-09")
    assert not out.exists()


def _xlsx(tmp_path, first_col):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Tarih", "M1", "M2"])
    ws.append([first_col[0], 100, 200])
    ws.append([first_col[1], 110, None])
    path = tmp_path / "trips.xlsx"
    wb.save(path)
    return path


EXPECTED_TRIPS = [
    {"month": "2024-10", "line": "M1", "trips": 100.0},
    {"month": "2024-10", "line": "M2", "trips": 200.0},
    {"month": "2024-11", "line": "M1", "trips": 110.0},
]


def test_load_trips_long_format(tmp_path):
    path = _xlsx(tmp_path, [datetime.date(2024, 10, 1), datetime.date(2024, 11, 1)])
    assert load_trips(path).to_dict("records") == EXPECTED_TRIPS


def test_load_trips_accepts_excel_serial_dates(tmp_path):
    path = _xlsx(tmp_path, [45566, 45597])  # 2024-10-01, 2024-11-01
    assert load_trips(path).to_dict("records") == EXPECTED_TRIPS


def _frame(rows):
    import pandas as pd

    df = pd.DataFrame(rows, columns=["date", "hour", "line", "station", "boardings"])
    df["date"] = pd.to_datetime(df["date"])
    for c in ("passengers", "b_full", "b_discount", "b_free", "b_transfer"):
        df[c] = 0
    return df


def test_complete_days_drops_thin_days():
    from metro.prep import complete_days

    df = _frame([("2024-07-01", 8, "M2", "A", 1_200_000), ("2024-08-02", 8, "M2", "A", 7_695)])
    assert [d.strftime("%Y-%m-%d") for d in complete_days(df)] == ["2024-07-01"]


def test_analysis_hourly_stops_at_july_2024():
    from metro.prep import analysis_hourly

    df = _frame([
        ("2024-07-31", 8, "M2", "A", 1_500_000),
        ("2024-08-25", 8, "M2", "A", 1_500_000),   # complete, but after the analysis window
        ("2024-07-31", 9, "34A", "X", 36),          # stray line code
        ("2024-07-30", 8, "M2", "A", 500),          # thin day
    ])
    out = analysis_hourly(df)
    assert out.date.dt.strftime("%Y-%m-%d").tolist() == ["2024-07-31"] and out.line.tolist() == ["M2"]
