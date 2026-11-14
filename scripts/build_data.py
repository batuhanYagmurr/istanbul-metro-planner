"""Download IBB hourly public transport CSVs month by month and keep only a
small rail aggregate per month (data/raw/rail_hourly/YYYYMM.parquet).

Raw CSVs are 0.3-1.8 GB each; only one is on disk at a time unless --keep-csv
names months to keep for manual verification.

    python scripts/build_data.py --start 2023-01 --end 2024-10 --newest-first
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metro.prep import aggregate_rail_month, load_trips, select_resources  # noqa: E402

CKAN = "https://data.ibb.gov.tr/api/3/action/package_show?id="
HOURLY_ID = "hourly-public-transport-data-set"
TRIPS_ID = "rayli-sistemler-hat-bazli-sefer-sayilari"
USER_AGENT = "metro-planner-data-build/1.0"
RAW = ROOT / "data" / "raw"


def resources(package_id: str) -> list[dict]:
    req = urllib.request.Request(CKAN + package_id, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)["result"]["resources"]


def download(url: str, dest: Path) -> None:
    """Download with retries. The portal ignores range requests, so a dropped
    transfer cannot be resumed: every attempt starts from zero. curl checks the
    received size against Content-Length, so a short file is an error, not data."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    cmd = ["curl", "-sSL", "--fail", "-A", USER_AGENT, "--retry", "8",
           "--retry-delay", "15", "--retry-all-errors", "-o", str(part), url]
    for attempt in range(1, 6):
        part.unlink(missing_ok=True)
        if subprocess.run(cmd).returncode == 0:
            part.rename(dest)
            return
        print(f"  download attempt {attempt} failed, retrying", flush=True)
        time.sleep(30)
    raise RuntimeError(f"could not download {url}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="2023-01")
    ap.add_argument("--end", default="2024-10")
    ap.add_argument("--newest-first", action="store_true")
    ap.add_argument("--keep-csv", default="", help="comma-separated months (YYYY-MM) whose raw CSV is kept")
    ap.add_argument("--skip-trips", action="store_true")
    args = ap.parse_args()
    keep = {m for m in args.keep_csv.split(",") if m}

    if not args.skip_trips:
        xlsx = RAW / "trips.xlsx"
        download(resources(TRIPS_ID)[0]["url"], xlsx)
        trips = load_trips(xlsx)
        trips.to_csv(ROOT / "data" / "trips_monthly.csv", index=False)
        print(f"trips: {len(trips)} rows, {trips.month.min()} to {trips.month.max()}", flush=True)

    out_dir = RAW / "rail_hourly"
    for month, url in select_resources(resources(HOURLY_ID), args.start, args.end, args.newest_first):
        out = out_dir / f"{month.replace('-', '')}.parquet"
        csv = RAW / "csv" / Path(url).name
        if out.exists() and (month not in keep or csv.exists()):
            print(f"{month}: already built, skipping", flush=True)
            continue
        t0 = time.time()
        if not csv.exists():
            download(url, csv)
        size = csv.stat().st_size / 1e6
        rows = aggregate_rail_month(csv, out, expected_month=month)
        if month not in keep:
            csv.unlink()
        print(f"{month}: {size:.0f} MB csv -> {rows} rail rows ({time.time() - t0:.0f}s)"
              + (" [csv kept]" if month in keep else ""), flush=True)


if __name__ == "__main__":
    main()
