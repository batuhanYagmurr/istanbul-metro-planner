"""Build app/data.json, data/station_groups.csv and data/recommendations.csv from the rail aggregate.

    python scripts/make_app_data.py --inspect   # look at the groups before naming them
    python scripts/make_app_data.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from metro.app_data import EVENT_NAME, build_app_data, recommendation_rows  # noqa: E402
from metro.calendar import load_calendar  # noqa: E402
from metro.features import FEATURE_COLS, station_features  # noqa: E402
from metro.groups import discover_groups, fit_rule, rule_agreement, rule_text  # noqa: E402
from metro.prep import analysis_hourly, load_hourly  # noqa: E402

# Named by behaviour after looking at the clusters (python scripts/make_app_data.py --inspect).
# Ids come from discover_groups (0 = largest group); recheck the means if the data change.
GROUP_NAMES = {
    0: "Morning departure",                 # am_share 0.33, weekend 0.70x weekday
    1: "All-day & weekend",                 # midday 0.36, weekend 0.85x weekday
    2: "Evening departure, quiet weekend",  # pm_share 0.52, weekend 0.49x weekday
    3: "Transfer hub",                      # transfer share 0.25
}
GROUP_RULE = (
    "If more than 23% of a station's weekday boardings are in the morning peak (07-09) and fewer than "
    "18% are transfers, it is a Morning departure station, unless over 41% fall in the evening peak "
    "(16-19), which makes it Evening departure. "
    "If the morning share is 23% or less: up to 40% in the evening peak means All-day & weekend; "
    "above 40% means Evening departure, or Transfer hub when more than 14% of boardings are transfers. "
    "Stations with a strong morning peak and more than 18% transfers are Transfer hubs when over 7% of "
    "weekday boardings come after 20:00, otherwise Morning departure."
)


def inspect(h, cal) -> None:
    f = station_features(h, cal)
    lab = discover_groups(f)
    vol = h.groupby(["line", "station"])["boardings"].sum()
    d = f.loc[lab.index].assign(group=lab)
    print(d.groupby("group")[FEATURE_COLS].mean().round(2).assign(n=d.groupby("group").size()).to_string())
    for g, x in d.groupby("group"):
        print(g, GROUP_NAMES.get(g, EVENT_NAME), "|", ", ".join(f"{l} {s}" for l, s in vol.reindex(x.index).nlargest(5).index))
    tree = fit_rule(f, lab)
    print(f"rule agreement (depth 3): {rule_agreement(tree, f, lab):.3f}")
    print(rule_text(tree))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", action="store_true")
    args = ap.parse_args()
    full = load_hourly(ROOT / "data" / "raw" / "rail_hourly")
    cal = load_calendar()
    if args.inspect:
        inspect(analysis_hourly(full), cal)
        return
    trips = pd.read_csv(ROOT / "data" / "trips_monthly.csv", dtype={"month": str})
    data = build_app_data(full, cal, trips, GROUP_NAMES, rule=GROUP_RULE)
    out = ROOT / "app" / "data.json"
    out.write_text(json.dumps(data, allow_nan=False, ensure_ascii=False, separators=(",", ":")))
    rec = recommendation_rows(data)
    rec.to_csv(ROOT / "data" / "recommendations.csv", index=False)
    sg = [{"line": l, "station": s["station"], "group": s["group"], "in_forecast": s["in_forecast"]}
          for l, d in data["lines"].items() for s in d["stations"]]
    pd.DataFrame(sg).to_csv(ROOT / "data" / "station_groups.csv", index=False)
    print(f"wrote {out} ({out.stat().st_size / 1e3:.0f} kB), {len(rec)} recommendation rows, {len(sg)} stations")


if __name__ == "__main__":
    main()
