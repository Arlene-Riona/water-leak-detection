# Water Leak Detection

A decision-support tool for detecting water leaks from hourly customer
consumption data — using minimum night flow, trend analysis, and burst
detection, with seasonal and peer-comparison context to reduce false
positives caused by shared events (e.g. Ramadan) rather than individual
leaks.

> **This is a decision-support system, not an autonomous alarm.** Every
> result is meant to be reviewed by a person before any action is taken.
> See [`docs/07_Design_Decisions.md`](docs/07_Design_Decisions.md) for why.

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

## Repository structure

```
water-leak-detection/
├── docs/                  Full documentation (see below)
├── src/                   Core detection logic (importable module)
├── notebooks/
│   ├── leak_detection.ipynb    Main pipeline notebook
│   ├── exploratory/             Early exploratory analysis (partial EDA)
│   └── benchmarking/            Synthetic data generation + benchmark tests
├── data/
│   └── benchmarking/            Synthetic/benchmark datasets only
├── archive/                Recent superseded versions, kept for rollback
├── results/                 Generated output (gitignored)
├── tests/                    (planned — see docs/08_Future_Work.md)
├── requirements.txt
└── .gitignore
```

**Not included in this repository:** real customer data (`customers/`),
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
| [`06_Validation.md`](docs/06_Validation.md) | All tested false-positive/true-positive numbers, and the real-data incident that shaped seasonal handling |
| [`07_Design_Decisions.md`](docs/07_Design_Decisions.md) | Why MNF over ML, why Mann-Kendall over CUSUM, why peer comparison only boosts, and other tradeoffs |
| [`08_Future_Work.md`](docs/08_Future_Work.md) | What's blocked on more data vs. what's just unbuilt architecture |

## Current status

This is a **validated proof-of-concept for the detection logic and
architecture**, not a production-hardened system. Specifically:

- All validation to date uses **synthetic data**; no confirmed real-world
  leak/no-leak outcomes exist yet to calibrate against.
- All thresholds are hand-set engineering judgment, not fitted to outcomes.
- Not yet hardened against real-world data issues (negative readings, DST
  transitions, duplicate meters, inconsistent units).
- No automated regression test suite exists yet.

None of this blocks using it as a **decision-support tool with human
review** — which is its intended use today. See
[`08_Future_Work.md`](docs/08_Future_Work.md) for the concrete path from
here to something closer to production-ready.

## Data privacy

Customer consumption data is private and must never be committed to this
repository. See [`.gitignore`](.gitignore) and
[`data/README.md`](data/README.md) for the current exclusion rules before
adding any new files.