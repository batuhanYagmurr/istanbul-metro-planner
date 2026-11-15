"""Istanbul Metro Service Planner — one-page panel. Reads only app/data.json."""
from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import model
import view

HERE = Path(__file__).resolve().parent
st.set_page_config(page_title="Istanbul Metro Service Planner", layout="wide")


@st.cache_data
def load() -> dict:
    return json.loads((HERE / "data.json").read_text())


D = load()
BT = D["meta"]["backtest"]
LINES = sorted(D["lines"], key=lambda l: (not D["lines"][l]["has_trips"], l))

st.markdown("""<style>
table.card{border-collapse:separate;border-spacing:4px;width:100%}
table.card th{font-size:12px;color:#656d76;font-weight:600;text-align:left;padding:2px 4px}
table.card td{border-radius:6px;padding:6px 8px;font-size:13px;vertical-align:top;height:58px}
table.card td.high{background:#fff1e5;color:#b35900;border:2px solid #b35900}
table.card td.low{background:#e6f4fa;color:#0b6e99;border:2px solid #0b6e99}
table.card td.typ{background:#eef0f2;color:#57606a;border:2px solid transparent}
table.card td.weak{opacity:.42;border-style:dashed}
table.card td span{font-size:11px;color:#656d76;display:block}
</style>""", unsafe_allow_html=True)

top_l, top_r = st.columns([4, 1])
with top_r:
    line = st.selectbox("Line", LINES, index=LINES.index("M2") if "M2" in LINES else 0, key="line",
                        format_func=lambda l: l if D["lines"][l]["has_trips"] else f"{l} (demand only)")
L = D["lines"][line]
with top_l:
    st.title("Istanbul Metro Service Planner")
st.markdown(f"**{view.summary_sentence(line, L)}**")
st.markdown("The service readings further down are scenarios under an assumption about how monthly trips "
            "are spread over the day; only the figures in section 1 are measured.")
st.caption("Rail boardings, Jan 2023 – Jul 2024 (IBB Open Data Portal). Source files are incomplete from August 2024.")

# 1 · measured ----------------------------------------------------------------
st.header("1 · Measured: boardings per trip")
july = next((r for r in L["monthly"] if r["month"] == "2024-07"), None)
july23 = next((r for r in L["monthly"] if r["month"] == "2023-07"), None)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Boardings / day · Jul 2024", f"{july['boardings'] / 31:,.0f}" if july else "n/a")
if L["has_trips"] and july and july["trips"]:
    bpt = july["boardings"] / july["trips"]
    c2.metric("Trips / day · Jul 2024", f"{july['trips'] / 31:,.0f}")
    c3.metric("Boardings / trip · Jul 2024", f"{bpt:,.0f}")
    if july23 and july23["trips"]:
        c4.metric("Boardings / trip vs Jul 2023", f"{(bpt / (july23['boardings'] / july23['trips']) - 1) * 100:+.0f}%")
    else:
        c4.metric("Boardings / trip vs Jul 2023", "n/a")
else:
    for c, label in ((c2, "Trips / day"), (c3, "Boardings / trip"), (c4, "Boardings / trip vs Jul 2023")):
        c.metric(label, "n/a")

mo = pd.DataFrame(L["monthly"])
if L["has_trips"]:
    mo = mo.dropna(subset=["trips"]).assign(value=lambda d: d["boardings"] / d["trips"])
    ytitle = "Boardings per trip"
else:
    mo = mo.assign(value=lambda d: d["boardings"] / pd.to_datetime(d["month"]).dt.days_in_month)
    ytitle = "Boardings per day (no trip data published)"
mo["month"] = pd.to_datetime(mo["month"])
st.altair_chart(alt.Chart(mo).mark_line(point=True).encode(
    x=alt.X("month:T", title=None), y=alt.Y("value:Q", title=ytitle, scale=alt.Scale(zero=False)),
    tooltip=[alt.Tooltip("month:T", format="%b %Y"), alt.Tooltip("value:Q", format=",.0f")]), width="stretch")
st.caption("Boardings per trip = boardings at gates ÷ trips run. It is not occupancy: exits, trip length and train "
           "size are not in the data, so compare a line with itself over time, not with other lines.")

# 2 · scenario card -------------------------------------------------------------
st.header("2 · Scenario: where load per trip is uneven within the line")
st.markdown("**Scenario** · summer, August 2024. Forecast boardings ÷ an *assumed* spread of the line's monthly "
            "trips over the day, compared with this line's own average.")
s1, s2 = st.columns(2)
peak = s1.slider("Peak-hour service vs off-peak (×)", 1.0, 2.0, 1.0, 0.25, key="peak",
                 help="Weekday 07–09 and 16–19 trips per hour relative to other hours. Hourly timetables are not published.")
wknd = s2.slider("Weekend service vs weekday (×)", 0.6, 1.0, 1.0, 0.1, key="weekend",
                 help="Saturday and Sunday trips per hour relative to weekdays.")

if L["has_trips"] and L["has_forecast"]:
    b = model.band_boardings(L["hourly"])
    t = model.trips_per_cell(L["trips_month"], L["days"], peak, wknd)
    load = model.load_index(b, t)
    labels = model.recommend(load, t)
    rob = model.robust(b, L["trips_month"], L["days"])
    html = "<table class='card'><tr><th></th>" + "".join(f"<th>{v}</th>" for v in view.BAND_NAMES.values()) + "</tr>"
    for d in model.DAY_TYPES:
        html += f"<tr><th>{view.DAY_NAMES[d]}</th>"
        for band in model.BANDS:
            c = (d, band)
            cls = view.CELL_CLASS[labels[c]] + ("" if rob[c] else " weak")
            html += (f"<td class='{cls}'>{view.CELL_TEXT[labels[c]]}"
                     f"<span>{load[c]:,.0f} per trip{' · robust' if rob[c] else ''}</span></td>")
        html += "</tr>"
    st.markdown(html + "</table>", unsafe_allow_html=True)
    n_rob = sum(rob.values())
    st.caption(f"Solid = same reading under every slider setting ({n_rob} of 18 bands); faded = changes with the "
               "assumptions. Every line shows some high and some low bands because the comparison is with the "
               "line's own average: the card shows where service looks uneven, not whether the line needs more "
               f"trips overall. Trips: {L['trips_month']:,.0f} in {L['trips_month_used']}"
               + (" (latest month published)." if L["trips_month_is_fallback"] else "."))
else:
    st.info("No trip data is published for this line — demand view only."
            if not L["has_trips"] else "Not enough history to forecast this line — demand view only.")

# charts ----------------------------------------------------------------------
left, right = st.columns(2)
with left:
    st.subheader("Hourly: forecast boardings and assumed trips")
    day = st.radio("Day type", model.DAY_TYPES, horizontal=True, key="hourly_day", format_func=view.DAY_NAMES.get)
    src = L["hourly"] if L["has_forecast"] else L["measured_hourly"]
    hb = pd.DataFrame({"hour": range(24), "boardings": src[day]})
    base = alt.Chart(hb).mark_line(interpolate="step-after", color="#1f6feb").encode(
        x=alt.X("hour:Q", title="Hour", scale=alt.Scale(domain=[0, 23])),
        y=alt.Y("boardings:Q", title="Forecast boardings per hour" if L["has_forecast"] else "Measured boardings per hour",
                axis=alt.Axis(titleColor="#1f6feb")))
    if L["has_trips"]:
        ht = pd.DataFrame({"hour": range(24), "trips": view.assumed_trips_per_hour(L, peak, wknd, day)})
        trips_line = alt.Chart(ht).mark_line(interpolate="step-after", color="#8250df", strokeDash=[5, 3]).encode(
            x="hour:Q", y=alt.Y("trips:Q", title="Assumed trips per hour (monthly total, spread by the sliders)",
                                axis=alt.Axis(titleColor="#8250df", orient="right")))
        st.altair_chart(alt.layer(base, trips_line).resolve_scale(y="independent"), width="stretch")
    else:
        st.altair_chart(base, width="stretch")
with right:
    st.subheader("Summer scenario: August 2024 by day")
    over, n = view.august_over_forecast(D)
    if L["has_forecast"]:
        dd = pd.DataFrame(L["daily"]).assign(date=lambda d: pd.to_datetime(d["date"]),
                                             day=lambda d: d["special"].replace({"none": "Normal day"}).str.replace("_", " "))
        st.altair_chart(alt.Chart(dd).mark_bar().encode(
            x=alt.X("date:T", title=None), y=alt.Y("boardings:Q", title="Forecast boardings per day"),
            color=alt.Color("day:N", legend=alt.Legend(orient="bottom", title=None)),
            tooltip=[alt.Tooltip("date:T"), alt.Tooltip("boardings:Q", format=",.0f"), "day:N"]), width="stretch")
    else:
        st.info("No forecast for this line — demand view only.")
    st.caption(f"Summer scenario. The check rests on the {n} complete August days in the source files: on those "
               f"{n} complete August days the network forecast was {over * 100:.1f}% above what happened. The "
               "school-break factor is learned from the first weeks of summer, which were busier than August. "
               f"Forecast covers {L['forecast_coverage'] * 100:.0f}% of this line's boardings.")

st.subheader("Stations on this line, by group")
stations = pd.DataFrame(L["stations"]).assign(group=lambda d: d["group"].fillna("Too new to group"))
st.altair_chart(alt.Chart(stations).mark_bar().encode(
    y=alt.Y("station:N", sort="-x", title=None), x=alt.X("boardings_day:Q", title="Boardings per day (last 8 weeks)"),
    color=alt.Color("group:N", legend=alt.Legend(orient="bottom", title=None)),
    tooltip=["station:N", "group:N", alt.Tooltip("boardings_day:Q", format=",.0f")]).properties(
    height=max(120, 18 * len(stations))), width="stretch")

with st.expander("What we can't measure"):
    st.markdown("\n".join(f"- {x}" for x in [
        "Trips are published per month only; their spread over hours and weekends is an assumption (the two sliders).",
        "Boardings are counted at gates. Exits, trip length and train size are not in the data, so boardings per trip is not occupancy.",
        "Readings are relative to each line's own average, so every line shows some high and some low bands.",
        "Source files are incomplete from August 2024 (19 complete days in Aug–Oct); the analysis stops at July 2024 and August is a summer scenario.",
        f"The school-break factor is learned from the first weeks of summer; on the {n} complete August days the forecast was {over * 100:.1f}% too high.",
        "Public holidays get one factor: Sunday holidays run above a normal Sunday and weekday holidays below a weekday, so it comes out near 1.0.",
    ] + [f"{e['line']} {e['station'].title()} is event-driven ({e['late_share'] * 100:.0f}% of weekday boardings "
         "after 20:00) and is shown as demand only." for e in D["meta"].get("event_units", [])]))
    st.markdown(f"**How stations are grouped** (matches the clustering for {D['meta']['rule_agreement'] * 100:.0f}% of stations): "
                + D["meta"]["rule"])

st.caption(f"Forecast error (backtest Apr–May 2024, boardings-weighted, station-day): **{view.error_label(D)}**. "
           f"Unweighted mean: {BT['station_day_mape'] * 100:.1f}%, inflated by closed-station days. "
           f"Special-day factors: {BT['level_used']} level. Data: IBB Open Data Portal, analysis period Jan 2023 – Jul 2024.")
