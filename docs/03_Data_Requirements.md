# Data Requirements

## Required file format

- **File types:** `.xlsx`, `.xls`, or `.csv`
- **Required columns** (exact names, case-sensitive):
  - `Hourly` — hourly-resolution timestamp
  - `Consumption m3` — consumption for that hour, in cubic meters
- **Header row position:** flexible. The pipeline scans the first 10 rows of
  each file for the row that literally contains both column names, so files
  with title/metadata rows above the real header still parse correctly. If
  neither column name is found in the first 10 rows, row 0 is used as a
  fallback (will error clearly if that's also wrong, rather than silently
  misparsing).

## Folder structure

Files must be organized in subfolders by customer category, with the
subfolder name used directly to select detection thresholds:

```
customers/
├── Villa (Residential)/
├── Flat (Residential)/
├── Commercial/
├── Hotel/
├── Government/
└── Industrial (Subsidized)/
```

Category matching is **substring-based** on the folder name:
- Contains `"Residential"`, `"Villa"`, or `"Flat"` → Residential thresholds
- Contains `"Government"` → Government thresholds
- Contains `"Industrial"` → Industrial thresholds
- Everything else → Commercial/Hotel thresholds

**Known limitation:** this matching is order-dependent and can misfire on
folder names that combine keywords (e.g. a folder literally named
`"Government Villas"` would match Residential first). Rename folders to
avoid ambiguous combinations rather than relying on the matching logic to
disambiguate.

## Minimum data footprint

- **Absolute minimum:** at least 4 weeks of history *before* the most recent
  4 weeks (i.e. the file's earliest timestamp must be more than 4 weeks
  before its latest). Files that don't meet this are `SKIPPED`, not
  evaluated.
- **Recommended minimum:** 12 weeks total (8-week baseline + 4-week
  evaluation window) for any result to be meaningful.
- **For Mann-Kendall trend detection specifically:** at least 14 clean
  recent days with ≥90% hourly coverage each. Falls through with an
  explanatory note if this isn't met.
- **For statistically-learned seasonality** (not yet implemented — see
  `08_Future_Work.md`): would need 1+ years of history per customer. The
  current system's seasonal handling is a rule-based calendar lookup, not
  learned from data, specifically because this volume of history isn't
  available yet.

## Data quality expectations

- **Missing hours:** handled — the pipeline reindexes to a complete hourly
  grid and tracks completeness explicitly (`Data_Completeness_Recent`,
  `Data_Completeness_Night`).
- **Duplicate timestamps:** dropped (first occurrence kept) during ingestion.
- **Negative readings, meter rollbacks, DST transitions:** **not currently
  handled** — see `08_Future_Work.md`. Real utility exports may contain
  these and should be checked before trusting results at scale.
- **Units:** assumed to be consistent m³ per hour across all files. No
  automatic unit-consistency check exists yet.

## Sensitive data handling

Customer consumption files are private data and must never be committed to
version control. See the repository's `.gitignore` and `data/README.md` for
the current exclusion rules. Only fully synthetic or clearly anonymized
sample data belongs in this repository.