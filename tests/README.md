# Tests

An automated regression test suite covering every detection path validated
manually throughout this project's development. This directly closes the
gap flagged in `docs/08_Future_Work.md` — previously, every false-positive/
true-positive check was run once in a sandbox and thrown away; now it's
checked automatically.

## Running the tests

```bash
pip install pytest
pytest tests/
```

## What's covered

| File | Covers |
|---|---|
| `test_mnf_and_intermittent.py` | Minimum Night Flow (fixed + adaptive trough), intermittent/duty-cycled leak detection |
| `test_mann_kendall.py` | Trend detection fallback for accounts with no reliable night trough, including a false-positive-rate regression guard |
| `test_burst_detection.py` | Both burst paths (strict consecutive + cumulative/fluctuating), including a direct regression guard for the original untested Option 7 false-positive bug |
| `test_seasonal_confound.py` | Calendar confound flagging, and the Ramadan-specific mechanism fixes (night-hour shifting for Residential, MNF bypass for Commercial/Hotel) |
| `test_peer_comparison.py` | Portfolio-level cohort comparison — outlier boosting, shared-cause capping, small-cohort skip |
| `test_data_handling.py` | Header row auto-detection, insufficient-history skip, malformed-file error handling |

## A real bug this suite caught on first run

Writing this suite immediately caught a genuine bug in
`MNF_Applicable`: it was being returned as `numpy.bool_` instead of a native
Python `bool`, due to how Python's `and` operator short-circuits between a
plain bool and a numpy comparison result. This silently breaks two things:
- `json.dumps()` fails on `numpy.bool_` — a real problem if this pipeline's
  output ever needs to feed a JSON API.
- `value is True` / `value is False` identity comparisons silently fail even
  when the value is logically correct, since `numpy.bool_(True) is True`
  evaluates to `False` in Python.

Fixed by explicitly casting to `bool(...)` at the point `MNF_Applicable` is
computed. This is exactly the kind of subtle, easy-to-miss correctness issue
an automated suite is for — it was found by writing the very first version
of `test_mnf_and_intermittent.py` and `test_mann_kendall.py`, not by manual
inspection.

## Environment note

This suite was developed and validated in an environment without network
access to install `pytest`, so every test function was verified by manually
invoking it with hand-wired fixture equivalents (bypassing `pytest`'s
fixture injection, but exercising the exact same test logic and
assertions). All 24 tests passed against the fixed source. Run
`pytest tests/` yourself in a normal environment as the first thing you do
after cloning this repo, to confirm the same result end-to-end with real
pytest fixture wiring.

## A note on test data dates

Several tests use `pd.date_range("2026-01-01", ...)` for a default 12-week
window. Be aware that a 12-week window starting January 1, 2026 lands its
"recent evaluation" period inside Ramadan 2026 — this was discovered while
writing this suite (see `test_seasonal_confound.py` for tests that
deliberately exploit this) and caused four initial test failures, all
correctly traced to `is True`/`is False` comparisons against `numpy.bool_`
rather than to the Ramadan interaction itself, once debugged directly. If
you add new tests with a default date range, check whether it
unintentionally overlaps a confound period in
`leak_detection._FIXED_YEAR_CONFOUND_PERIODS` — that's a common way to get
a confusing, hard-to-diagnose test failure.
