"""Run every backtest on the real data and write one table (CSV) so numbers are never overwritten silently.

    python scripts/run_backtests.py --tag before-review --out docs/backtests/before-review.csv
"""
from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from metro import backtest as bt  # noqa: E402
from metro.calendar import load_calendar  # noqa: E402
from metro.features import station_features  # noqa: E402
from metro.forecast import wape  # noqa: E402
from metro.groups import discover_groups  # noqa: E402
from metro.prep import STRAY_LINES, analysis_hourly, load_hourly  # noqa: E402

WINDOWS = {"main Apr-May 2024": ("2024-04-01", "2024-05-26"), "extra Jun-Jul 2024": ("2024-06-03", "2024-07-28")}
LEVELS = ["none", "station", "group"]


def _kwargs(fn, **kw):
    """Pass only the options this version of the backtest functions supports."""
    params = inspect.signature(fn).parameters
    return {k: v for k, v in kw.items() if k in params}


def run(tag: str, regroup: bool = False, closed_threshold=None) -> pd.DataFrame:
    full = load_hourly(ROOT / "data" / "raw" / "rail_hourly")
    full = full[~full["line"].isin(STRAY_LINES)]
    h = analysis_hourly(full)
    cal = load_calendar()
    groups = discover_groups(station_features(h, cal))
    opts = dict(regroup=regroup, closed_threshold=closed_threshold)
    rows = []
    for name, (s, e) in WINDOWS.items():
        for lv in LEVELS:
            r = bt.backtest_recent(h, cal, groups, start=s, end=e, level=lv, **_kwargs(bt.backtest_recent, **opts))
            for metric in ("station_day", "line_band"):
                rows.append({"test": name, "level": lv, "measure": metric,
                             "wape": r[f"{metric}_wape"], "mape": r[f"{metric}_mape"], "n_days": None})
    sp = bt.backtest_special(h, cal, groups, **_kwargs(bt.backtest_special, **opts))
    for r in sp.itertuples():
        rows.append({"test": f"special 2024: {r.special}", "level": r.level, "measure": "station_day",
                     "wape": r.station_day_wape, "mape": r.station_day_mape, "n_days": r.n_days})
    for lv in LEVELS:
        c = bt.compare_complete_days(full, cal, groups, level=lv, **_kwargs(bt.compare_complete_days, **opts))
        rows.append({"test": "complete days Aug-Oct 2024", "level": lv, "measure": "network_day",
                     "wape": wape(c["actual"], c["forecast"]), "mape": c["ape"].mean(), "n_days": len(c)})
    out = pd.DataFrame(rows)
    out.insert(0, "run", tag)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--regroup", action="store_true", help="rebuild groups from data before each cut")
    ap.add_argument("--closed-threshold", type=float, default=None)
    args = ap.parse_args()
    out = run(args.tag, args.regroup, args.closed_threshold)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False, float_format="%.4f")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
