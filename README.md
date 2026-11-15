# Istanbul Metro Service Planner

**On which Istanbul rail line, and in which hours, is the load per trip uneven — where could service be added or reduced?**

Using the IBB Open Data Portal's hourly boardings (2023-01-01 to 2024-07-31, 578 days, 23 rail lines) and the monthly trips each line ran, this project measures boardings per trip by line and month. It then groups 321 stations by when people board, forecasts August 2024 (a summer scenario) with a typical-week profile and special-day factors, and reads each line's 18 day-type × time bands against the line's own average. The forecast misses by **10.7%** of boardings (weighted error, April–May 2024 backtest). The clearest result is negative. Weekday rush hours read "load per trip high" on 16 of the 17 lines with trip data, but that reading depends entirely on an assumption about how trips are spread over the day, which IBB does not publish. The readings that hold under every assumption are mostly busy Saturday afternoons (16–19) and quiet 06:00 hours.

Live app: not deployed yet

> **Screenshot placeholder** — panel screenshot goes here (`docs/panel.png`).

## What we found

1. **Boardings per trip moved both ways between July 2023 and July 2024.** It rose on 11 of the 17 lines with trip data. On M1, trips fell 13.9% and boardings fell 8.4%, so each trip carried 6.4% more (546 boardings per trip). On M2 (−5.0%, now 654) and T1 (−7.6%) it fell. This is measured and needs no assumption.
2. **Weekday rush-hour readings are not robust.** At base assumptions 26 of the 34 weekday peak bands (07–09, 16–19) read "load per trip high", and none of them survives the sensitivity test: once peak hours are assumed to get more trips, the reading goes. Of 306 line-bands, 181 (59%) give the same reading under all 25 assumption combinations. The robust "high" readings (35) are mostly Saturday 16–19 (16 lines); the robust "low" readings (78) are mostly the 06:00 hour (43).
3. **The forecast misses by 10.7% of boardings** (April–May 2024, station-day, weighted) and 15.2% in June–July, when summer starts. Over the 19 complete days after the cut it misses by 10.6%. On the 6 complete August days it ran **18.6% above** what happened, so the August summer scenario is on the high side.
4. **Grouping stations does not improve the forecast.** The groups are clear and easy to describe, but station-level special-day factors beat group-level ones in all 6 tests (see below).
5. **M9 Olimpiyat Doğu is event-driven.** 96% of its weekday boardings fall after 20:00. It is its own outlier in the clustering and gets no factor and no forecast; the panel shows it as demand only.

## Where load per trip looks uneven (August 2024, base assumptions)

Each line is compared with its own average, not with other lines. **Bold** = robust (same reading under every slider setting); plain = depends on the assumptions. "Weekday" covers Monday–Friday; hours are start hours (07–09 = 07:00–09:59).

| Line | Load per trip high | Load per trip low | Robust bands |
|---|---|---|---|
| F1 | Weekday 16–19, **Sat 16–19**, **Sat 20–21**, **Sun 16–19** | **Weekday 06**, **Sat 06**, **Sat 07–09**, **Sun 06**, **Sun 07–09** | 10 of 18 |
| F4 | Weekday 16–19, **Sat 16–19**, **Sat 20–21**, **Sun 16–19**, **Sun 20–21** | **Weekday 06**, **Weekday 07–09**, **Sat 06**, **Sat 07–09**, **Sun 06**, **Sun 07–09** | 11 of 18 |
| M1 | Weekday 07–09, Weekday 16–19, **Sat 16–19** | Weekday 06, **Sat 06**, **Sun 06**, Sun 07–09 | 8 of 18 |
| M2 | Weekday 07–09, Weekday 16–19, **Sat 16–19** | **Weekday 06**, **Sat 06**, **Sun 06**, **Sun 07–09** | 11 of 18 |
| M3 | Weekday 07–09, Weekday 16–19 | **Weekday 22–23**, **Sat 06**, Sat 22–23, **Sun 06**, Sun 07–09, Sun 22–23 | 7 of 18 |
| M4 | Weekday 07–09, Weekday 16–19, **Sat 16–19** | Weekday 22–23, **Sat 06**, **Sun 06**, Sun 07–09 | 8 of 18 |
| M5 | Weekday 07–09, Weekday 16–19, **Sat 16–19** | **Weekday 06**, **Sat 06**, **Sun 06**, **Sun 07–09** | 11 of 18 |
| M6 | Weekday 16–19, **Sat 16–19**, **Sun 16–19** | **Weekday 06**, **Sat 06**, **Sun 06**, **Sun 07–09** | 12 of 18 |
| M7 | Weekday 07–09, Weekday 16–19, **Sat 16–19** | Weekday 22–23, Sat 06, **Sun 06**, Sun 07–09 | 7 of 18 |
| M8 | Weekday 07–09, Weekday 16–19, **Sat 16–19** | **Weekday 06**, **Weekday 22–23**, **Sat 06**, Sat 22–23, **Sun 06**, Sun 07–09, Sun 22–23 | 9 of 18 |
| M9 | Weekday 07–09, Weekday 16–19, **Sat 16–19**, **Sun 16–19** | Sat 06, **Sun 06**, **Sun 07–09** | 10 of 18 |
| T1 | Weekday 07–09, Weekday 10–15, Weekday 16–19, **Sat 10–15**, **Sat 16–19** | **Weekday 06**, **Weekday 22–23**, **Sat 06**, **Sun 06**, **Sun 07–09**, Sun 22–23 | 12 of 18 |
| T3 | **Weekday 10–15**, Weekday 16–19, **Sat 10–15**, **Sat 16–19**, **Sun 10–15**, **Sun 16–19** | **Weekday 06**, Weekday 20–21, **Weekday 22–23**, **Sat 06**, **Sat 07–09**, Sat 20–21, **Sat 22–23**, **Sun 06**, **Sun 07–09**, **Sun 20–21**, **Sun 22–23** | 14 of 18 |
| T4 | Weekday 07–09, Weekday 16–19, **Sat 16–19** | **Weekday 22–23**, **Sat 06**, **Sun 06**, **Sun 07–09**, Sun 22–23 | 9 of 18 |
| T5 | Weekday 16–19, **Sat 16–19**, **Sun 16–19** | **Weekday 06**, **Weekday 22–23**, **Sat 06**, **Sun 06**, **Sun 07–09** | 12 of 18 |
| TF1 | Weekday 16–19, **Sat 16–19**, **Sun 16–19** | **Weekday 06**, **Weekday 07–09**, **Weekday 20–21**, **Weekday 22–23**, **Sat 06**, **Sat 07–09**, **Sat 20–21**, **Sat 22–23**, **Sun 06**, **Sun 07–09**, **Sun 20–21**, **Sun 22–23** | 15 of 18 |
| TF2 | **Sat 10–15**, **Sat 16–19**, **Sat 20–21**, **Sun 10–15**, **Sun 16–19**, **Sun 20–21** | **Weekday 06**, **Weekday 07–09**, **Weekday 22–23**, **Sat 06**, **Sat 22–23**, **Sun 06**, Sun 22–23 | 15 of 18 |

The full card, with boardings and assumed trips per band, is in [`data/recommendations.csv`](data/recommendations.csv).

## How it works

1. **Data prep (SQL).** Each monthly CSV is reduced with one DuckDB query ([`sql/rail_hourly.sql`](sql/rail_hourly.sql)) to rail boardings per line, station, date and hour, plus fare-type and transfer counts. The raw CSV is then deleted. A day counts as complete when it has at least 100,000 rail boardings.
2. **Measured indicator.** Monthly boardings ÷ monthly trips per line (trips file: IBB "Rayli sistemler hat bazli sefer sayilari").
3. **Station groups.** The unit is a line–station pair, i.e. one station's gates for one line. Each unit gets seven features from normal days: weekend/weekday ratio, the weekday shares of 07–09, 10–15, 16–19 and 20–05, and the discounted-fare and transfer shares. K-means on the standardized features chooses k from 4–6 by silhouette score. A cluster under 5 stations is an outlier, and units with under 12 months of data are not grouped (62 units). The result is 4 groups plus one outlier. A depth-3 decision tree turns them into a rule that matches the clusters for 83% of stations.
4. **Forecast.** Typical profile × special-day factor. The profile is the mean boardings by day type and hour over the 8 normal weeks before the cut, leaving out closed-station days (below 20% of the station's own median for that day type). A factor is the median of actual ÷ the 28-day same-day-type average on earlier public holidays, religious holidays and school-break days. Factors were tried per station, per group and not at all; the backtests chose **station**. Only data before each cut is used: profiles, factors, and the groups too, when they are rebuilt.
5. **Card.** August forecast boardings per band ÷ an assumed share of the line's monthly trips. The base assumption is the same trips every operating hour, every day. A band at least 1.25× the line's trip-weighted average reads *load per trip high*; one at most 0.6× reads *low*. The sliders set weekday peak service to 1–2× and weekend service to 0.6–1×, and a reading is **robust** if it is the same at all 25 combinations. The thresholds were set before the results were seen and have not been changed.

| Group | Stations | Busiest examples |
|---|---|---|
| Morning departure | 147 | MARMARAY USKUDAR-2, M5 CARSI, M5 UMRANIYE, M1 BAGCILAR MEYDAN, MARMARAY ZEYTINBURNU |
| All-day & weekend | 73 | M1 ATAKOY, T1 SIRKECI, T1 SULTANAHMET, MARMARAY PENDIK, MARMARAY BAKIRKOY-2 |
| Evening departure, quiet weekend | 51 | M2 OSMANBEY KUZEY, M2 LEVENT 2 KUZEY, M2 ITU GUNEY, MARMARAY FENERYOLU, M4 YENISAHRA |
| Transfer hub | 49 | M1 YENIKAPI, M5 USKUDAR 1, M2 GAYRETTEPE, M4 AYRILIKCESME, T1 ZEYTINBURNU 2 |

**Rule:** If more than 23% of a station's weekday boardings are in the morning peak (07-09) and fewer than 18% are transfers, it is a Morning departure station, unless over 41% fall in the evening peak (16-19), which makes it Evening departure. If the morning share is 23% or less: up to 40% in the evening peak means All-day & weekend; above 40% means Evening departure, or Transfer hub when more than 14% of boardings are transfers. Stations with a strong morning peak and more than 18% transfers are Transfer hubs when over 7% of weekday boardings come after 20:00, otherwise Morning departure.

The analysis runs end to end in [`analysis.ipynb`](analysis.ipynb).

## Backtests: before and after the review

The headline error is **WAPE** = Σ|actual − forecast| ÷ Σ actual, weighted by boardings. The unweighted mean (MAPE) is given too. It is much larger, 79.6% for the main backtest, because small stations and closed-station days (e.g. stations shut on 1 May) count as much as busy ones. Station-day errors include hours 0–5; the line-band error for the card's hours (06–23) is 11.0%.

An external review asked for three changes: stricter leakage tests, groups rebuilt from data before each cut, and closed-station days left out of profiles and baselines. The table shows the numbers before and after. No run was overwritten; every run is its own CSV in [`docs/backtests/`](docs/backtests/), with notes in [`docs/backtests/README.md`](docs/backtests/README.md). Leaving out closed days moved WAPE by at most 0.1 points, and rebuilding groups by at most 0.8 points.

| Test | Factor level | Before the review | **Now (used in the panel)** | Now, groups rebuilt before each cut | Now, unweighted MAPE |
|---|---|---|---|---|---|
| Main: Apr–May 2024, station-day | none | 12.6% | **12.6%** | 12.5% | 77.7% |
|  | group | 11.6% | **11.6%** | 11.4% | 81.9% |
|  | station | 10.7% | **10.7%** | 10.6% | 79.6% |
| Extra: Jun–Jul 2024, station-day | none | 23.1% | **23.1%** | 23.2% | 31.9% |
|  | group | 15.9% | **15.8%** | 15.8% | 22.6% |
|  | station | 15.2% | **15.2%** | 15.2% | 19.9% |
| Public holidays 2024 (5 days) | none | 37.2% | **37.2%** | 37.1% | 748.2% |
|  | group | 36.8% | **36.7%** | 36.2% | 824.1% |
|  | station | 33.3% | **33.2%** | 33.0% | 806.8% |
| Religious holidays 2024 (9 days) | none | 50.0% | **50.0%** | 50.2% | 86.4% |
|  | group | 32.0% | **31.9%** | 31.1% | 47.6% |
|  | station | 23.7% | **23.6%** | 23.3% | 27.0% |
| School breaks 2024 (40 days) | none | 21.1% | **21.1%** | 21.2% | 109.2% |
|  | group | 10.9% | **10.8%** | 10.8% | 93.5% |
|  | station | 9.7% | **9.6%** | 9.6% | 90.2% |
| Complete days Aug–Oct 2024, network-day (19 days) | none | 15.2% | **15.3%** | 15.3% | 16.5% |
|  | group | 10.7% | **10.7%** | 10.7% | 11.9% |
|  | station | 10.5% | **10.6%** | 10.6% | 11.8% |

## Groups do not improve the forecast

This was a hypothesis, and the backtests rejected it. Special days are rare, so pooling stations into groups should give steadier special-day factors than each station's own few holidays. Group factors do beat using no factor at all (main backtest: 11.6% against 12.6%). But each station's own factor beats the group factor in every test: 10.7% against 11.6% in April–May, and on religious holidays 23.6% against 31.9% (no factor: 50.0%). The same holds with groups rebuilt before each cut. Stations within a group still differ too much on special days for pooling to help. The panel therefore uses station-level factors, and the groups serve only to describe the stations.

## What we can't measure

- **Trips by hour.** IBB publishes trips per line per month only. How they are spread over hours and weekends is an assumption, which is what the two sliders change.
- **Occupancy.** Boardings are counted at the gates. Exits, trip length and train size (number of cars) are not in the data, so boardings per trip is not occupancy, and lines are not compared with each other.
- **Relative readings.** Each band is compared with its own line's average, so every line shows some high and some low bands. The card shows where service looks uneven within a line, not whether the line as a whole needs more or fewer trips.
- **The source data break.** From August 2024 most days in IBB's hourly files are nearly empty, for buses and ferries as well as rail. Only 19 complete days remain in August–October 2024 (August 6, September 8, October 5). The analysis therefore stops at 2024-07-31, and August 2024 is a **summer scenario** checked against those days.
- **The summer factor.** The school-break factor is learned from the first weeks of summer, which were busier than August. On the 6 complete August days the forecast ran 18.6% high; by October (5 days) it was within 1.1%.
- **Public holidays.** There is one public-holiday factor, not one per day type. Sunday holidays run above a normal Sunday and weekday holidays below a weekday, so the factor comes out near 1. The 2024 test has few public-holiday days.
- **Event traffic.** M9 Olimpiyat Doğu depends on events at the Olympic stadium and cannot be forecast from the calendar.
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

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/build_data.py        # downloads the monthly CSVs one at a time; large and slow
python scripts/make_app_data.py     # parquet -> app/data.json, data/*.csv
python scripts/make_readme.py       # app/data.json + docs/backtests -> README.md
streamlit run app/streamlit_app.py
```

The panel alone needs only `pip install -r app/requirements.txt` and reads only `app/data.json`. The notebook needs the parquet files from `build_data.py` (run it from the repo root).

## Data source and licence

[IBB Open Data Portal](https://data.ibb.gov.tr) (Istanbul Metropolitan Municipality), under the IBB Open Data Licence. Datasets: [hourly public transport data](https://data.ibb.gov.tr/dataset/hourly-public-transport-data-set) and [monthly trips per rail line](https://data.ibb.gov.tr/dataset/rayli-sistemler-hat-bazli-sefer-sayilari). The special-day calendar (`data/calendar.csv`) and its sources are described in [`docs/data-notes.md`](docs/data-notes.md).

**Data notes.** On the portal, the resource titled "Aralık 2024" (December 2024) is the file `hourly_transportation_202512.csv`. Like November 2024, it has a header and no rows, so the hourly data ends in October 2024 (last complete day 2024-10-18). The monthly files shrink sharply from August 2024 because most days in them are nearly empty, not because the rows became less detailed. `build_data.py` matches files by name and checks every date against the expected month. Raw-file totals, checked against the aggregate, are in [`docs/data-notes.md`](docs/data-notes.md).
