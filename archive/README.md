# Archive

This folder holds early, superseded versions of the main detection
notebook — kept as a historical record of how the project started, not as
a "most recent backups" folder. The current, canonical version lives at
`notebooks/leak_detection.ipynb` (originally `v7`).

Full version history is also tracked in git commits (see the repo's commit
log). This folder is a convenience layer on top of that — instant file
access without needing git commands — not a replacement for it.

## What's actually in here, and why these two specifically

The two files kept here are the **earliest** versions of the project, not
the most recent ones:

- `generic_leak_detection_for_all_customers.ipynb` — the original,
  unversioned starting point.
- `v2_generic_leak_detection_for_all_customers.ipynb` — the first
  numbered iteration after that.

Everything between `v2` and the current `v7` (including `v3`) was not
carried into this repository — only these two oldest versions were kept,
specifically because they're useful as a "before" reference: comparing
either of these against `notebooks/leak_detection.ipynb` shows the full
distance the detection logic traveled, from a flat, single-threshold rule
set to the current multi-signal, seasonally-aware, peer-compared system
(see [`../docs/07_Design_Decisions.md`](../docs/07_Design_Decisions.md)
for why each later change was made). Git history is the record for
anything else in between.

## Before adding or updating anything in this folder

These notebooks were run against real customer data at various points.
Before any file goes in here (or is updated), the same rule applies as
everywhere else in this repo:

1. **Clear all cell outputs:**
   ```bash
   jupyter nbconvert --clear-output --inplace archive/*.ipynb
   ```
2. **Scrub source code and markdown for customer names/identifiers** — clearing
   outputs does not remove anything written directly in code or text cells:
   ```bash
   grep -rn "LLC\|Villa\|Trading\|Al \|Hotel\|Estate" archive/
   ```
   Check every hit manually before committing.

## Versions kept

Each major logic improvement during development resulted in a new
notebook rather than an edit to the existing one, which is why several
versioned files existed before this repo was cleaned up (see
[`../README.md`](../README.md) for the current, single canonical
notebook going forward). Individual changes between each version were not
tracked in detail at the time, so the two files below are kept as broad
historical snapshots, not a changelog:

| File | Verified clean? |
|---|---|
| `generic_leak_detection_for_all_customers.ipynb` | ☐ |
| `v2_generic_leak_detection_for_all_customers.ipynb` | ☐ |

For reference, the canonical version (`v7` → `notebooks/leak_detection.ipynb`)
includes: per-customer Minimum Night Flow (fixed + adaptive trough
discovery) with intermittent/duty-cycled leak detection, Mann-Kendall trend
detection as a fallback for accounts with no reliable quiet period, dual
burst detection (strict consecutive + retuned cumulative/fluctuating),
rule-based seasonal confound handling with Ramadan-specific mechanism fixes,
a priority score with full explainability, and portfolio-level peer/cohort
comparison — none of which exists in either archived file here. See
[`../docs/07_Design_Decisions.md`](../docs/07_Design_Decisions.md) for the
reasoning behind each of these additions.