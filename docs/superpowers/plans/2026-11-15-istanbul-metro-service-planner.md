# Istanbul Metro Service Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A portfolio project that answers "on which Istanbul rail line, in which time band, should service be added or reduced?" with a SQL data prep, rule-based station groups, a backtested simple forecast and a one-page Streamlit panel.

**Architecture:** Raw IBB monthly CSVs are reduced with DuckDB SQL to one small Parquet file per month (rail only). A small Python package `metro/` turns that into station features, groups, forecasts and backtests. `scripts/make_app_data.py` writes everything the panel needs into `app/data.json`; the panel (`app/streamlit_app.py` + `app/model.py`) reads only that file and computes the recommendation card live from two assumption sliders.

**Tech Stack:** Python 3.11+, DuckDB, pandas, scikit-learn, Streamlit, Altair, pytest, Jupyter.

**Spec:** `docs/superpowers/specs/2026-11-15-istanbul-metro-service-planner-design.md` (Turkish). Read it first; this plan argues from it.

## Global Constraints

- All project outputs (README, panel, notebook, code comments, commit messages) are in English.
- Demand measure is `number_of_passage` (boardings). `number_of_passenger` is kept only as auxiliary.
- Analysis unit is the station-line pair (`line_name` + `station_poi_desc_cd`).
- Period built: rail rows (`road_type = 'RAYLI'`) of the hourly dataset, 2023-01 to 2024-10 (all 22 months are in `data/raw/rail_hourly/`; months after 2024-07 are used only for the complete-day comparison). If download size is a problem, shorten to 2024-01 to 2024-10 and say so in the README.
- Download budget (checked 2026-11-15 from catalogue sizes): 2023-01..2024-10 is 31.5 GB in total (2024 alone 12.5 GB); files are 1.3–1.8 GB each through 2024-07, then 0.27–0.39 GB for 2024-08..10. Free disk was 686 GB. Only one raw CSV may exist on disk at a time.
- **Period decision (Batuhan, 2026-11-15; overrides earlier dates in this plan):** analysis window 2023-01-01 to 2024-07-31 (`ANALYSIS_END = "2024-07-31"`). Main backtest 2024-04-01..2024-05-26 (school term, 8 weeks); extra backtest 2024-06-03..2024-07-28 (8 weeks). Forecast window 2024-08-01..2024-08-31, called "summer scenario" in README and panel. The 19 complete days of 2024-08..10 are compared with forecasts made from data up to 2024-07-31.
- Complete day: a date whose total rail boardings are at least 100,000 (complete days have 1.2–3.8 million (1,198,341 to 3,817,592), incomplete ones at most 7,695; see `docs/data-notes.md`). Only complete days may be used anywhere.
- **Event-driven unit (Batuhan, 2026-11-15):** units that `discover_groups` marks `-1` (on real data only M9 OLIMPIYAT DOGU: 96% of boardings after 20:00, weekend 0.01× weekday) are labelled "Event-driven (unpredictable)". They get no station factor, no forecast, no backtest and no card; they appear only in the demand view, and the README lists this as a finding.
- **Group names (Batuhan, 2026-11-15: name by behaviour for now):** 0 "Morning departure", 1 "All-day & weekend", 2 "Evening departure, quiet weekend", 3 "Transfer hub", -1 "Event-driven (unpredictable)". Recheck in Task 6 that ids still map to the same behaviour before writing `GROUP_NAMES`.
- **Error measure (Batuhan, 2026-11-15):** the headline error everywhere (README, panel tile, `level_used` choice) is the boardings-weighted error `wape` (Σ|a−p| ÷ Σa) from `metro/forecast.py`; the unweighted MAPE is also given in the README, with one sentence on why it is higher (closed-station days such as 1 May at Taksim, Şişhane and Kabataş). `data.json` carries both: `station_day_wape`/`line_band_wape` next to the `*_mape` keys, and `complete_days_wape` next to `complete_days_mape`. Task 6 and Task 8 tests that read `station_day_mape` read `station_day_wape` instead for the headline.
- **Public-holiday factor (Batuhan, 2026-11-15):** stays one factor per category; not split by day type. The README's "What we can't measure" says why: Sunday holidays (e.g. 29 October celebrations) run above a normal Sunday and weekday holidays below a normal weekday, so the single factor comes out near 1.0 (0.82–1.10 by group); the 2024 test had only 5 public-holiday days, too few to estimate one factor per day type; 30 August 2024 is the worst complete day (33% error at station level).
- **Groups as a tested hypothesis (Batuhan, 2026-11-15):** the README presents "estimating special-day factors per group improves the forecast" as a hypothesis that was tested and not supported: station-level factors beat group-level in every backtest (Apr–May WAPE 10.7% vs 11.6%, Jun–Jul 15.3% vs 15.9%, religious holidays 23.7% vs 32.0%, school breaks 9.7% vs 10.9%, public holidays 33.3% vs 36.8%; complete days 10.5% vs 10.6%). Groups are kept because they describe station behaviour, not because they improve the forecast.
- **Complete-day comparison (Batuhan, 2026-11-15):** reported for all three levels. Real data, 19 days, WAPE / MAPE: none 15.2% / 16.4%, station 10.5% / 11.7%, group 10.6% / 11.8%; by month at station level August 18.6%, September 13.1%, October 1.1%. `data.json` `complete_days` rows carry the forecast of the level used plus `ape` for each level.
- **External review notes for the README (Batuhan, 2026-11-15):**
  - The summer school-break factor is estimated from the first weeks of the summer break (2024-06-17..07-31, of which 17..19 June are Kurban Bayramı): `backtest_special` and the forecast use school-break days before the cut, i.e. at most the first ~4–6 weeks of summer plus the semester and mid-term breaks. Applying it to August may be biased; the complete-day comparison shows August over-forecast (18.6% station level vs 1.1% in October). State this in "What we can't measure".
  - Station-day errors include hours 0–5; line-band errors cover only the card's bands (06–23). Hours 0–5 are 0.69% of boardings. State this next to the error numbers.
  - Closed-station days: a normal day with boardings below 20% of the unit's median for that day type (median from earlier days only) is left out of the profile and the special-day baseline (`CLOSED_THRESHOLD = 0.2` in `metro/forecast.py`). Closed days are still scored in the backtests. Give the before/after numbers from `docs/backtests/`.
  - Groups rebuilt per cut (only data before each cut) are reported next to groups built on the whole analysis period; both tables are in `docs/backtests/`.
  - Every old and new backtest number is kept in `docs/backtests/*.csv` (one file per run, never overwritten); the README quotes the final run and links the comparison.
- **No leakage (Batuhan, 2026-11-15):** in every backtest and in the complete-day comparison, typical profiles and special-day factors use only data strictly before the first forecast day. Task 4 has tests that change data on/after that day and check the profile and factors do not move.
- The source data's break (2024-08..10 mostly empty, files end 2024-10-18, Nov/Dec empty) goes in the README's "What we can't measure" section, stated as a property of the IBB files.
- No ML models beyond k-means (discovery) and a shallow decision tree (rule extraction). No LightGBM, Prophet, deep learning.
- Raw CSVs are never kept or committed. `data/raw/` is git-ignored. The panel runs with only `app/data.json`.
- Recommendations compare a line with itself only, never lines with each other.
- Never state a recommendation with more precision than "add / keep / can reduce" per line, day type and band.
- Units with fewer than 12 months of data in the period are excluded from grouping, factor estimation and the recommendation card (demand view only).
- Only lines present in both the ridership and the trips data get a recommendation card.
- Pushing to GitHub and deploying to Streamlit Community Cloud are NOT part of this plan; they need Batuhan's explicit go-ahead at the end.
- Requests to `data.ibb.gov.tr` carry no personal details (generic User-Agent).

## Fixed definitions (used by several tasks)

- Day types: `weekday`, `saturday`, `sunday`.
- Bands (hour of day, inclusive): `early` 6; `am_peak` 7–9; `midday` 10–15; `pm_peak` 16–19; `evening` 20–21; `late` 22–23. Hours 0–5 are `overnight`: shown in the demand chart, excluded from the card. (The spec's sixth band "gece" is `late`.)
- Special-day categories in the calendar: `none`, `public_holiday`, `religious_holiday`, `school_break`. If a date qualifies for several, priority is religious > public > school_break.
- A cell is a `(day_type, band)` pair; a line has 18 cells.

## Review Focus

1. A station-line with zero or missing baseline boardings (closed days, new station) → factors fall back to 1.0, no division by zero, no NaN in outputs. (Task 4)
2. A line with ridership but no trips data (e.g. Marmaray) → panel shows demand view with a plain note, no card, no crash. (Tasks 5, 7)
3. Trips missing for the forecast month for one line → last available month is used and flagged in `data.json` and in the panel. (Task 6)
4. Raw CSV quirks: blank station, hour as `"00"` text, mixed case / Turkish characters in station names, unknown `product_kind` → normalized, counted in `boardings`, never dropped silently. (Task 1)
5. A special-day category with no earlier observation for a unit (first bayram in the data) → factor 1.0 at station level; group level uses whatever group history exists. (Task 4)

---

## File structure

```
.gitignore                       data/raw/, .venv/, __pycache__/, .ipynb_checkpoints/
requirements-dev.txt             duckdb, pandas, pyarrow, openpyxl, scikit-learn, pytest, jupyter, nbconvert, -r app/requirements.txt
app/requirements.txt             streamlit, altair, pandas
sql/rail_hourly.sql              one month CSV -> station x date x hour aggregate
metro/__init__.py
metro/prep.py                    run the SQL, load trips, load hourly parquet
metro/calendar.py                load + validate data/calendar.csv
metro/features.py                station features
metro/groups.py                  k-means discovery, rule tree, agreement
metro/forecast.py                typical profile, special-day factors, forecast
metro/backtest.py                MAPE, recent-window and special-day backtests
scripts/build_data.py            download months -> data/raw/rail_hourly/YYYYMM.parquet; trips xlsx -> data/trips_monthly.csv
scripts/make_app_data.py         everything -> data/station_groups.csv, data/recommendations.csv, app/data.json
data/calendar.csv                hand-written, sourced
data/trips_monthly.csv           committed (small)
docs/data-notes.md               what the real data looked like (Task 2)
app/model.py                     panel formulas, pure Python (no pandas)
app/streamlit_app.py             panel
app/data.json                    committed
analysis.ipynb                   end-to-end narrative using metro/
README.md
tests/fixtures/hourly_sample.csv
tests/test_prep.py  test_calendar.py  test_features.py  test_groups.py
tests/test_forecast.py  test_backtest.py  test_model.py  test_app_data.py  test_app.py
```

`metro/` is an addition to the spec's layout: the spec puts all formulas in `app/model.py`, but the analysis functions need pandas/scikit-learn and tests, and the panel must stay light.

---

### Task 1: Data prep (SQL + loaders)

**Files:**
- Create: `.gitignore`, `requirements-dev.txt`, `app/requirements.txt`, `sql/rail_hourly.sql`, `metro/__init__.py`, `metro/prep.py`, `tests/fixtures/hourly_sample.csv`, `tests/test_prep.py`

**Interfaces:**
- Produces:
  - `aggregate_rail_month(csv_path: Path, out_parquet: Path) -> int` (rows written)
  - `load_hourly(parquet_dir: Path) -> pd.DataFrame` with columns `date` (datetime64), `hour` (int 0–23), `line` (str), `station` (str), `boardings`, `passengers`, `b_full`, `b_discount`, `b_free`, `b_transfer` (ints)
  - `load_trips(xlsx_path: Path) -> pd.DataFrame` with columns `month` (str `YYYY-MM`), `line` (str), `trips` (float); blank cells dropped

- [ ] **Step 1: Create the venv and dependency files**

Run: `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`
Expected: installs without error; `.venv/bin/pytest --version` prints a version.

- [ ] **Step 2: Write the fixture `tests/fixtures/hourly_sample.csv`**

Header exactly as in the real data:
`transition_date,transition_hour,transport_type_id,road_type,line,transfer_type,number_of_passage,number_of_passenger,product_kind,transaction_type_desc,town,line_name,station_poi_desc_cd`

Rows (11):
```
2024-10-01,08,2,RAYLI,YENIKAPI - HACIOSMAN,Normal,10,9,TAM,Tam Kontur,SISLI,M2,LEVENT
2024-10-01,08,2,RAYLI,YENIKAPI - HACIOSMAN,Aktarma,4,4,TAM,Tam Aktarma,SISLI,M2,LEVENT
2024-10-01,08,2,RAYLI,YENIKAPI - HACIOSMAN,Normal,6,5,INDIRIMLI1,Indirimli Abonman,SISLI,M2,LEVENT
2024-10-01,08,2,RAYLI,YENIKAPI - HACIOSMAN,Normal,2,2,UCRETSIZ,Ucretsiz,SISLI,M2,LEVENT
2024-10-01,08,2,RAYLI,YENIKAPI - HACIOSMAN,Normal,1,1,BILINMEYEN,Diger,SISLI,M2,LEVENT
2024-10-01,09,2,RAYLI,YENIKAPI - HACIOSMAN,Normal,7,7,INDIRIMLI2,Indirimli Tip 2,SISLI,M2, levent 
2024-10-01,00,2,RAYLI,KADIKOY-KARTAL,Normal,3,3,TAM,Tam Kontur,KADIKOY,M4,KOZYATAGI
2024-10-01,08,2,RAYLI,KADIKOY-KARTAL,Normal,5,5,TAM,Tam Kontur,KADIKOY,M4,
2024-10-01,08,1,OTOYOL,CEBECI - TAKSIM,Normal,99,99,TAM,Tam Kontur,SARIYER,36T,
2024-10-01,08,3,DENİZ,KADIKOY-KARAKOY,Normal,50,50,TAM,Tam Kontur,KADIKOY,KK,KADIKOY
2024-10-02,08,2,RAYLI,YENIKAPI - HACIOSMAN,Normal,8,8,TAM,Tam Kontur,SISLI,M2,LEVENT
```

- [ ] **Step 3: Write the failing tests in `tests/test_prep.py`**

```python
def test_aggregate_keeps_only_rail_and_sums(tmp_path):
    n = aggregate_rail_month(FIXTURE, tmp_path / "202410.parquet")
    df = load_hourly(tmp_path)
    assert n == len(df) == 6
    assert set(df["line"]) == {"M2", "M4"}
    row = df[(df.line == "M2") & (df.station == "LEVENT") & (df.hour == 8) & (df.date == "2024-10-01")].iloc[0]
    assert (row.boardings, row.passengers) == (23, 21)
    assert (row.b_full, row.b_discount, row.b_free, row.b_transfer) == (14, 6, 2, 4)

def test_station_names_are_trimmed_and_uppercased(tmp_path):
    aggregate_rail_month(FIXTURE, tmp_path / "202410.parquet")
    df = load_hourly(tmp_path)
    row = df[(df.line == "M2") & (df.hour == 9)].iloc[0]
    assert row.station == "LEVENT" and row.b_discount == 7

def test_blank_station_is_kept_as_unknown(tmp_path):
    aggregate_rail_month(FIXTURE, tmp_path / "202410.parquet")
    df = load_hourly(tmp_path)
    assert df[(df.line == "M4") & (df.station == "UNKNOWN")].boardings.sum() == 5

def test_hour_text_becomes_int(tmp_path):
    aggregate_rail_month(FIXTURE, tmp_path / "202410.parquet")
    df = load_hourly(tmp_path)
    assert df[df.station == "KOZYATAGI"].hour.tolist() == [0]

def test_total_boardings_match_raw_rail_rows(tmp_path):
    aggregate_rail_month(FIXTURE, tmp_path / "202410.parquet")
    assert load_hourly(tmp_path).boardings.sum() == 46

def test_load_trips_long_format(tmp_path):
    # build a 3-row xlsx with openpyxl: header ["Tarih","M1","M2"], rows [date(2024,10,1), 100, 200], [date(2024,11,1), 110, None]
    df = load_trips(path)
    assert df.to_dict("records") == [
        {"month": "2024-10", "line": "M1", "trips": 100.0},
        {"month": "2024-10", "line": "M2", "trips": 200.0},
        {"month": "2024-11", "line": "M1", "trips": 110.0},
    ]
```

- [ ] **Step 4: Run to verify failure**

Run: `.venv/bin/pytest tests/test_prep.py -v`
Expected: FAIL (import error for `metro.prep`).

- [ ] **Step 5: Write `sql/rail_hourly.sql` and implement `metro/prep.py`**

The SQL is a single readable `SELECT ... GROUP BY` with two placeholders (`{csv_path}`, `{out_parquet}`) filled by `aggregate_rail_month`; all columns read as VARCHAR then cast. Mapping: `b_full` = `product_kind = 'TAM'`; `b_discount` = `product_kind LIKE 'INDIRIMLI%'`; `b_free` = `product_kind = 'UCRETSIZ'`; `b_transfer` = `transfer_type = 'Aktarma'`; station = `upper(trim(station_poi_desc_cd))`, empty → `'UNKNOWN'`. Use plain `upper()` (ASCII-safe; real station names are unaccented capitals — Task 2 verifies). `load_trips` must accept the real file's date column whether openpyxl returns datetimes or Excel serial numbers.

- [ ] **Step 6: Run to verify pass**

Run: `.venv/bin/pytest tests/test_prep.py -v`
Expected: 6 passed.

- [ ] **Step 7: Commit**

```bash
git add .gitignore requirements-dev.txt app/requirements.txt sql metro tests
git commit -m "feat: SQL prep for rail hourly ridership and trips loader"
```

---

### Task 2: Build the real dataset, record what it looks like, write the calendar

**Files:**
- Create: `scripts/build_data.py`, `metro/calendar.py`, `data/calendar.csv`, `data/trips_monthly.csv`, `docs/data-notes.md`, `tests/test_calendar.py`

**Interfaces:**
- Consumes: `aggregate_rail_month`, `load_trips`, `load_hourly` (Task 1)
- Produces:
  - CLI: `python scripts/build_data.py --start 2023-01 --end 2024-10` → `data/raw/rail_hourly/YYYYMM.parquet` (skips months already present; downloads each CSV to a temp file and deletes it after aggregation), plus `data/trips_monthly.csv` (`month,line,trips`)
  - `load_calendar(path: Path = Path("data/calendar.csv")) -> pd.DataFrame` with columns `date` (datetime64), `day_type`, `special`, `label` (free text, e.g. "Ramazan Bayramı day 1")

- [ ] **Step 1: Write the failing calendar tests**

```python
def test_calendar_covers_period_without_gaps():
    cal = load_calendar()
    assert cal.date.min() == pd.Timestamp("2023-01-01")
    assert cal.date.max() >= pd.Timestamp("2024-11-30")
    assert cal.date.is_unique and (cal.date.diff().dropna() == pd.Timedelta(days=1)).all()

def test_calendar_values():
    cal = load_calendar()
    assert set(cal.day_type) == {"weekday", "saturday", "sunday"}
    assert set(cal.special) == {"none", "public_holiday", "religious_holiday", "school_break"}
    assert (cal.day_type == cal.date.dt.dayofweek.map(lambda d: "saturday" if d == 5 else "sunday" if d == 6 else "weekday")).all()

def test_known_days():
    cal = load_calendar().set_index("date")
    assert cal.loc["2024-10-29", "special"] == "public_holiday"      # Republic Day
    assert cal.loc["2024-04-10", "special"] == "religious_holiday"   # Ramazan Bayramı day 1
    assert cal.loc["2024-06-16", "special"] == "religious_holiday"   # Kurban Bayramı day 1
    assert cal.loc["2023-04-21", "special"] == "religious_holiday"   # Ramazan Bayramı day 1
    assert cal.loc["2024-10-15", "special"] == "none"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_calendar.py -v` — Expected: FAIL (no module / no file).

- [ ] **Step 3: Write `data/calendar.csv` and `metro/calendar.py`**

Generate the date spine by script, then fill specials by hand: Turkish public holidays (Jan 1, Apr 23, May 1, May 19, Jul 15, Aug 30, Oct 29), Ramazan and Kurban bayram days including the official half-day eve (label it, category `religious_holiday`), and MEB school breaks for 2022-23, 2023-24 and 2024-25 (semester break, the two one-week mid-term breaks, summer break) for weekdays. Look the dates up from official sources (MEB calendar, Resmî Gazete) and list the source URLs at the top of `docs/data-notes.md`. Do not rely on memory for dates.

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_calendar.py -v` — Expected: 3 passed.

- [ ] **Step 5: Implement `scripts/build_data.py` and run it for one month**

Resource URLs come from the CKAN API (`https://data.ibb.gov.tr/api/3/action/package_show?id=hourly-public-transport-data-set`), matched by the file name `hourly_transportation_YYYYMM.csv`; trips from `id=rayli-sistemler-hat-bazli-sefer-sayilari`.

Known catalogue quirks (verified 2026-11-15) the script must handle:
- The resource titled "Aralık 2024" has the file name `hourly_transportation_202512.csv` (year mismatch). It and "Kasım 2024" (`202411`) are header-only, 187 bytes. Match on the file-name `YYYYMM`, accept only months inside `--start..--end`, and after aggregation assert that every date in the output falls in the month the file name claims; fail loudly otherwise. Add a test for that assertion in `tests/test_prep.py` (a fixture row dated outside the expected month → `ValueError`), which means `aggregate_rail_month` takes an extra `expected_month: str | None = None` argument (`"YYYY-MM"`).
- The server may ignore HTTP range requests and send the whole file; never rely on partial downloads for sampling.
- Downloads must be resumable (`curl -C -` or equivalent) and retried, with a generic User-Agent.

Run: `.venv/bin/python scripts/build_data.py --start 2024-10 --end 2024-10`
Expected: prints rows written; `data/raw/rail_hourly/202410.parquet` and `data/trips_monthly.csv` exist.

- [ ] **Step 6: Verify one month against the raw file independently**

While the temp CSV still exists (add a `--keep-csv` flag for this step), run:
`grep -c ',RAYLI,' <csv>` and an `awk -F,` sum of column 7 over rail rows, and compare with `load_hourly(...).boardings.sum()` for that month.
Expected: identical totals. Record both numbers in `docs/data-notes.md`.

- [ ] **Step 7: Build the full period**

Before starting, re-check free disk (`df -h .`) and re-read the catalogue sizes; stop and report if free space is under 10 GB.

Run in the background, newest month first, so a usable 2024 set exists early: `.venv/bin/python scripts/build_data.py --start 2023-01 --end 2024-10 --newest-first`
Expected: 22 parquet files (31.5 GB downloaded in total, one file at a time; expect hours, not minutes). If the download is impractical, keep 2024-01..2024-10 (12.5 GB) and record the decision in `docs/data-notes.md` and the README.

- [ ] **Step 8: Write `docs/data-notes.md` from the real data**

Answer each with a number or a short table, since later tasks depend on them:
1. Distinct `line` values, months present per line, and which lines also appear in `data/trips_monthly.csv` (and through which month the trips file runs).
2. Stations that appear under more than one line: is the split stable month to month? If not, list them; Task 3 treats those as one unit (line = the lines joined with `+`).
3. Distinct `product_kind` values with boarding shares. Is there a value that clearly means "student"? If yes, Task 3 uses it for `discount_share`; if not, all `INDIRIMLI%` stays.
4. Station-lines with fewer than 12 months of data (these are demand-view only).
5. Any non-ASCII or inconsistently spelled station names; if found, add a normalization map to `metro/prep.py` with a test.
6. Share of boardings in hours 0–5.
7. The file-size break: 2024-08..10 files are about a sixth of the size of earlier months. Compare rail rows per month, rail boardings per month and per line, and distinct values of each text column for 2024-07 vs 2024-08. If boardings per line are continuous, the change is only in row granularity and nothing else is needed. If totals jump, stop and report before Task 3: the backtest window (Sep–Oct 2024) sits entirely after the break.

Already verified on the full October 2024 file (2026-11-15), to be confirmed across all months: `road_type` has exactly three values (`OTOYOL`, `RAYLI`, `DENİZ`); every row has 13 fields; rail `line_name` values are `M1 M2 M3 M4 M5 M6 M7 M8 M9 T1 T3 T4 T5 F1 F4 TF1 TF2` plus `MARMARAY`, `TCDD-GH`, `TCDD-SK`, `TCDD-HB`, `TUNEL`, `NOSTRAM`; no rail-like code appears under another `road_type`. The trips file has 108 monthly rows from 2017-01 to 2025-12 with the 17 lines `M1`–`M9, T1, T3, T4, T5, F1, F4, TF1, TF2`; all 17 have values for 2024-10 and 2024-11 (in 2017-01 only `M1 M2 M3 M4 M6 T1 T4 F1`). So the six other codes are demand-view only, and the November 2024 trips fallback is not expected to trigger on real data.

- [ ] **Step 9: Commit**

```bash
git add scripts/build_data.py metro/calendar.py data/calendar.csv data/trips_monthly.csv docs/data-notes.md tests/test_calendar.py
git commit -m "feat: build script, calendar and data notes from the real IBB data"
```

---

### Task 3: Station features and groups

**Files:**
- Create: `metro/features.py`, `metro/groups.py`, `tests/test_features.py`, `tests/test_groups.py`

**Interfaces:**
- Consumes: hourly and calendar frames (Tasks 1–2)
- Produces:
  - In `metro/prep.py`: `ANALYSIS_END = "2024-07-31"`, `MIN_DAY_BOARDINGS = 100_000`, `complete_days(hourly) -> pd.DatetimeIndex` (dates whose total boardings ≥ `MIN_DAY_BOARDINGS`), `analysis_hourly(hourly) -> pd.DataFrame` (rows with date ≤ `ANALYSIS_END` and on a complete day; also drops line `34A`). Tests in `tests/test_prep.py`: `test_complete_days_drops_thin_days` (a date with 7,695 boardings is excluded, one with 1,200,000 kept) and `test_analysis_hourly_stops_at_july_2024` (a 2024-08-25 row is dropped). Features, groups and factors are computed on `analysis_hourly(...)` only.
  - `station_features(hourly, calendar, min_months: int = 12) -> pd.DataFrame` indexed by `(line, station)`, columns `weekend_ratio, am_share, midday_share, pm_share, late_share, discount_share, transfer_share, months_active, eligible` (bool)
  - `FEATURE_COLS: list[str]` (the seven feature columns, in that order)
  - `discover_groups(features, k_values=(4, 5, 6), seed: int = 0) -> pd.Series` (cluster id per eligible unit; k chosen by best silhouette score)
  - `fit_rule(features, labels, max_depth: int = 3) -> DecisionTreeClassifier`
  - `rule_text(tree) -> str` (sklearn `export_text` with feature names)
  - `rule_agreement(tree, features, labels) -> float` (share of units where the tree reproduces the cluster)

Feature definitions (non-special days only): `weekend_ratio` = mean daily boardings on Sat+Sun ÷ mean daily boardings on weekdays; the four `*_share` are shares of weekday boardings in bands `am_peak`, `midday`, `pm_peak`, `late` (`late_share` here includes `evening`, `late` and `overnight` hours, i.e. 20–05); `discount_share` and `transfer_share` are shares of all boardings; `months_active` = months with any boardings.

- [ ] **Step 1: Write the failing tests**

```python
def test_features_on_synthetic_commuter_station():
    # helper builds 14 months of hourly rows for ("M2","A"): weekdays 100 boardings at hour 8, 50 at hour 12, 50 at hour 17; Sat/Sun 20 at hour 12; b_discount = 10% of boardings, b_transfer = 0
    f = station_features(hourly, calendar).loc[("M2", "A")]
    assert f.am_share == pytest.approx(0.5) and f.midday_share == pytest.approx(0.25) and f.pm_share == pytest.approx(0.25)
    assert f.late_share == 0 and f.weekend_ratio == pytest.approx(0.1)
    assert f.discount_share == pytest.approx(0.1) and f.months_active == 14 and f.eligible

def test_short_history_is_not_eligible():   # 5 months of data
    assert not station_features(hourly, calendar).loc[("M9", "NEW")].eligible

def test_special_days_do_not_enter_profile_shares():
    # same station, but every public_holiday has 1000 boardings at hour 23 -> late_share stays 0

def test_station_with_no_weekday_boardings_gets_nan_free_row():
    # weekend-only unit: weekend_ratio is 0-safe (set to large finite cap 10.0), shares 0, no NaN anywhere

def test_discover_groups_separates_obvious_clusters():
    # 40 units: 20 with am_share .6/pm_share .1, 20 with am_share .1/pm_share .6 (small noise, seed fixed); k_values=(2,3)
    labels = discover_groups(features, k_values=(2, 3))
    assert labels.nunique() == 2 and labels.iloc[:20].nunique() == 1 and labels.iloc[20:].nunique() == 1

def test_rule_reproduces_separable_clusters():
    tree = fit_rule(features, labels)
    assert rule_agreement(tree, features, labels) == 1.0
    assert "am_share" in rule_text(tree) or "pm_share" in rule_text(tree)
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_features.py tests/test_groups.py -v` → FAIL (imports).

- [ ] **Step 3: Implement `metro/features.py` and `metro/groups.py`**

`discover_groups` standardizes `FEATURE_COLS` (StandardScaler) and runs `KMeans(n_init=10, random_state=seed)` on eligible units only. `fit_rule` trains on the unstandardized features so the thresholds read as plain shares.

- [ ] **Step 4: Run to verify pass** — same command → 6 passed.

- [ ] **Step 5: Commit**

```bash
git add metro/features.py metro/groups.py tests/test_features.py tests/test_groups.py
git commit -m "feat: station features, k-means discovery and rule extraction"
```

---

### Task 4: Forecast and backtests

**Files:**
- Create: `metro/forecast.py`, `metro/backtest.py`, `tests/test_forecast.py`, `tests/test_backtest.py`

**Interfaces:**
- Consumes: hourly, calendar; `groups: pd.Series` indexed by `(line, station)` → group name (eligible units only)
- Produces:
  - `typical_profile(hourly, calendar, as_of: pd.Timestamp, n_weeks: int = 8) -> pd.DataFrame` columns `line, station, day_type, hour, boardings` — mean boardings per day for that hour over non-special days in the `n_weeks` × 7 days strictly before `as_of`; every unit gets all 3 × 24 rows (0 where absent)
  - `special_factors(hourly, calendar, groups, before: pd.Timestamp, level: str) -> pd.DataFrame` columns `line, station, special, factor`; `level` in `{"none", "station", "group"}`
  - `forecast(profile, factors, future_calendar) -> pd.DataFrame` columns `date, line, station, hour, boardings`
  - `mape(actual: pd.Series, predicted: pd.Series) -> float` (mean of |a−p|/a over rows with a > 0)
  - `backtest_recent(hourly, calendar, groups, start="2024-04-01", end="2024-05-26", level="group") -> dict` with keys `station_day_mape`, `line_band_mape` (main backtest; called again with `start="2024-06-03", end="2024-07-28"` for the extra backtest)
  - `compare_complete_days(hourly, calendar, groups, level: str, as_of="2024-08-01") -> pd.DataFrame` columns `date, actual, forecast, ape` at line-day level summed over all lines, one row per complete day after `as_of` (expected 19 rows on real data); uses `complete_days` from `metro/prep.py`
  - `backtest_special(hourly, calendar, groups, year: int = 2024) -> pd.DataFrame` columns `special, level, station_day_mape, n_days` for the three levels

Factor definition: for each special day `d` before `before`, baseline = the unit's mean daily boardings on non-special days of the same `day_type` in the 28 days before `d`; ratio = actual daily boardings ÷ baseline. Station level: factor = median ratio per `(unit, special)`. Group level: sum actual and sum baseline over the group's units first, then the median of those group ratios, applied to every unit in the group. `none`: all factors 1.0. Any missing, zero-baseline or non-finite case → 1.0. Factors apply to all hours of the day equally.

`backtest_special`: consecutive special days of the same category form a block; for each 2024 block, build the profile and factors from data strictly before the block's first day, forecast the block, and score it at station-day level.

- [ ] **Step 1: Write the failing tests**

```python
def test_typical_profile_is_mean_of_last_n_weeks_non_special():
    # unit has 10 boardings at hour 8 on every weekday for 12 weeks, except the last 8 weeks have 20; one public_holiday inside the window has 500
    p = typical_profile(hourly, calendar, as_of=AS_OF, n_weeks=8)
    assert p[(p.day_type == "weekday") & (p.hour == 8)].boardings.item() == pytest.approx(20)
    assert len(p) == 72

def test_station_factor_is_median_ratio():
    # three earlier public holidays (weekdays) with daily boardings 50, 60, 100 against a baseline of 100
    f = special_factors(hourly, calendar, groups, before=AS_OF, level="station")
    assert f[f.special == "public_holiday"].factor.item() == pytest.approx(0.6)

def test_group_factor_pools_units():
    # unit A: holiday 50 vs baseline 100; unit B (same group): holiday 10 vs baseline 100 -> group ratio 60/200
    f = special_factors(hourly, calendar, groups, before=AS_OF, level="group")
    assert set(f[f.special == "public_holiday"].factor.round(3)) == {0.3}

def test_factor_falls_back_to_one():
    # (a) category never seen before `before`; (b) unit with zero baseline -> factor 1.0, finite
    f = special_factors(hourly, calendar, groups, before=AS_OF, level="station")
    assert np.isfinite(f.factor).all() and f[f.special == "religious_holiday"].factor.eq(1.0).all()

def test_level_none_gives_all_ones():
    assert special_factors(hourly, calendar, groups, before=AS_OF, level="none").factor.eq(1.0).all()

def test_forecast_applies_factor_on_special_day_only():
    # profile weekday hour 8 = 20, factor public_holiday = 0.5; future calendar = one normal weekday + one public-holiday weekday
    out = forecast(profile, factors, future)
    assert out[out.hour == 8].boardings.tolist() == [20.0, 10.0]

def test_mape_ignores_zero_actuals():
    assert mape(pd.Series([100, 0, 50]), pd.Series([90, 5, 60])) == pytest.approx(0.15)

def test_backtest_special_prefers_right_level_on_synthetic_data():
    # every unit truly drops to 40% on religious holidays in both 2023 and 2024
    r = backtest_special(hourly, calendar, groups).set_index(["special", "level"]).station_day_mape
    assert r[("religious_holiday", "group")] < 0.05 < r[("religious_holiday", "none")]

def test_backtest_recent_returns_both_levels_of_error():
    r = backtest_recent(hourly, calendar, groups)
    assert set(r) == {"station_day_mape", "line_band_mape"} and all(np.isfinite(v) for v in r.values())
```

Add to the Step 1 tests:

```python
def test_compare_complete_days_skips_thin_days_and_uses_only_earlier_data():
    # data to 2024-07-31 plus 2024-08-25 (complete, 1.5M) and 2024-08-26 (thin, 500); 2024-08-25 actual is doubled vs profile
    r = compare_complete_days(hourly, calendar, groups, level="none")
    assert r.date.dt.strftime("%Y-%m-%d").tolist() == ["2024-08-25"]
    assert r.ape.item() == pytest.approx(0.5)
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_forecast.py tests/test_backtest.py -v` → FAIL (imports).
- [ ] **Step 3: Implement `metro/forecast.py` and `metro/backtest.py`**
- [ ] **Step 4: Run to verify pass** — same command → 10 passed.
- [ ] **Step 5: Commit**

```bash
git add metro/forecast.py metro/backtest.py tests/test_forecast.py tests/test_backtest.py
git commit -m "feat: profile forecast with special-day factors and two backtests"
```

---

### Task 5: Panel formulas (`app/model.py`)

**Files:**
- Create: `app/model.py`, `tests/test_model.py`

**Interfaces:**
- Produces (pure Python, no pandas; `Cell = tuple[str, str]` = `(day_type, band)`):
  - `BANDS: dict[str, list[int]]` and `DAY_TYPES: list[str]` per "Fixed definitions"; `PEAK_BANDS = ("am_peak", "pm_peak")`
  - `band_boardings(hourly: dict[str, list[float]]) -> dict[Cell, float]` — sums a 24-value list per day type into bands (boardings per day in that cell)
  - `trips_per_cell(monthly_trips: float, days: dict[str, int], peak_mult: float = 1.0, weekend_mult: float = 1.0) -> dict[Cell, float]` — trips per day in each cell
  - `load_index(boardings: dict[Cell, float], trips: dict[Cell, float]) -> dict[Cell, float]`
  - `recommend(load: dict[Cell, float], trips: dict[Cell, float], add_at: float = 1.25, reduce_at: float = 0.6) -> dict[Cell, str]` — labels `"add"`, `"keep"`, `"reduce"`
  - `robust(boardings, monthly_trips, days, peak_grid=(1.0, 1.25, 1.5, 1.75, 2.0), weekend_grid=(0.6, 0.7, 0.8, 0.9, 1.0)) -> dict[Cell, bool]`

`trips_per_cell`: each operating hour (6–23) gets weight 1; weekday hours in `PEAK_BANDS` get `peak_mult`; all Saturday and Sunday hours are multiplied by `weekend_mult`. One base rate is solved so that `sum(days[d] × trips[(d, band)]) == monthly_trips`. `recommend`: reference = the line's trip-weighted mean load (`Σ boardings·days / Σ trips·days` reduces to total boardings ÷ total trips; pass `trips` as weights); `add` if load ≥ `add_at` × reference, `reduce` if ≤ `reduce_at` × reference. `robust[cell]` is True when the label is identical over all 25 grid combinations.

- [ ] **Step 1: Write the failing tests**

```python
DAYS = {"weekday": 20, "saturday": 4, "sunday": 4}

def test_bands_cover_operating_hours_once():
    hours = sorted(h for hs in BANDS.values() for h in hs)
    assert hours == list(range(6, 24)) and list(BANDS) == ["early", "am_peak", "midday", "pm_peak", "evening", "late"]

def test_band_boardings_sums_hours_and_drops_overnight():
    b = band_boardings({"weekday": [1.0] * 24, "saturday": [0.0] * 24, "sunday": [0.0] * 24})
    assert b[("weekday", "am_peak")] == 3 and b[("weekday", "midday")] == 6 and sum(b.values()) == 18

def test_flat_trips_are_proportional_to_band_hours_and_sum_to_month():
    t = trips_per_cell(18 * 28 * 10, DAYS)           # 10 trips per operating hour
    assert t[("weekday", "am_peak")] == pytest.approx(30) and t[("sunday", "early")] == pytest.approx(10)
    assert sum(DAYS[d] * v for (d, _), v in t.items()) == pytest.approx(18 * 28 * 10)

def test_multipliers_shift_trips_but_keep_monthly_total():
    t = trips_per_cell(5040, DAYS, peak_mult=2.0, weekend_mult=0.6)
    assert sum(DAYS[d] * v for (d, _), v in t.items()) == pytest.approx(5040)
    assert t[("weekday", "am_peak")] / 3 == pytest.approx(2 * t[("weekday", "midday")] / 6)
    assert t[("saturday", "midday")] == pytest.approx(0.6 * t[("weekday", "midday")])
    assert t[("saturday", "am_peak")] / 3 == pytest.approx(t[("saturday", "midday")] / 6)   # no peak boost on weekends

def test_recommend_labels_relative_to_line_mean():
    # 18 cells with equal trips; loads: one cell 200, one cell 40, sixteen cells 100 -> reference ~ 102
    labels = recommend(load, trips)
    assert labels[HIGH] == "add" and labels[LOW] == "reduce" and list(labels.values()).count("keep") == 16

def test_robust_true_only_when_label_never_changes():
    # weekday am_peak boardings so high it is "add" even at peak_mult 2.0; weekday pm_peak "add" at 1.0 but "keep" at 2.0
    r = robust(boardings, monthly_trips, DAYS)
    assert r[("weekday", "am_peak")] is True and r[("weekday", "pm_peak")] is False

def test_zero_trips_or_zero_boardings_do_not_crash():
    assert load_index({c: 0.0 for c in CELLS}, trips_per_cell(0, DAYS)) == {c: 0.0 for c in CELLS}
    assert set(recommend({c: 0.0 for c in CELLS}, trips_per_cell(0, DAYS)).values()) == {"keep"}

def test_slider_extremes_are_accepted():
    for pm, wm in [(1.0, 0.6), (2.0, 1.0), (2.0, 0.6)]:
        assert len(trips_per_cell(5040, DAYS, pm, wm)) == 18
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_model.py -v` → FAIL (import).
- [ ] **Step 3: Implement `app/model.py`**
- [ ] **Step 4: Run to verify pass** — same command → 8 passed.
- [ ] **Step 5: Commit**

```bash
git add app/model.py tests/test_model.py
git commit -m "feat: load index, recommendation rule and robustness check"
```

---

### Task 6: Produce the outputs (`make_app_data.py`)

**Files:**
- Create: `scripts/make_app_data.py`, `data/station_groups.csv`, `data/recommendations.csv`, `app/data.json`, `tests/test_app_data.py`

**Interfaces:**
- Consumes: everything from Tasks 1–5; `docs/data-notes.md` findings
- Produces:
  - `build_app_data(hourly, calendar, trips, group_names: dict[int, str]) -> dict` (pure; the CLI wraps it and writes the three files)
  - `GROUP_NAMES: dict[int, str]` and `GROUP_RULE: str` constants in the script — written by the implementer after looking at the real clusters (short English names such as "Residential (AM-out)"; the rule as 2–5 plain sentences derived from `rule_text`)
  - `app/data.json`:

```
{
  "meta": {"data_start": "2023-01-01", "data_end": "2024-07-31",
           "forecast_start": "2024-08-01", "forecast_end": "2024-08-31", "scenario": "summer",
           "backtest": {"station_day_mape": f, "line_band_mape": f,
                        "extra": {"window": "2024-06-03..2024-07-28", "station_day_mape": f, "line_band_mape": f},
                        "complete_days": [{"date": "2024-08-25", "actual": n, "forecast": f, "ape": f}],
                        "complete_days_mape": f,
                        "special": [{"special": s, "level": l, "station_day_mape": f, "n_days": n}],
                        "level_used": "group" | "station" | "none"},
           "rule_agreement": f, "rule": "<GROUP_RULE>"},
  "groups": [{"name": s, "n_stations": n}],
  "lines": {"M2": {
      "has_trips": bool, "trips_month_used": "2024-08" | null, "trips_month_is_fallback": bool,
      "monthly": [{"month": "2023-01", "boardings": n, "trips": n | null}],
      "days": {"weekday": n, "saturday": n, "sunday": n},
      "trips_month": n | null,
      "hourly": {"weekday": [24 floats], "saturday": [...], "sunday": [...]},
      "stations": [{"station": s, "group": s | null, "boardings_day": f}],
      "daily": [{"date": "2024-08-01", "boardings": f, "special": s}]}}
}
```

  `days` counts each day type in the forecast window; `hourly` is the forecast mean boardings per day by hour for the line (special days included); `stations[].group` is null for ineligible units; `monthly[].trips` is null where absent.
  - `data/recommendations.csv` columns `line, day_type, band, boardings_per_day, trips_per_day, load, label, robust` at base assumptions (1.0, 1.0), lines with trips only.
  - `data/station_groups.csv` columns `line, station, group, cluster`.

`level_used` = the level with the lowest boarding-weighted `station_day_mape` in `backtest_special`; ties → the simpler one (`none` < `group` < `station`). Trips for the card: August 2024 from `trips_monthly.csv`; if absent for a line, its last available month with `trips_month_is_fallback: true`.

- [ ] **Step 1: Write the failing tests** (synthetic small inputs: 2 lines × 2 stations × 14 months, line "MX" absent from trips, line "M1" missing the 2024-08 trips row)

```python
def test_schema_and_window():
    d = build_app_data(hourly, calendar, trips, {0: "A", 1: "B"})
    assert d["meta"]["forecast_start"] == "2024-08-01" and d["meta"]["forecast_end"] == "2024-08-31"
    assert d["meta"]["data_end"] == "2024-07-31" and d["meta"]["scenario"] == "summer"
    assert sum(d["lines"]["M1"]["days"].values()) == 31 and len(d["lines"]["M1"]["daily"]) == 31
    assert all(len(v) == 24 for v in d["lines"]["M1"]["hourly"].values())

def test_line_without_trips_is_demand_only():
    mx = build_app_data(...)["lines"]["MX"]
    assert mx["has_trips"] is False and mx["trips_month"] is None and mx["trips_month_used"] is None

def test_missing_forecast_month_falls_back_and_is_flagged():
    m1 = build_app_data(...)["lines"]["M1"]
    assert m1["trips_month_used"] == "2024-07" and m1["trips_month_is_fallback"] is True

def test_no_nan_or_inf_anywhere_and_json_serializable():
    s = json.dumps(build_app_data(...), allow_nan=False)   # raises on NaN/inf

def test_daily_forecast_sums_station_forecasts():
    # sum of line daily boardings == sum over days of hourly[day_type] weighted by normal days + special-day rows; compare to forecast() output total within 1e-6

def test_committed_data_json_matches_schema():
    d = json.load(open("app/data.json"))
    assert {"meta", "groups", "lines"} <= set(d) and any(l["has_trips"] for l in d["lines"].values())
    assert 0 < d["meta"]["backtest"]["station_day_mape"] < 1
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_app_data.py -v` → FAIL.
- [ ] **Step 3: Implement `build_app_data` and the CLI** — the first five tests pass.
- [ ] **Step 4: Run on real data, inspect clusters, write `GROUP_NAMES` and `GROUP_RULE`**

Run: `.venv/bin/python scripts/make_app_data.py --inspect` (prints k, silhouette, cluster sizes, mean features per cluster, `rule_text`, agreement, and 5 example stations per cluster).
Name the groups from what the features show, not from the spec's guesses. If agreement is below 0.8 at depth 3, keep the rule but report the number as is.

- [ ] **Step 5: Generate the files**

Run: `.venv/bin/python scripts/make_app_data.py`
Expected: writes the three files; `app/data.json` under 1 MB.

- [ ] **Step 6: Run all tests** — `.venv/bin/pytest -v` → all pass.
- [ ] **Step 7: Commit**

```bash
git add scripts/make_app_data.py data/station_groups.csv data/recommendations.csv app/data.json tests/test_app_data.py
git commit -m "feat: groups, backtest results, forecast and recommendations as app data"
```

---

### Task 7: Streamlit panel

**Files:**
- Create: `app/streamlit_app.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: `app/data.json` schema (Task 6), `app/model.py` (Task 5)

Layout (one page, wide, English), following the sketch in spec §5:
1. Title "Istanbul Metro Service Planner", selectors `Line` (lines with trips first) and `Day type`.
2. Four tiles: "Boardings / day", "Trips / day", "Boardings / trip", "Forecast error (backtest)" = `meta.backtest.station_day_mape` as a percentage. Tile labels say "boardings", never "riders".
3. Left: recommendation card for the selected day type — six bands, label ADD / keep / can reduce, with "(robust)" where `robust` is True. Right: 24-hour chart of forecast boardings with the assumed trips per hour as a second series, peak bands shaded.
4. Left: bar chart of stations on the line coloured by group. Right: daily forecast bars for 2024-08-01..31 labelled "Summer scenario: August 2024", special days marked, and the actual totals of the complete August days as dots.
5. A chart of monthly boardings per trip for the line, captioned as the measured indicator.
6. Two sliders: "Peak-hour service vs off-peak" 1.0–2.0 step 0.25, "Weekend service vs weekday" 0.6–1.0 step 0.1 (the same grids as `robust`). Next to them an expander "What we can't measure" with the four limits from the spec, and the group rule text.
7. Line without trips: tiles 2 and 3 show "n/a", the card is replaced by "No trip data is published for this line — demand view only." If `trips_month_is_fallback`, a caption states which month's trips were used.
8. Footer: data source (IBB Open Data Portal), analysis period 2023-01..2024-07, "Source files are incomplete from August 2024".

- [ ] **Step 1: Write the failing smoke tests**

```python
from streamlit.testing.v1 import AppTest

def run(line=None, day=None, peak=None, weekend=None):
    at = AppTest.from_file("app/streamlit_app.py", default_timeout=30).run()
    # set selectboxes / sliders when given, then .run() again
    return at

def test_app_runs_for_every_line_and_day_type():
    data = json.load(open("app/data.json"))
    for line in data["lines"]:
        for day in ["Weekday", "Saturday", "Sunday"]:
            assert not run(line, day).exception

def test_line_without_trips_shows_demand_only_note():
    # pick a line with has_trips false if one exists, else skip
    assert any("demand view only" in m.value for m in run(line).info)

def test_slider_extremes_do_not_crash():
    assert not run(peak=2.0, weekend=0.6).exception

def test_app_does_not_need_raw_data(tmp_path, monkeypatch):
    # run with cwd where data/raw does not exist; app resolves data.json relative to its own file
    assert not run().exception
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_app.py -v` → FAIL (file missing).
- [ ] **Step 3: Implement `app/streamlit_app.py`** (Altair charts; imports only `streamlit`, `altair`, `pandas`, `json`, `model`).
- [ ] **Step 4: Run to verify pass** — same command → 4 passed (or 3 passed, 1 skipped).
- [ ] **Step 5: Look at it**

Run: `.venv/bin/streamlit run app/streamlit_app.py`, open it, take a screenshot of two lines, and check: card readable in under five seconds, no overlapping labels, sliders change the card, numbers match `data/recommendations.csv` at base assumptions. Show the screenshots to Batuhan; layout and look are his call.

- [ ] **Step 6: Commit**

```bash
git add app/streamlit_app.py tests/test_app.py
git commit -m "feat: one-page Streamlit panel"
```

---

### Task 8: Notebook, README, end-to-end check

**Files:**
- Create: `analysis.ipynb`, `README.md`, `tests/test_readme.py`

**Interfaces:**
- Consumes: `metro/*`, `app/data.json`, `data/*.csv`, `docs/data-notes.md`

Notebook sections (each calls `metro/` functions; no logic re-implemented in cells): 1 Question and data; 2 Data prep (shows `sql/rail_hourly.sql`, monthly totals); 3 Measured indicator: boardings per trip by line and month; 4 Station features and groups (cluster means, rule, agreement, examples); 5 Forecast method; 6 Backtests (main Apr–May 2024, extra Jun–Jul 2024, special days by level — state plainly whether groups helped; then the 19 complete days of Aug–Oct 2024 against the forecast); 7 Recommendation card at base assumptions; 8 Sensitivity (how many labels are robust); 9 What we can't measure.

README must state as a finding that M9 Olimpiyat Doğu is event-driven (96% of boardings after 20:00) and is shown as demand only. README sections: title and one-line question; live-app placeholder line ("Live app: not deployed yet"); What we found (3–5 numbered findings with numbers); Recommendation table (lines × the cells labelled add/reduce at base assumptions, robust ones marked); How it works; What we can't measure (the four limits, plus the source data's break: Aug–Oct 2024 mostly empty in the IBB files, so the analysis stops at July 2024 and the August forecast is a summer scenario); What's in this repo; Run it yourself (`pip install -r requirements-dev.txt`, `python scripts/build_data.py`, `python scripts/make_app_data.py`, `streamlit run app/streamlit_app.py`; note the panel alone needs only `app/requirements.txt`); Data source and licence (IBB Open Data Portal); a short "Data notes" paragraph stating that the portal's "Aralık 2024" file is named `202512` and, like November 2024, is empty, so the data ends in October 2024, and that monthly files shrink sharply from August 2024 (with what Task 2 found about it).

- [ ] **Step 1: Write the failing README consistency test**

```python
def test_readme_numbers_come_from_data_json():
    d = json.load(open("app/data.json")); readme = open("README.md").read()
    assert f'{d["meta"]["backtest"]["station_day_mape"]:.0%}' in readme
    assert f'{d["meta"]["rule_agreement"]:.0%}' in readme
    assert str(len(d["groups"])) in readme and all(g["name"] in readme for g in d["groups"])
    assert "What we can't measure" in readme and "summer scenario" in readme.lower()
    assert "August 2024" in readme and "19 complete days" in readme
    assert f'{d["meta"]["backtest"]["complete_days_mape"]:.0%}' in readme

def test_readme_recommendation_table_matches_csv():
    rec = pd.read_csv("data/recommendations.csv")
    for line in rec[rec.label != "keep"].line.unique():
        assert f"| {line} |" in open("README.md").read()
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/pytest tests/test_readme.py -v` → FAIL (no README).
- [ ] **Step 3: Write `analysis.ipynb` and execute it**

Run: `.venv/bin/jupyter nbconvert --to notebook --execute --inplace analysis.ipynb`
Expected: exits 0, all cells have outputs.

- [ ] **Step 4: Write `README.md` from the notebook's numbers** — test from Step 1 passes.
- [ ] **Step 5: Full verification (spec "Doğrulama" 1–5)**

Run: `.venv/bin/pytest -v` → all pass. Confirm: the Task 2 raw-vs-parquet totals are in `docs/data-notes.md`; the notebook ran clean; the panel's backtest tile equals the README number; `git status` shows no raw data staged and `du -sh .git` is small.

- [ ] **Step 6: Commit**

```bash
git add analysis.ipynb README.md tests/test_readme.py
git commit -m "docs: analysis notebook and README with findings"
```

- [ ] **Step 7: Stop and report**

Report to Batuhan: findings, backtest numbers (including if groups did not help), screenshots, and anything that deviated from the spec. Ask before creating a GitHub repo or deploying.
