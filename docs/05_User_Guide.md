# User Guide

## What this tool is (and isn't)

This is a **decision-support tool**, not an autonomous alarm system. Every
result is meant to be reviewed by a person before any action is taken — the
`Priority_Tier` labels ("Dispatch", "Monitor", "Review Only") are explicitly
phrased as recommendations for a human, not automated triggers. See
`07_Design_Decisions.md` for why it isn't ready for autonomous use.

## Running an audit

See `04_Installation.md` for setup. In short: point `base_folder` at your
`customers/` directory and run the audit cell. This produces
`portfolio_leakage_audit_summary.csv`.

## Reading the output

| Column | What it means |
|---|---|
| `Status` | `SUCCESS`, `SKIPPED` (not enough history), or `ERROR` (file couldn't be processed — check `Details`) |
| `Leak_Suspected` | `YES`/`NO` — did *any* detection path fire |
| `Priority_Score` | 0–100 additive suspicion score. **Not a calibrated probability** — see below |
| `Priority_Tier` | `High - Dispatch`, `Medium - Monitor`, `Low - Review Only`, or `None` — recommended triage action |
| `Priority_Reasons` | Every signal that fired, with its point contribution — this is the "why" |
| `Details` | Same reasons in narrative form, plus advisory notes (seasonal overlap, adaptive trough used, etc.) |
| `Seasonal_Confound_Recent` | Known calendar event(s) overlapping this evaluation, if any |
| `Peer_Comparison_Note` | How this customer's rise compares to their category peers this run |
| `MNF_Applicable`, `Trough_Detection_Method` | Whether Minimum Night Flow could be evaluated, and how |
| `MK_Evaluated`, `MK_P_Value`, `MK_Sen_Slope` | Mann-Kendall trend test details, if used |
| `Data_Completeness_Recent`, `Data_Completeness_Night` | How much of the expected recent data was actually present |

## How to interpret `Priority_Score`

It is **not** a percentage chance of a real leak. It's an additive score
built from which independent statistical signals fired (see
`02_Algorithm_Design.md` for the point values). Treat it as a ranking tool
for where to spend investigation time first, not as a calibrated risk
probability — there is no labeled outcome data yet to validate a real
probability against.

## A `YES` result doesn't always mean "dispatch a technician"

Check these fields before acting on any flag:

1. **`Seasonal_Confound_Recent`** — if populated, the flag may reflect normal
   seasonal demand (e.g. Ramadan) rather than a leak. The tier is
   automatically capped below "High - Dispatch" in this case unless peer
   comparison shows the customer stood out even among affected peers.
2. **`Peer_Comparison_Note`** — if it says "consistent with... category's
   typical change," many other customers in the same category showed a
   similar rise this run, which is evidence of a shared cause rather than an
   individual leak.
3. **`Data_Completeness_Recent`** — a low value means the result is based on
   incomplete data and should be treated with extra caution regardless of
   score.
4. **`MNF_Applicable: False`** — this account has no reliable quiet period
   (24/7 operation, or Ramadan-affected Commercial/Hotel), so slow-leak
   detection relied on Mann-Kendall instead of the more direct MNF check.

## A `NO` result doesn't always mean "confirmed clean"

Check `MNF_Evaluated` and `MK_Evaluated` — if both are `False` and
`MNF_Applicable` is also `False`, the account may not have had enough clean
data for either slow-leak method to run at all. A `NO` in that case means
"nothing was caught," not "confirmed no leak."

## Example workflow

1. Run the audit.
2. Sort `portfolio_leakage_audit_summary.csv` by `Priority_Score` descending.
3. For each `High - Dispatch` result, read `Priority_Reasons` and check for
   a `Seasonal_Confound_Recent` or cautionary `Peer_Comparison_Note` before
   acting.
4. For `Medium - Monitor` results, re-check in the next audit cycle to see
   if the signal persists or was a one-off.
5. Log actual outcomes (confirmed leak, false alarm, inconclusive) somewhere
   — this is the data needed to eventually calibrate thresholds and move
   toward a real risk probability (see `08_Future_Work.md`).