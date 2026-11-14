# Backtest runs

Every run of `scripts/run_backtests.py` is kept as its own CSV here; none is overwritten. Errors are
boardings-weighted (WAPE, Σ|a−p| ÷ Σa, the headline) and unweighted (MAPE, mean of |a−p| ÷ a).
Station-day errors include hours 0–5 (0.69% of boardings); line-band errors cover only the card's
bands, 06–23.

| File | Groups | Closed-station days in profile and baseline |
|---|---|---|
| `before-review.csv` | built once on the whole analysis period | kept (old behaviour) |
| `old-settings-recheck.csv` | same as above, rerun after the review changes | kept; identical to `before-review.csv` (max difference 0) |
| `regroup.csv` | rebuilt from data before each cut | kept |
| `closed-0.2.csv` | whole period | left out (threshold 0.2) |
| `closed-0.2-regroup.csv` | rebuilt before each cut | left out (threshold 0.2) |

## Closed-station days

A normal (non-special) day on which a unit's boardings are below **20% of that unit's median for the
same day type** is a closed-station day. The median uses only days before the cut, and days before a
station opened are not counted. Closed days are left out of the typical profile and of the
special-day baseline, but they are still scored. Before 2024-08-01 this marks 1,214 unit-days at 113
of 383 units (most: M7 Veysel Karani Doğu 129 days, T4 Bastabya 87, M3 Şehir Hastanesi 77). Days
such as 1 May are public holidays, so they were never part of a profile or baseline in the first place.

## WAPE, % (old → new)

| Test | Level | Old (whole-period groups) | Groups rebuilt before cut | Closed days out | Both |
|---|---|---|---|---|---|
| Main Apr–May 2024, station-day | none | 12.6 | 12.5 | 12.6 | 12.5 |
| | station | 10.7 | 10.6 | 10.7 | 10.6 |
| | group | 11.6 | 11.4 | 11.6 | 11.4 |
| Extra Jun–Jul 2024, station-day | none | 23.1 | 23.2 | 23.1 | 23.2 |
| | station | 15.3 | 15.2 | 15.2 | 15.2 |
| | group | 15.9 | 16.0 | 15.8 | 15.8 |
| Public holidays 2024 (5 days) | none | 37.2 | 37.1 | 37.2 | 37.1 |
| | station | 33.3 | 33.1 | 33.2 | 33.0 |
| | group | 36.8 | 36.3 | 36.7 | 36.2 |
| Religious holidays 2024 (9 days) | none | 50.0 | 50.2 | 50.0 | 50.2 |
| | station | 23.7 | 23.4 | 23.6 | 23.3 |
| | group | 32.0 | 31.2 | 31.9 | 31.1 |
| School breaks 2024 (40 days) | none | 21.1 | 21.2 | 21.1 | 21.2 |
| | station | 9.7 | 9.6 | 9.6 | 9.6 |
| | group | 10.9 | 10.9 | 10.8 | 10.8 |
| Complete days Aug–Oct 2024 (19), network-day | none | 15.2 | 15.2 | 15.3 | 15.3 |
| | station | 10.5 | 10.5 | 10.6 | 10.6 |
| | group | 10.6 | 10.6 | 10.7 | 10.7 |

The extra-window station value was quoted earlier as 15.3; the CSV has 15.25, which rounds to 15.2.
The MAPE values and the line-band errors for all runs are in the CSV files.

## What changed

- Rebuilding groups before each cut moves WAPE by at most 0.8 points (religious holidays, group level:
  32.0 → 31.2). The conclusion stays the same: station-level factors beat group-level factors in every test.
- Leaving out closed-station days moves WAPE by at most 0.1 points. The large unweighted MAPE values
  (e.g. 77.7–82.0% in April–May, 7–8× on public holidays) come from closed days being *scored*, not from
  them distorting the profile, so excluding them from the inputs does not bring MAPE down.
