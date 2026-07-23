# Archive

This folder holds the last few superseded versions of the main detection
notebook, kept for quick reference and rollback — the current, canonical
version lives at `notebooks/leak_detection.ipynb` (originally `v7`).

Full version history is also tracked in git commits (see the repo's commit
log). This folder is a convenience layer on top of that — instant file
access without needing git commands — not a replacement for it. Only the
most recent superseded versions are kept here; older versions
(`v3` and everything under the old `previousVersionsOfMainCode/` folder)
were intentionally not carried into this repository. Git history (from the
point this repo was initialized) is the record for anything older than
what's listed below.

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

| File | What changed / why superseded | Verified clean? |
|---|---|---|
| `v4_leak_detection.ipynb` | *[fill in: summary of what this version did, and what changed in the version after it]* | ☐ |
| `v5_leak_detection.ipynb` | *[fill in]* | ☐ |
| `v6_leak_detection.ipynb` | *[fill in]* | ☐ |

For reference, the canonical version (`v7` → `notebooks/leak_detection.ipynb`)
includes: per-customer Minimum Night Flow (fixed + adaptive trough
discovery) with intermittent/duty-cycled leak detection, Mann-Kendall trend
detection as a fallback for accounts with no reliable quiet period, dual
burst detection (strict consecutive + retuned cumulative/fluctuating),
rule-based seasonal confound handling with Ramadan-specific mechanism fixes,
a priority score with full explainability, and portfolio-level peer/cohort
comparison. See [`../docs/07_Design_Decisions.md`](../docs/07_Design_Decisions.md)
for the reasoning behind each of these, if any archived version reflects an
earlier stage of that reasoning worth referencing.

*(Fill in the table above with what actually changed between your archived
versions — this document doesn't have visibility into what changed between
v4, v5, and v6 specifically, so these should be completed from your own
knowledge of the iteration history before this goes into the repo.)*