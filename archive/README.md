# Archive

This folder holds every superseded version of the main detection notebook,
from the original starting point through the last version before the
current one. The current, canonical version lives at
`notebooks/leak_detection.ipynb` (originally `v7`).

Full version history is also tracked in git commits (see the repo's commit
log) once this repo is actually committed to. This folder is a convenience
layer on top of that — instant file access without needing git commands —
not a replacement for it.

## What's in here

Each major logic improvement during development resulted in a new
notebook rather than an edit to the existing one, which is why this many
versioned files exist. Individual changes between each version were not
tracked in detail at the time, so the files below are kept as broad
historical snapshots, not a changelog:

- `generic_leak_detection_for_all_customers.ipynb`
- `v2_generic_leak_detection_for_all_customers.ipynb`
- `v3_generic_leak_detection_for_all_customers.ipynb`
- `v4_generic_leak_detection_for_all_customers.ipynb`
- `v5_generic_leak_detection_for_all_customers.ipynb`
- `v6_generic_leak_detection_for_all_customers.ipynb`

All six have had their outputs cleared and been scrubbed for customer
names/identifiers (see below for the process used).

For reference, the canonical version (`v7` → `notebooks/leak_detection.ipynb`)
includes: per-customer Minimum Night Flow (fixed + adaptive trough
discovery) with intermittent/duty-cycled leak detection, Mann-Kendall trend
detection as a fallback for accounts with no reliable quiet period, dual
burst detection (strict consecutive + retuned cumulative/fluctuating),
rule-based seasonal confound handling with Ramadan-specific mechanism fixes,
a priority score with full explainability, and portfolio-level peer/cohort
comparison — none of which exists in the earlier archived files here. See
[`../docs/07_Design_Decisions.md`](../docs/07_Design_Decisions.md) for the
reasoning behind each of these additions, and comparing any archived file
against `v7` shows the full distance the logic traveled from a flat,
single-threshold rule set to the current system.

## Before adding anything new to this folder

These notebooks were run against real customer data at various points. If
any file is ever added or updated here in future, apply the same rule
used for everything already in this folder:

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