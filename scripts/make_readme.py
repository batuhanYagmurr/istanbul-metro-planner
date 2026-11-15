"""Write README.md. Every number in it is read from app/data.json, data/recommendations.csv,
docs/backtests/*.csv or a constant in the code; none is typed into the text.

    python scripts/make_readme.py           # write README.md
    python scripts/make_readme.py --check   # exit 1 if README.md is out of date

The prose states some directions ("fell", "beat in every test"). Each of those is checked with an
assert below, so if the data change in a way that makes a sentence false, the script stops instead
of writing it.
"""
from __future__ import annotations

import argparse
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

import pandas as pd  # noqa: E402

import model  # noqa: E402
import view  # noqa: E402
from metro.app_data import EVENT_NAME  # noqa: E402
from metro.calendar import load_calendar  # noqa: E402
from metro.features import station_features  # noqa: E402
from metro.forecast import BASELINE_DAYS, typical_profile  # noqa: E402
from metro.groups import discover_groups  # noqa: E402
from metro.prep import MIN_DAY_BOARDINGS  # noqa: E402

BACKTESTS = ROOT / "docs" / "backtests"
RUNS = {"old": "before-review", "new": "closed-0.2", "regroup": "closed-0.2-regroup"}
DAY_SHORT = {"weekday": "Weekday", "saturday": "Sat", "sunday": "Sun"}
BAND_HOURS = view.BAND_NAMES


def p1(x: float) -> str:
    """A share as a percentage with one decimal: 0.1067 -> '10.7%'."""
    return f"{x * 100:.1f}%"


def p0(x: float) -> str:
    return f"{x * 100:.0f}%"


def signed(x: float) -> str:
    return f"{x * 100:+.1f}%".replace("-", "−")


def n(x: float) -> str:
    return f"{x:,.0f}"


def default(fn, name):
    return inspect.signature(fn).parameters[name].default


def _month(line: dict, m: str) -> dict:
    return next(r for r in line["monthly"] if r["month"] == m)


def measured(d: dict) -> dict:
    rows = {}
    for name, line in d["lines"].items():
        if not line["has_trips"]:
            continue
        a, b = _month(line, "2024-07"), _month(line, "2023-07")
        if not (a["trips"] and b["trips"]):
            continue
        rows[name] = {"bpt": a["boardings"] / a["trips"] / (b["boardings"] / b["trips"]) - 1,
                      "boardings": a["boardings"] / b["boardings"] - 1, "trips": a["trips"] / b["trips"] - 1,
                      "bpt_now": a["boardings"] / a["trips"]}
    return rows


def backtest_table(runs: dict[str, pd.DataFrame], bt: dict) -> str:
    tests = [("main Apr-May 2024", "station_day", "Main: Apr–May 2024, station-day"),
             ("extra Jun-Jul 2024", "station_day", "Extra: Jun–Jul 2024, station-day"),
             ("special 2024: public_holiday", "station_day", "Public holidays 2024"),
             ("special 2024: religious_holiday", "station_day", "Religious holidays 2024"),
             ("special 2024: school_break", "station_day", "School breaks 2024"),
             ("complete days Aug-Oct 2024", "network_day", "Complete days Aug–Oct 2024, network-day")]
    out = ["| Test | Factor level | Before the review | **Now (used in the panel)** | Now, groups rebuilt before each cut | Now, unweighted MAPE |",
           "|---|---|---|---|---|---|"]
    for test, measure, label in tests:
        for i, lv in enumerate(("none", "group", "station")):
            vals = {k: r[(r.test == test) & (r.level == lv) & (r.measure == measure)].iloc[0] for k, r in runs.items()}
            nd = vals["new"]["n_days"]
            name = label + (f" ({int(nd)} days)" if pd.notna(nd) and i == 0 else "")
            out.append(f"| {name if i == 0 else ''} | {lv} | {p1(vals['old'].wape)} | **{p1(vals['new'].wape)}** | "
                       f"{p1(vals['regroup'].wape)} | {p1(vals['new'].mape)} |")
    # the "now" column must be what the panel shows
    new = runs["new"]
    for lv in ("none", "group", "station"):
        main = new[(new.test == "main Apr-May 2024") & (new.level == lv) & (new.measure == "station_day")].iloc[0]
        assert round(main.wape, 4) == bt["main"][lv]["station_day_wape"], lv
        cd = new[(new.test == "complete days Aug-Oct 2024") & (new.level == lv)].iloc[0]
        assert round(cd.wape, 4) == bt["complete_days_by_level"][lv]["wape"], lv
    return "\n".join(out)


def card_table(rec: pd.DataFrame) -> str:
    def cells(x):
        return ", ".join(f"**{DAY_SHORT[r.day_type]} {BAND_HOURS[r.band]}**" if r.robust
                         else f"{DAY_SHORT[r.day_type]} {BAND_HOURS[r.band]}" for r in x.itertuples()) or "–"
    order = {b: i for i, b in enumerate(model.BANDS)} | {d: i for i, d in enumerate(model.DAY_TYPES)}
    rec = rec.assign(o1=rec.day_type.map(order), o2=rec.band.map(order)).sort_values(["line", "o1", "o2"])
    out = ["| Line | Load per trip high | Load per trip low | Robust bands |", "|---|---|---|---|"]
    for line, x in rec.groupby("line", sort=True):
        out.append(f"| {line} | {cells(x[x.label == 'add'])} | {cells(x[x.label == 'reduce'])} | {int(x.robust.sum())} of {len(x)} |")
    return "\n".join(out)


def values() -> dict:
    d = json.loads((ROOT / "app" / "data.json").read_text())
    m, bt = d["meta"], d["meta"]["backtest"]
    rec = pd.read_csv(ROOT / "data" / "recommendations.csv")
    runs = {k: pd.read_csv(BACKTESTS / f"{v}.csv") for k, v in RUNS.items()}

    v = {}
    # period and data -------------------------------------------------------------------------
    v["data_start"], v["data_end"] = m["data_start"], m["data_end"]
    v["n_days"] = (pd.Timestamp(m["data_end"]) - pd.Timestamp(m["data_start"])).days + 1
    cdays = pd.DataFrame(bt["complete_days"]).assign(month=lambda x: x.date.str[:7])
    per_month = cdays.groupby("month").size()
    v["n_complete"] = len(cdays)
    v["complete_by_month"] = ", ".join(f"{pd.Timestamp(k + '-01'):%B} {c}" for k, c in per_month.items())
    v["last_complete_day"] = cdays.date.max()
    v["min_day"] = n(MIN_DAY_BOARDINGS)
    lines = d["lines"]
    v["n_lines"] = len(lines)
    v["n_trip_lines"] = sum(x["has_trips"] for x in lines.values())
    v["demand_only_lines"] = ", ".join(sorted(k for k, x in lines.items() if not x["has_trips"]))
    v["n_units"] = sum(len(x["stations"]) for x in lines.values())

    # groups ------------------------------------------------------------------------------------
    groups = [g for g in d["groups"] if g["name"] != EVENT_NAME]
    v["n_groups"] = len(groups)
    v["n_grouped"] = sum(g["n_stations"] for g in d["groups"])
    v["n_ungrouped"] = v["n_units"] - v["n_grouped"]
    v["group_list"] = "\n".join(f"| {g['name']} | {g['n_stations']} | {', '.join(g['examples'])} |" for g in groups)
    v["rule"], v["rule_agreement"] = m["rule"], p0(m["rule_agreement"])
    v["min_months"] = default(station_features, "min_months")
    v["min_size"] = default(discover_groups, "min_size")
    ks = default(discover_groups, "k_values")
    v["k_range"] = f"{min(ks)}–{max(ks)}"
    ev = m["event_units"]
    assert len(ev) == 1
    v["event_station"] = "M9 Olimpiyat Doğu" if ev[0]["station"] == "OLIMPIYAT DOGU" else f"{ev[0]['line']} {ev[0]['station']}"
    v["event_late"] = p0(ev[0]["late_share"])

    # forecast and backtests -------------------------------------------------------------------
    v["n_weeks"] = default(typical_profile, "n_weeks")
    v["baseline_days"] = BASELINE_DAYS
    v["closed_pct"] = p0(m["closed_threshold"])
    v["error"] = view.error_label(d)
    assert v["error"] == p1(bt["station_day_wape"])
    v["error_mape"] = p1(bt["station_day_mape"])
    v["error_line_band"] = p1(bt["line_band_wape"])
    v["level_used"] = bt["level_used"]
    assert v["level_used"] == "station"          # the text says the headline factors do not use the groups
    v["n_special_days"] = int(pd.DataFrame(bt["special"]).groupby("special").n_days.first().sum())
    a, b = (pd.Timestamp(x) for x in bt["window"].split(".."))
    v["main_window"] = f"{a:%-d %B} – {b:%-d %B %Y}"
    v["extra_error"] = p1(bt["extra"][bt["level_used"]]["station_day_wape"])
    sp = pd.DataFrame(bt["special"]).pivot(index="special", columns="level", values="station_day_wape")
    v["rel_station"], v["rel_group"], v["rel_none"] = (p1(sp.at["religious_holiday", k]) for k in ("station", "group", "none"))
    blocks = [bt["main"], {k: bt["extra"][k] for k in ("none", "station", "group")}]
    station_beats_group = (all(sp.station < sp.group) and all(b["station"]["station_day_wape"] < b["group"]["station_day_wape"] for b in blocks)
                           and bt["complete_days_by_level"]["station"]["wape"] < bt["complete_days_by_level"]["group"]["wape"])
    group_beats_none = all(sp.group < sp["none"]) and all(b["group"]["station_day_wape"] < b["none"]["station_day_wape"] for b in blocks)
    assert station_beats_group and group_beats_none, "the 'groups do not improve the forecast' section no longer matches the data"
    rg = runs["regroup"][runs["regroup"].measure != "line_band"]
    assert all(rg[(rg.test == t) & (rg.level == "station")].wape.item() < rg[(rg.test == t) & (rg.level == "group")].wape.item()
               for t in rg.test.unique()), "station no longer beats group with regrouping"
    v["main_none"], v["main_group"], v["main_station"] = (p1(bt["main"][k]["station_day_wape"]) for k in ("none", "group", "station"))
    v["n_tests"] = len(sp) + len(blocks) + 1
    v["complete_wape"] = p1(bt["complete_days_wape"])
    v["complete_mape"] = p1(bt["complete_days_mape"])
    over, n_aug = view.august_over_forecast(d)
    assert over > 0
    v["aug_over"], v["n_aug"] = p1(over), n_aug
    oct_ = cdays[cdays.month == "2024-10"]
    v["oct_wape"] = p1((oct_.forecast - oct_.actual).abs().sum() / oct_.actual.sum())
    v["n_oct"] = len(oct_)

    # regrouping / closed-day sensitivity ---------------------------------------------------------
    key = ["test", "level", "measure"]
    old = runs["old"].set_index(key).wape
    v["regroup_max"] = f"{(runs['regroup'].set_index(key).wape - runs['new'].set_index(key).wape).abs().max() * 100:.1f}"
    v["closed_max"] = f"{(runs['new'].set_index(key).wape - old).abs().max() * 100:.1f}"
    v["backtest_table"] = backtest_table(runs, bt)

    # measured ---------------------------------------------------------------------------------
    ms = measured(d)
    v["n_measured"] = len(ms)
    v["n_up"] = sum(r["bpt"] > 0 for r in ms.values())
    assert 0 < v["n_up"] < v["n_measured"]
    m1, m2, t1 = ms["M1"], ms["M2"], ms["T1"]
    assert m1["trips"] < m1["boardings"] < 0 < m1["bpt"] and m2["bpt"] < 0 and t1["bpt"] < 0
    v["m1_trips"], v["m1_b"], v["m1_bpt"] = p1(-m1["trips"]), p1(-m1["boardings"]), p1(m1["bpt"])
    v["m2_bpt"], v["t1_bpt"] = signed(m2["bpt"]), signed(t1["bpt"])
    v["m1_now"], v["m2_now"] = n(m1["bpt_now"]), n(m2["bpt_now"])
    big = sorted(ms, key=lambda k: abs(ms[k]["bpt"]), reverse=True)[:3]
    assert all(ms[k]["boardings"] > ms[k]["trips"] for k in big)     # "driven by boardings" below
    v["big_moves"] = ", ".join(f"{k} ({signed(ms[k]['bpt'])})" for k in big[:-1]) + f" and {big[-1]} ({signed(ms[big[-1]]['bpt'])})"
    v["big_boardings"] = ", ".join(signed(ms[k]["boardings"]) for k in big)
    v["big_trips"] = ", ".join(signed(ms[k]["trips"]) for k in big)
    cal = load_calendar()
    jul = cal[cal.date.dt.strftime("%Y-%m").isin(["2023-07", "2024-07"]) & cal.special.isin(["religious_holiday", "public_holiday"])]
    rel = jul[jul.special == "religious_holiday"]
    pub = jul[jul.special == "public_holiday"]
    assert len(rel) == 1 and rel.date.dt.year.item() == 2023 and len(pub) == 2 and pub.date.dt.day.nunique() == 1
    v["jul_rel"] = f"{rel.date.item():%-d %B %Y} ({rel.label.item().replace(' day ', ', day ')}, a {rel.day_type.item().title()})"
    p23, p24 = (pub[pub.date.dt.year == y].iloc[0] for y in (2023, 2024))
    v["jul_pub"] = (f"{p23.date:%-d July}, a public holiday, fell on a {p23.date:%A} in 2023 and a {p24.date:%A} in 2024")

    # card -------------------------------------------------------------------------------------
    v["add_at"], v["reduce_at"] = f"{m['add_at']:g}", f"{m['reduce_at']:g}"
    v["peak_lo"], v["peak_hi"] = f"{min(model.PEAK_GRID):g}", f"{max(model.PEAK_GRID):g}"
    v["wk_lo"], v["wk_hi"] = f"{min(model.WEEKEND_GRID):g}", f"{max(model.WEEKEND_GRID):g}"
    v["n_combos"] = len(model.PEAK_GRID) * len(model.WEEKEND_GRID)
    v["n_card_lines"] = rec.line.nunique()
    v["n_cells"], v["n_robust"], v["robust_pct"] = len(rec), int(rec.robust.sum()), p0(rec.robust.mean())
    peaks = rec[(rec.day_type == "weekday") & rec.band.isin(model.PEAK_BANDS)]
    peak_high = peaks[peaks.label == "add"]
    assert peak_high.robust.sum() == 0
    v["n_peak_high"], v["n_peak_cells"] = len(peak_high), len(peaks)
    v["n_peak_lines"] = peak_high.line.nunique()
    rh = rec[rec.robust & (rec.label == "add")]
    rl = rec[rec.robust & (rec.label == "reduce")]
    v["n_rob_high"], v["n_rob_low"] = len(rh), len(rl)
    sat_pm = rh[(rh.day_type == "saturday") & (rh.band == "pm_peak")]
    assert len(sat_pm) == rh.groupby(["day_type", "band"]).size().max()
    v["sat_pm_lines"] = sat_pm.line.nunique()
    early = rl[rl.band == "early"]
    assert len(early) == rl.groupby("band").size().max()
    v["n_rob_low_early"] = len(early)
    v["card_table"] = card_table(rec)
    return v


TEMPLATE = """# Istanbul Metro Service Planner

**On which Istanbul rail line, and in which hours, is the load per trip uneven — where could service be added or reduced?**

Using the IBB Open Data Portal's hourly boardings ({data_start} to {data_end}, {n_days} days, {n_lines} rail lines) and the monthly trips each line ran, this project measures boardings per trip by line and month. It then groups {n_grouped} stations by when people board, forecasts August 2024 (a summer scenario) with a typical-week profile and special-day factors, and reads each line's 18 day-type × time bands against the line's own average. The forecast misses by **{error}** of boardings (weighted error, April–May 2024 backtest). The clearest result is negative. Weekday rush hours read "load per trip high" on {n_peak_lines} of the {n_card_lines} lines with trip data, but that reading depends entirely on an assumption about how trips are spread over the day, which IBB does not publish. The readings that hold under every assumption are mostly busy Saturday afternoons (16–19) and quiet 06:00 hours.

Live app: [https://appapppy-frrvdz2txlxxaxbbtxorew.streamlit.app](https://appapppy-frrvdz2txlxxaxbbtxorew.streamlit.app)

![Panel, section 1 for line M2: a one-sentence measured finding, four tiles for July 2024 and the monthly boardings-per-trip trend since January 2023](docs/panel1.png)
*Measured: the selected line's boardings per trip, July 2024 against July 2023, and the month-by-month trend.*

![Panel, section 2 for line M2: the two assumption sliders above a 3 × 6 grid of day types and time bands; robust bands are solid, assumption-dependent ones faded with a dashed border; below, hourly forecast boardings with assumed trips on a separate axis, and August 2024 forecast by day with special days coloured](docs/panel2.png)
*Scenario: where load per trip is high or low within the line, how it shifts with the sliders, and the August summer forecast.*

![Panel, the busiest M2 station units as horizontal bars of boardings per day, coloured by station group, with every station name shown](docs/panel3.png)
*The line's busiest stations by daily boardings, coloured by behaviour group.*

## What we found

1. **Boardings per trip moved both ways between July 2023 and July 2024.** It rose on {n_up} of the {n_measured} lines with trip data. On M1, trips fell {m1_trips} and boardings fell {m1_b}, so each trip carried {m1_bpt} more ({m1_now} boardings per trip). On M2 ({m2_bpt}, now {m2_now}) and T1 ({t1_bpt}) it fell. This is measured and needs no assumption. The largest moves were {big_moves}, driven by boardings ({big_boardings}) more than by trips ({big_trips}). Whether they come from line extensions or from a break in the data has not been checked. The two months are not like for like: July 2023 includes {jul_rel}, and {jul_pub}.
2. **Weekday rush-hour readings are not robust.** At base assumptions {n_peak_high} of the {n_peak_cells} weekday peak bands (07–09, 16–19) read "load per trip high", and none of them survives the sensitivity test: once peak hours are assumed to get more trips, the reading goes. Of {n_cells} line-bands, {n_robust} ({robust_pct}) give the same reading under all {n_combos} assumption combinations. The robust "high" readings ({n_rob_high}) are mostly Saturday 16–19 ({sat_pm_lines} lines); the robust "low" readings ({n_rob_low}) are mostly the 06:00 hour ({n_rob_low_early}).
3. **The forecast misses by {error} of boardings** (April–May 2024, station-day, weighted) and {extra_error} in June–July, when summer starts. Over the {n_complete} complete days after the cut it misses by {complete_wape}. On the {n_aug} complete August days it ran **{aug_over} above** what happened, so the August summer scenario is on the high side.
4. **Grouping stations does not improve the forecast.** The groups are clear and easy to describe, but station-level special-day factors beat group-level ones in all {n_tests} tests (see below).
5. **{event_station} is event-driven.** {event_late} of its weekday boardings fall after 20:00. It is its own outlier in the clustering and gets no factor and no forecast; the panel shows it as demand only.

## Where load per trip looks uneven (August 2024, base assumptions)

Each line is compared with its own average, not with other lines. **Bold** = robust (same reading under every slider setting); plain = depends on the assumptions. "Weekday" covers Monday–Friday; hours are start hours (07–09 = 07:00–09:59).

{card_table}

The full card, with boardings and assumed trips per band, is in [`data/recommendations.csv`](data/recommendations.csv).

## How it works

1. **Data prep (SQL).** Each monthly CSV is reduced with one DuckDB query ([`sql/rail_hourly.sql`](sql/rail_hourly.sql)) to rail boardings per line, station, date and hour, plus fare-type and transfer counts. The raw CSV is then deleted. A day counts as complete when it has at least {min_day} rail boardings.
2. **Measured indicator.** Monthly boardings ÷ monthly trips per line (trips file: IBB "Rayli sistemler hat bazli sefer sayilari").
3. **Station groups.** The unit is a line–station pair, i.e. one station's gates for one line. Each unit gets seven features from normal days: weekend/weekday ratio, the weekday shares of 07–09, 10–15, 16–19 and 20–05, and the discounted-fare and transfer shares. K-means on the standardized features chooses k from {k_range} by silhouette score. A cluster under {min_size} stations is an outlier, and units with under {min_months} months of data are not grouped ({n_ungrouped} units). The result is {n_groups} groups plus one outlier. A depth-3 decision tree turns them into a rule that matches the clusters for {rule_agreement} of stations.
4. **Forecast.** Typical profile × special-day factor. The profile is the mean boardings by day type and hour over the {n_weeks} normal weeks before the cut, leaving out closed-station days (below {closed_pct} of the station's own median for that day type). A factor is the median of actual ÷ the {baseline_days}-day same-day-type average on earlier public holidays, religious holidays and school-break days. Factors were tried per station, per group and not at all. The level was chosen on the 2024 special-day backtest ({n_special_days} days; lowest boardings-weighted error, each category weighted by its number of days), which chose **{level_used}**. The headline {error} comes from a separate window, the {main_window} backtest, scored with that level. Profiles and factors use only data before each cut. Two inputs come from the whole analysis period ({data_start} to {data_end}) instead: which units are eligible (at least {min_months} months of data) and the setting-aside of {event_station} as an outlier, both from the clustering. The {level_used}-level factors behind the headline do not use the groups, and rebuilding the groups from data before each cut moves the error by at most {regroup_max} points (the "groups rebuilt" column below).
5. **Card.** August forecast boardings per band ÷ an assumed share of the line's monthly trips. The base assumption is the same trips every operating hour, every day. A band at least {add_at}× the line's trip-weighted average reads *load per trip high*; one at most {reduce_at}× reads *low*. The sliders set weekday peak service to {peak_lo}–{peak_hi}× and weekend service to {wk_lo}–{wk_hi}×, and a reading is **robust** if it is the same at all {n_combos} combinations. The thresholds were set before the results were seen and have not been changed.

| Group | Stations | Busiest examples |
|---|---|---|
{group_list}

**Rule:** {rule}

The analysis runs end to end in [`analysis.ipynb`](analysis.ipynb).

## Backtests: before and after the review

The headline error is **WAPE** = Σ|actual − forecast| ÷ Σ actual, weighted by boardings. The unweighted mean (MAPE) is given too. It is much larger, {error_mape} for the main backtest, because small stations and closed-station days (e.g. stations shut on 1 May) count as much as busy ones. Station-day errors include hours 0–5; the line-band error for the card's hours (06–23) is {error_line_band}.

An external review asked for three changes: stricter leakage tests, groups rebuilt from data before each cut, and closed-station days left out of profiles and baselines. The table shows the numbers before and after. No run was overwritten; every run is its own CSV in [`docs/backtests/`](docs/backtests/), with notes in [`docs/backtests/README.md`](docs/backtests/README.md). Leaving out closed days moved WAPE by at most {closed_max} points, and rebuilding groups by at most {regroup_max} points.

{backtest_table}

## Groups do not improve the forecast

This was a hypothesis, and the backtests rejected it. Special days are rare, so pooling stations into groups should give steadier special-day factors than each station's own few holidays. Group factors do beat using no factor at all (main backtest: {main_group} against {main_none}). But each station's own factor beats the group factor in every test: {main_station} against {main_group} in April–May, and on religious holidays {rel_station} against {rel_group} (no factor: {rel_none}). The same holds with groups rebuilt before each cut. Stations within a group still differ too much on special days for pooling to help. The panel therefore uses station-level factors, and the groups serve only to describe the stations.

## What we can't measure

- **Trips by hour.** IBB publishes trips per line per month only. How they are spread over hours and weekends is an assumption, which is what the two sliders change.
- **Occupancy.** Boardings are counted at the gates. Exits, trip length and train size (number of cars) are not in the data, so boardings per trip is not occupancy, and lines are not compared with each other.
- **Relative readings.** Each band is compared with its own line's average, so every line shows some high and some low bands. The card shows where service looks uneven within a line, not whether the line as a whole needs more or fewer trips.
- **The source data break.** From August 2024 most days in IBB's hourly files are nearly empty, for buses and ferries as well as rail. Only {n_complete} complete days remain in August–October 2024 ({complete_by_month}). The analysis therefore stops at {data_end}, and August 2024 is a **summer scenario** checked against those days.
- **The summer factor.** The school-break factor is learned from the first weeks of summer, which were busier than August. On the {n_aug} complete August days the forecast ran {aug_over} high; by October ({n_oct} days) it was within {oct_wape}.
- **Public holidays.** There is one public-holiday factor, not one per day type. Sunday holidays run above a normal Sunday and weekday holidays below a weekday, so the factor comes out near 1. The 2024 test has few public-holiday days.
- **Event traffic.** {event_station} depends on events at the Olympic stadium and cannot be forecast from the calendar.
- **Scaling.** The features are standardized over all eligible units, including the outlier {event_station}, before k-means, so that one station shifts the scaling slightly.
- **Hours 0–5.** These are in the station-day error but not on the card.

## What's in this repo

| Path | What |
|---|---|
| `analysis.ipynb` | The whole analysis, rerunnable; checks its numbers against `app/data.json` |
| `sql/rail_hourly.sql` | The data-prep query |
| `metro/` | Prep, features, groups, forecast, backtests, app data |
| `app/` | Streamlit panel (`streamlit_app.py`), card formulas (`model.py`), panel text (`view.py`), `data.json` |
| `scripts/` | `build_data.py` (download → parquet), `make_app_data.py`, `run_backtests.py`, `make_calendar.py`, `make_readme.py` |
| `data/` | Calendar of special days, trips per month, station groups, card readings |
| `docs/` | Data notes, backtest runs, design and plan |
| `tests/` | pytest suite, including a check that this README matches the data |

## Run it yourself

Needs Python 3.10 or newer (tested on 3.12; current Streamlit releases do not install on 3.9).

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/build_data.py        # downloads the monthly CSVs one at a time; large and slow
python scripts/make_app_data.py     # parquet -> app/data.json, data/*.csv
python scripts/make_readme.py       # app/data.json + docs/backtests -> README.md
streamlit run app/streamlit_app.py
```

The panel alone needs only `pip install -r app/requirements.txt` and reads only `app/data.json`. The notebook needs the parquet files from `build_data.py` (run it from the repo root).

## Data source and licence

[IBB Open Data Portal](https://data.ibb.gov.tr) (Istanbul Metropolitan Municipality), under the IBB Open Data Licence. Datasets: [hourly public transport data](https://data.ibb.gov.tr/dataset/hourly-public-transport-data-set) and [monthly trips per rail line](https://data.ibb.gov.tr/dataset/rayli-sistemler-hat-bazli-sefer-sayilari). The special-day calendar (`data/calendar.csv`) and its sources are described in [`docs/data-notes.md`](docs/data-notes.md).

**Data notes.** On the portal, the resource titled "Aralık 2024" (December 2024) is the file `hourly_transportation_202512.csv`. Like November 2024, it has a header and no rows, so the hourly data ends in October 2024 (last complete day {last_complete_day}). The monthly files shrink sharply from August 2024 because most days in them are nearly empty, not because the rows became less detailed. `build_data.py` matches files by name and checks every date against the expected month. Raw-file totals, checked against the aggregate, are in [`docs/data-notes.md`](docs/data-notes.md).
"""


def render() -> str:
    return TEMPLATE.format(**values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text = render()
    path = ROOT / "README.md"
    if args.check:
        sys.exit(0 if path.exists() and path.read_text() == text else 1)
    path.write_text(text)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
