"""Data preparation: raw IBB files -> small tidy tables."""
from __future__ import annotations

import datetime
from pathlib import Path

import duckdb
import pandas as pd

SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "rail_hourly.sql"
_EXCEL_EPOCH = datetime.date(1899, 12, 30)


def _quote(path: Path) -> str:
    return str(path).replace("'", "''")


def aggregate_rail_month(csv_path: Path, out_parquet: Path, expected_month: str | None = None) -> int:
    """Aggregate one monthly CSV to rail boardings per line, station, date, hour.

    Returns the number of rows written. If ``expected_month`` ("YYYY-MM") is given,
    every date in the file must fall in that month, otherwise nothing is written
    and ValueError is raised (the portal has at least one misnamed file).
    """
    query = SQL_PATH.read_text().format(csv_path=_quote(Path(csv_path)))
    con = duckdb.connect()
    try:
        con.execute(f"CREATE TEMP TABLE rail AS {query}")
        n, lo, hi = con.execute("SELECT count(*), min(date), max(date) FROM rail").fetchone()
        if expected_month is not None and n:
            months = {lo.strftime("%Y-%m"), hi.strftime("%Y-%m")}
            if months != {expected_month}:
                raise ValueError(
                    f"{Path(csv_path).name}: expected only {expected_month} dates, found {lo} to {hi}"
                )
        Path(out_parquet).parent.mkdir(parents=True, exist_ok=True)
        con.execute(f"COPY rail TO '{_quote(Path(out_parquet))}' (FORMAT parquet)")
        return n
    finally:
        con.close()


def load_hourly(parquet_dir: Path) -> pd.DataFrame:
    """All monthly parquet files in a directory as one frame."""
    files = sorted(Path(parquet_dir).glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"no parquet files in {parquet_dir}")
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df["hour"] = df["hour"].astype(int)
    return df


def _to_month(value) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.strftime("%Y-%m")
    if isinstance(value, (int, float)):
        return (_EXCEL_EPOCH + datetime.timedelta(days=int(value))).strftime("%Y-%m")
    return pd.Timestamp(value).strftime("%Y-%m")


def load_trips(xlsx_path: Path) -> pd.DataFrame:
    """Monthly trips per line in long format: month ("YYYY-MM"), line, trips."""
    import openpyxl

    ws = openpyxl.load_workbook(xlsx_path, data_only=True).active
    rows = ws.iter_rows(values_only=True)
    header = next(rows)
    records = []
    for row in rows:
        month = _to_month(row[0])
        if month is None:
            continue
        for line, value in zip(header[1:], row[1:]):
            if line and value not in (None, ""):
                records.append({"month": month, "line": str(line).strip(), "trips": float(value)})
    return pd.DataFrame(records, columns=["month", "line", "trips"])


def _month_range(start: str, end: str) -> list[str]:
    return [p.strftime("%Y-%m") for p in pd.period_range(start, end, freq="M")]


def select_resources(resources: list[dict], start: str, end: str, newest_first: bool = False) -> list[tuple[str, str]]:
    """Pick (month, url) for every month in start..end, matching on the file name.

    Titles are ignored on purpose: the portal's "Aralık 2024" resource is the
    file hourly_transportation_202512.csv. A month in the range with no file raises.
    """
    import re

    by_month = {}
    for res in resources:
        m = re.search(r"hourly_transportation_(\d{4})(\d{2})\.csv$", res.get("url", ""))
        if m:
            by_month[f"{m.group(1)}-{m.group(2)}"] = res["url"]
    wanted = _month_range(start, end)
    missing = [m for m in wanted if m not in by_month]
    if missing:
        raise ValueError(f"no file on the portal for: {', '.join(missing)}")
    picked = [(m, by_month[m]) for m in wanted]
    return picked[::-1] if newest_first else picked


ANALYSIS_END = "2024-07-31"
MIN_DAY_BOARDINGS = 100_000  # complete days have 1.2-3.8 million rail boardings, incomplete ones at most 7,695
STRAY_LINES = {"34A"}


def complete_days(hourly: pd.DataFrame) -> pd.DatetimeIndex:
    """Dates whose total rail boardings reach MIN_DAY_BOARDINGS (the source files have near-empty days from 2024-08)."""
    totals = hourly.groupby("date")["boardings"].sum()
    return pd.DatetimeIndex(totals[totals >= MIN_DAY_BOARDINGS].index).sort_values()


def analysis_hourly(hourly: pd.DataFrame) -> pd.DataFrame:
    """Rows usable for analysis: complete days up to ANALYSIS_END, stray line codes removed."""
    keep = hourly["date"].isin(complete_days(hourly)) & (hourly["date"] <= pd.Timestamp(ANALYSIS_END))
    keep &= ~hourly["line"].isin(STRAY_LINES)
    return hourly[keep].reset_index(drop=True)
