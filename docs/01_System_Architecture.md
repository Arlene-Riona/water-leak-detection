# System Architecture

## Overview

The system audits water customers for potential leaks using only hourly
consumption readings (`Hourly` timestamp, `Consumption m3` volume) — no
pressure sensors, no network topology, no labeled leak history. It runs in
two passes:

1. **Per-customer evaluation** (`analyze_leak_production_grade`) — every file
   is evaluated independently, using only that customer's own history as its
   baseline.
2. **Portfolio-level peer comparison** (`_apply_peer_comparison`) — a second
   pass, run once per category after every file in that category has been
   individually evaluated, that adjusts confidence based on how a flagged
   customer compares to their category peers *in the same run*.

This two-pass split is deliberate: a single-file function can never know
whether "everyone in Commercial spiked at once" — that requires seeing the
whole cohort, which only exists once every file has already been scored.

## Pipeline flow (per customer)

```mermaid
flowchart TD
    A[Load file<br/>auto-detect header row] --> B[Reindex to complete<br/>hourly grid]
    B --> C[Split into 8wk baseline<br/>+ 4wk recent evaluation]
    C --> D[Seasonal / calendar<br/>confound check]
    D --> E[Compute per-hour-of-week<br/>baseline median + std]
    E --> F{Night trough exists?}
    F -->|Yes, fixed hours| G[Attempt 1: MNF<br/>fixed category hours]
    F -->|No| H[Attempt 2: MNF<br/>adaptive trough discovery]
    H -->|Still no trough| I[Attempt 3: Mann-Kendall<br/>trend + Sen's slope]
    G --> J[Slow Constant Leak /<br/>Intermittent Slow Leak check]
    H --> J
    I --> K[Slow Trend Leak check]
    J --> L[Burst check:<br/>strict consecutive]
    K --> L
    L -->|Not consecutive| M[Cumulative / fluctuating<br/>burst check]
    L --> N[Priority Score + Tier<br/>+ explainability]
    M --> N
    N --> O[Return per-file result]
```

## Pipeline flow (portfolio level)

```mermaid
flowchart TD
    A[Crawl customers/ folder tree] --> B[Run per-customer evaluation<br/>on every file]
    B --> C[Group SUCCESS results<br/>by category folder]
    C --> D{Cohort size >= 5?}
    D -->|No| E[Skip peer comparison<br/>leave result as-is]
    D -->|Yes| F[Compute cohort median +<br/>MAD of demand change]
    F --> G{Customer's own change<br/>vs cohort}
    G -->|Far above peers| H[Boost score + tier<br/>overrides seasonal cap]
    G -->|Consistent with peers| I[Cap tier only<br/>never touch score/reasons]
    G -->|Ambiguous| J[No adjustment]
    H --> K[Export portfolio_leakage_audit_summary.csv]
    I --> K
    J --> K
    E --> K
```

## Module map

| File / function | Responsibility |
|---|---|
| `_detect_header_row` | Locates the real header row in files with extra title/metadata rows above the actual columns |
| `_get_confound_periods` / `_find_confound_overlaps` | Rule-based lookup of known regional high-variance calendar periods (Ramadan/Eid, National Day, summer holidays, New Year) |
| `_mann_kendall_trend` | Nonparametric trend test + Sen's slope estimator, used as the slow-leak fallback for accounts with no reliable night trough |
| `_compute_night_floor` | Shared Minimum Night Flow computation (historical floor, rolling recent floor, evaluation validity, daily-minimum series) — reused by both the fixed-hours and adaptive-hours attempts |
| `analyze_leak_production_grade` | The core per-customer engine — runs all detection paths and returns one result dict per file |
| `_apply_peer_comparison` | Second-pass, portfolio-level confidence adjustment based on category cohort comparison |
| `run_portfolio_leak_audit` | Crawls the customer folder tree, calls the per-file engine on every file, then applies peer comparison, then exports the CSV |

## Design principle: self-comparison is the only thing that can create a flag

Every layer above self-comparison (seasonal confound handling, peer
comparison) is a **confidence modifier**, never a detector in its own right.
Nothing outside the core per-file statistical tests (MNF, Mann-Kendall,
burst) can turn a `NO` into a `YES`. This is intentional: it keeps every
"why was this flagged" answer traceable to one of three well-defined,
independently-validated statistical mechanisms, rather than to an opaque
combination of adjustments.