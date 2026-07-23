# Design Decisions

This document records *why* the system is built the way it is, including
approaches that were considered and deliberately not taken. It exists so a
future reader doesn't have to re-derive these tradeoffs, and doesn't mistake
a deliberate scoping decision for an oversight.

## Why Minimum Night Flow instead of a machine learning approach

The literature on water leak detection includes K-means/LVQ clustering,
Random Forest classifiers (~96% reported accuracy), and BiLSTM autoencoders,
often with higher reported accuracy than a rule-based MNF system. These were
not used because of what they require and what's actually available:

| Method | Requires | Available here |
|---|---|---|
| K-means/LVQ, PCA, CFPD | Network-zone or DMA-level flow/pressure sensors | Per-customer hourly consumption only, no pressure, no zone topology |
| Random Forest | Labeled training data (confirmed leak/no-leak) | No confirmed leak history yet |
| BiLSTM autoencoder | Large labeled training volume + training infrastructure | Same labeling gap, plus no training pipeline |

MNF was chosen because it is self-supervised in the way that matters here
(each customer is their own baseline, no labels needed), physically
grounded (the same core technique real utilities use at the DMA level, just
applied one level down), explainable (every flag traces to a specific,
readable reason), and buildable with the actual data available.

**This is not a permanent choice.** Once real outcome labels accumulate
(via confirmed leak/no-leak feedback — see `08_Future_Work.md`), the
engineered features already computed here (z-score, night trough ratio, MNF
drift, Sen's slope, data completeness) become strong candidate input
features for a future supervised model, rather than being thrown away.

## Why Mann-Kendall instead of CUSUM

Both were built. CUSUM was tried first and discarded — see
`06_Validation.md` for the numbers. The core reason: CUSUM's decision
interval is an approximated control limit that has to be empirically
re-tuned per sample size, and even after tuning it still produced a 7.5%
false-positive rate. Mann-Kendall is nonparametric (no Gaussian assumption
on the residuals) and produces a real p-value, so its false-alarm rate is
controlled directly by the significance threshold rather than approximated —
and empirically it achieved 0% false positives with higher true-positive
recall than the tuned CUSUM version.

## Why the priority score is not a risk percentage

An earlier draft of this feature (from external review) proposed labeling
it "Leak Risk = 91%". This was deliberately changed to a 0–100 "priority
score" with a tier label, because a percentage implies calibration against
real outcomes — i.e. that 91 out of 100 similarly-scored customers
historically had a confirmed leak. No such calibration exists yet. Labeling
it a probability would overstate the system's actual confidence. The score
still provides the operational value of ranking customers for investigation
while remaining statistically honest about what it is.

## Why peer/cohort comparison boosts, never suppresses

The first version of this idea used a hard AND-gate: a customer would only
be flagged as high-priority if they were elevated *both* above their own
history *and* above their category peers. This was corrected before
implementation, because it has a specific, serious flaw: a customer with a
real leak riding on top of a genuine shared cause (e.g. a real leak during
Ramadan, when the whole category's demand rises together) would look
"normal for the group" under that design and get suppressed — exactly the
case that most needs to be caught.

The corrected, implemented design is asymmetric by construction:
- Self-comparison remains the *only* thing that can create a `YES` flag.
- Peer comparison, applied only afterward to already-flagged customers, can
  **boost** confidence when a customer stands out well above their peers
  (evidence of an individual issue on top of whatever's happening broadly),
  and can only **cap the tier label** — never reduce the score or erase the
  recorded reasons — when a customer's rise looks statistically
  indistinguishable from their peers' typical rise.

This was validated directly: a synthetic customer with a real leak riding on
top of a shared category-wide rise was correctly *amplified* (boosted to
High - Dispatch), not diluted. See `06_Validation.md`.

## Why Ramadan got a deeper fix than other calendar confounds

Most calendar confounds (Eid al-Adha, UAE National Day, summer holidays, New
Year) raise general daytime demand without touching night-time behavior —
Minimum Night Flow should remain reliable through them, so they only receive
the shallow "flag and cap tier" treatment.

Ramadan is different: it specifically shifts *when* people and businesses
are active into hours normally treated as quiet (suhoor for residential
accounts, extended iftar/suhoor service hours for Commercial/Hotel
accounts) — which is the one mechanism that can actually fool MNF itself,
not just inflate demand around it. This is why Ramadan received a
mechanism-specific fix (shifted night-hours window for residential, MNF
bypass to Mann-Kendall for Commercial/Hotel) rather than only the generic
flag-and-cap treatment.

## Why an LLM-based seasonal adjustment was not built

Considered and rejected: using a live LLM/web search to estimate a
seasonal demand-increase multiplier per evaluation. Rejected because (a) a
targeted search for published, quantitative water-demand statistics during
Ramadan for the UAE commercial sector found no reliable, generalizable
source — only one residential-specific academic study covering a handful of
buildings — so there is nothing solid to look up; (b) even if a number
existed, it would be a generic industry statistic, not calibrated to an
individual customer; and (c) a live per-file LLM call breaks reproducibility
(non-deterministic results undermine the audit trail every other number in
this system provides) and adds cost/latency at portfolio scale. The
calendar-rule approach, while cruder, is deterministic, auditable, and free
to run.

## Why this remains a decision-support system, not an autonomous one

Three concrete reasons, not just general caution:

1. **No labeled outcome data.** Every validation number in `06_Validation.md`
   is from synthetic data. The one real-data test performed (a live
   Commercial audit) immediately surfaced a real problem (the Ramadan
   mass-flagging) that synthetic testing hadn't caught — direct evidence
   that synthetic validation has real blind spots.
2. **All thresholds are hand-set, not fitted.** Every multiplier, z-score
   cutoff, and priority-score point value in this system was chosen by
   engineering judgment, not learned from confirmed outcomes.
3. **No feedback loop exists yet** connecting flagged customers to actual
   investigation results. This is the specific thing that would unlock
   autonomous operation over time — not simply more months of consumption
   readings.

## Why no automated test suite exists yet (as of this writing)

Every validation check in this project was run manually, ad hoc, during
development. This is a known, explicitly accepted gap for the current
proof-of-concept scope — not an oversight to be silently assumed away. See
`08_Future_Work.md`.