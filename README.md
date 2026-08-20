# Water Leak Detection

A decision-support tool for detecting water leaks from hourly customer
consumption data — using minimum night flow, trend analysis, and burst
detection, with seasonal and peer-comparison context to reduce false
positives caused by shared events (e.g. Ramadan) rather than individual
leaks.

> **This is a decision-support system, not an autonomous alarm.** Every
> result is meant to be reviewed by a person before any action is taken.
> See [`docs/07_Design_Decisions.md`](docs/07_Design_Decisions.md) for why.

## Project summary

Water utilities need a way to flag customers who might have a leak, using
only what most of them already collect: hourly consumption readings per
customer. There's no pressure data, no network sensors, and — at the
start of this project — no confirmed list of which customers actually had
real leaks. That last point shaped almost every decision below: without
labeled outcomes, a machine-learning model has nothing to learn from, so
this project is built as a transparent, rule-based statistical system
instead — one where every flag traces back to a specific, readable reason,
not a black-box score.

The system evolved in stages, each one built to fix a specific, real
weakness found by testing the previous version, not by guesswork:

1. **Minimum Night Flow (MNF)** — the industry-standard technique: a real
   leak runs 24 hours a day, so if a customer's quietest hour has gotten
   noticeably higher, that's a strong signal. Extended with *adaptive
   trough discovery* (for customers whose real quiet period doesn't match
   their category's assumed hours) and *intermittent leak detection* (for
   leaks that cycle on and off instead of running continuously).
2. **Mann-Kendall trend detection** — a fallback for accounts with no
   reliable quiet period at all (e.g. 24/7 operations), using a proper
   statistical trend test instead of assuming a night trough exists.
3. **Dual burst detection** — catches both a sudden spike held for several
   straight hours, and a fluctuating burst that dips in and out of the
   anomaly threshold instead of holding steady.
4. **Seasonal/calendar awareness** — a real incident during testing (an
   entire portfolio of Commercial customers got flagged at once) revealed
   that shared events like Ramadan can fool every detection path at once.
   Fixed with a rule-based calendar of known high-variance periods, plus a
   deeper, mechanism-specific fix for Ramadan itself (which uniquely
   shifts *when* people are active, not just *how much* they use).
5. **Priority scoring, not a risk percentage** — every flag gets a 0–100
   suspicion score built from which signals fired, explicitly *not*
   labeled as a calibrated probability, since there's no confirmed-outcome
   data yet to validate a real percentage against.
6. **Peer/cohort comparison** — the most general fix: compares a flagged
   customer against their category peers in the same run, so a shared,
   non-leak cause (known or unknown, not just the ones on the calendar)
   gets caught too, without ever suppressing a genuine outlier riding on
   top of it.

Every one of these was tested empirically before being trusted, and at
least two proposed improvements along the way were tried, found to make
things measurably worse, and rejected — see
[`docs/06_Validation.md`](docs/06_Validation.md) and
[`docs/07_Design_Decisions.md`](docs/07_Design_Decisions.md) for the full,
honest record of what worked, what didn't, and why.

On top of the detection logic, a SQLite backend and a two-page Power BI
dashboard have since been built: an Executive view for portfolio-level
monitoring, and an Investigation view for technicians to drill into why a
specific customer was flagged, including a per-hour timeline and a
feedback loop for logging real investigation outcomes. See
[`docs/09_Database_and_Dashboard.md`](docs/09_Database_and_Dashboard.md).

## What it does

Given hourly `(timestamp, consumption)` readings per customer, organized by
category (Residential/Villa, Commercial, Government, Industrial, Hotel),
the pipeline:

1. Detects **slow leaks** via Minimum Night Flow (with adaptive trough
   discovery and intermittent/duty-cycled detection), falling back to a
   Mann-Kendall trend test for accounts with no reliable quiet period.
2. Detects **sudden bursts**, both strictly-consecutive and fluctuating
   patterns.
3. Flags results that overlap **known seasonal/calendar confounds**
   (Ramadan, Eid, National Day, summer holidays) so a shared demand spike
   isn't mistaken for a portfolio-wide leak epidemic.
4. Compares each flagged customer against their **category peers** in the
   same run, boosting confidence for genuine outliers and softening
   over-eager flags that just reflect a shared, non-leak cause.
5. Outputs a **priority score and tier** (not a calibrated risk
   probability) with a plain-language explanation of exactly why each
   customer was flagged.
6. Stores results in a **SQLite backend** (latest state, full run history,
   and per-hour investigation detail per customer) and surfaces them
   through a **Power BI dashboard**: a portfolio-level Executive view and
   a per-customer Investigation view for technicians, including a
   feedback loop for logging real investigation outcomes. Full detail:
   [`docs/09_Database_and_Dashboard.md`](docs/09_Database_and_Dashboard.md).

## Dashboard

**Executive Dashboard** — portfolio-level monitoring: active suspected
leaks, estimated water loss and revenue at risk, priority distribution,
a network leakage trend over time, and a category/zone breakdown.

<img width="1046" height="583" alt="pg1" src="https://github.com/user-attachments/assets/872eb188-3bcd-4d73-ad84-66e4e962962f" />

<img width="1046" height="582" alt="pg2" src="https://github.com/user-attachments/assets/31466ea9-7b92-4653-9b9d-7b66262f8ae9" />


**Investigation Dashboard** — per-customer drill-down for technicians:
why a customer was flagged, supporting evidence, a full consumption
timeline with the exact hours that drove the verdict, and a feedback form
to log the real outcome once investigated.

<img width="1045" height="586" alt="pg3" src="https://github.com/user-attachments/assets/83632f24-de63-4b3c-878d-ab1f61db5359" />

<img width="2464" height="1276" alt="pg44" src="https://github.com/user-attachments/assets/272fbe75-6d68-4b9d-b998-7f18da9f7887" />




## How well does it work

Three layers of testing, each telling us something the others can't:

| Test | What it's for | Result |
|---|---|---|
| Synthetic data (many scenarios) | Isolate and fix individual bugs under controlled conditions | 0% false positives across every detection path, after fixes; every bug found this way is documented in `06_Validation.md` |
| **BATADAL** (real, external, cross-domain — network cyber-attacks, not leaks) | Check whether the underlying math generalizes to a real, independently-labeled signal at all | Weak (Precision 50%, Recall 11%) — but this is *why* the baseline-contamination weakness was found and investigated in the first place |
| **BattLeDIM** (real, external, same-domain — actual pipe leaks, customer-shaped meter data) | Check the system on the real problem it's built for | Strong: **Precision 100%, Recall 71%, F1 0.83, 0% false positives**, on 27 real test cases |

The two BattLeDIM misses land on the exact same weakness BATADAL first
revealed — two independent, real datasets confirming the same limitation
is much stronger evidence than either alone. Full methodology, every
number, and the literature backing the conclusions: see
[`docs/06_Validation.md`](docs/06_Validation.md).

**Important caveat:** all of the above is either synthetic or from public
benchmark datasets (simulated water networks). None of it is validation
against your own real customers' confirmed leak/no-leak outcomes — that
still needs to happen before treating any of these numbers as production
accuracy. See "What's still needed" below.

## Quick start

```bash
pip install -r requirements.txt
```

Place customer files under `customers/<Category>/*.{csv,xlsx,xls}` (see
[`docs/03_Data_Requirements.md`](docs/03_Data_Requirements.md) for required
columns and folder naming), then run the audit notebook:

```
notebooks/leak_detection.ipynb
```

Full setup instructions: [`docs/04_Installation.md`](docs/04_Installation.md)

To reproduce the external validation results yourself:
```bash
python notebooks/benchmarking/batadal_benchmark.py
python notebooks/benchmarking/battledim_benchmark.py
```

To run the automated test suite:
```bash
pytest tests/
```

## Repository structure

```
water-leak-detection/
├── docs/                  Full documentation (see below)
├── src/                   Core detection logic (importable module)
│   ├── leak_detection_pipeline.py   Detection engine (file-based + DataFrame wrapper)
│   ├── leak_detection_database.py   SQLite adapter + business impact estimation
│   ├── run_detection.py             Pipeline orchestration script
│   └── database.py                  SQLite connection helper (see note below)
├── database/               Schema/setup scripts, gitignored .db file itself
├── dashboard/               .pbix file + sanitized screenshots
├── notebooks/
│   ├── leak_detection.ipynb    Main pipeline notebook
│   ├── exploratory/             Early exploratory analysis (partial EDA)
│   └── benchmarking/            Benchmark scripts + synthetic data generation
├── data/
│   └── benchmarking/            Synthetic + public benchmark datasets only
├── archive/                Superseded notebook versions, kept for rollback
├── results/                 Generated output (gitignored)
├── tests/                    24 automated tests — see tests/README.md
├── requirements.txt
└── .gitignore
```

> **The `database/` and `dashboard/` folder layout above is a proposed
> structure, not yet confirmed against where you actually put these
> files.** `database.py` and `config.py` (which `database.py` imports
> `DATABASE_PATH` from via a relative import — see
> `09_Database_and_Dashboard.md` for a possible import-structure gotcha
> this implies) haven't been fully reviewed yet — let me know the actual
> layout and I'll correct this section to match.

**Not included in this repository:** real customer data (`customers/`),
the SQLite database file itself (contains real customer records),
generated audit outputs, and any file containing customer names or
identifiable information. See `.gitignore` and
[`data/README.md`](data/README.md).

## Documentation

| Doc | Contents |
|---|---|
| [`01_System_Architecture.md`](docs/01_System_Architecture.md) | Pipeline flow, module map, the self-comparison / peer-comparison split |
| [`02_Algorithm_Design.md`](docs/02_Algorithm_Design.md) | Every detection path in detail — thresholds, formulas, what each catches |
| [`03_Data_Requirements.md`](docs/03_Data_Requirements.md) | Required columns, folder structure, minimum data footprint |
| [`04_Installation.md`](docs/04_Installation.md) | Setup and how to run |
| [`05_User_Guide.md`](docs/05_User_Guide.md) | How to read the output, what a flag does and doesn't mean |
| [`06_Validation.md`](docs/06_Validation.md) | All tested numbers — synthetic, BATADAL, BattLeDIM — and the real-data incident that shaped seasonal handling |
| [`07_Design_Decisions.md`](docs/07_Design_Decisions.md) | Why MNF over ML, why Mann-Kendall over CUSUM, why peer comparison only boosts, and other tradeoffs |
| [`08_Future_Work.md`](docs/08_Future_Work.md) | What's blocked on more data vs. what's just unbuilt architecture |
| [`09_Database_and_Dashboard.md`](docs/09_Database_and_Dashboard.md) | SQLite schema, pipeline orchestration, and the Power BI dashboard layer |

## Current status and what's still needed

This is a **validated proof-of-concept for the detection logic and
architecture**, not a production-hardened system. What's genuinely solid,
and what's genuinely still missing:

**Solid:**
- Every detection path is tested — synthetically, and against two real,
  independent external datasets (see "How well does it work" above).
- A 24-test automated regression suite (`tests/`) catches regressions
  automatically, including a real type-consistency bug found on its first
  run (see `06_Validation.md`).
- Known weaknesses are disclosed in the output itself (e.g.
  `Seasonal_Confound_Recent`, `MNF_Applicable`), not hidden.

**Still missing, split by what actually unblocks each one:**

| Needs more data (not more code) | Needs more engineering (buildable now, not yet built) |
|---|---|
| Validation against *your own* customers' confirmed outcomes — the mechanism now exists (`TechnicianFeedback` table, see `09_Database_and_Dashboard.md`), but needs real technician use before it produces validation data | Extending the deep Ramadan-style fix to other seasonal confounds |
| Learned/calibrated thresholds (currently hand-set) | Routing the burst-detection paths through the same seasonal logic MNF already has |
| A real calibrated risk probability, replacing the priority score | Hardening against messy real-world data (negative readings, DST transitions, duplicate meters, inconsistent units) |
| A machine-learning fix for baseline contamination (proven genuinely hard — see `06_Validation.md`) | Changepoint detection as a more principled contamination approach (researched, not yet built) |

None of this blocks using the system as a **decision-support tool with
human review** — which is its intended use today. Full detail and
priority order: [`08_Future_Work.md`](docs/08_Future_Work.md).

## Data privacy

Customer consumption data is private and must never be committed to this
repository. See [`.gitignore`](.gitignore) and
[`data/README.md`](data/README.md) for the current exclusion rules before
adding any new files.
