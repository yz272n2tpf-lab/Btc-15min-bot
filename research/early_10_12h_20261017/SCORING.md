# EARLY 10–12-hour evaluation contract

This defines the report before observing new outcomes. It does not change the
strategy, entry policy, source freshness, timing, or signal-only behavior.
Recommend 10 hours (40 full 15-minute contracts), fixed before capture. Choose
12 hours (48 contracts) only before starting, with separately verified capacity;
do not extend or stop based on wins or losses. Preparation and settlement tail
are outside the scored interval. A tail timeout leaves outcomes pending.

## Cohort and evidence gates

Freeze build/tree, configuration hashes, native owner identities, exact start/end
UTC boundaries and complete contract roster. Preserve all observations, PASS
states, unavailable states, gaps and rejected entries. Never select only settled
winners, cheap entries or intervals with working capture.

The primary unit is a unique original EARLY `origin_id`/native BUY. Report both
unique origin count and unique contract count; repeated WATCH/HOLD/EXIT records
must not create entries. FINAL and SCALP remain separate context, not EARLY buys.

A qualified entry must have the original native BUY and publication record,
exact source/quote/vector/contract associations, unchanged <=5-second source
freshness and all existing timing/publication gates, and a verified original
ask on the signaled UP or DOWN side. Quote receipt and proof must exist by the
original decision/publication cutoff. No later quote, candle, corrected source
or settlement may qualify an earlier BUY. Preserve each failure reason and
unavailable denominator. A signal is not a manual fill or an executed trade.

All roles must have complete seals, zero original losses, full native journal
ranges, unchanged strategy/proof behavior and verified integrity. A failed
capture may support an explicitly bounded diagnostic subset, but cannot pass
the complete 10-hour evaluation. Reader restart must yield identical results.

## Required report tables

1. **Run health and coverage:** every contract, official open/close/target,
   source-ready and quote-ready times, rollover latency, first eligible analysis,
   BUY/PASS/unavailable counts, gaps, observed vs expected journal ranges,
   capture and reader resource peaks, stop/drain/seal status, restart proofs.
   Distinguish no edge, readiness failure and missing evidence.

2. **Entries:** origin/native/publication identifiers; side; decision, receipt
   and publication timestamps; elapsed and seconds remaining; exact original
   bid/ask; source ages; entry gate results; proof and journal references.
   Show all qualified BUYs. Descriptive price bins: <25c, 25–35c, >35–50c,
   >50–<80c, >=80c. Show <=50c coverage and 25–35c coverage. These bins do not
   retrospectively exclude entries or change native entry thresholds.
   Timing bins: 0–3, >3–5, >5–7, >7–10, >10–15 minutes elapsed; include median,
   range and individual observations. Preserve the goal of useful early entry.

3. **Outcome accuracy:** authoritative Kalshi result and receipt timestamp,
   verified contract identity and settlement links. Report wins / settled
   qualified BUYs, plus total qualified, pending, invalid/unqualified, duplicate
   and uncovered counts. Report both origin and contract-level denominators.
   Use a two-sided 95% Wilson interval and disclose within-contract dependence;
   do not interpret a small correlated cohort as independent validation.
   Zero qualified or settled BUYs means N/A, never 0% or 100% accuracy.
   A 10–12-hour run cannot by itself establish a 93–95% long-run accuracy claim.

4. **Management and exits:** ordered ENTER/WATCH/HOLD/PROTECT/EXIT states tied
   to the same original origin; first warning/protection/terminal times; exact
   contemporaneous executable exit BID; original entry ASK; reason and immutable
   quote identity. Deduplicate latched terminal records. Show quote-based gross
   cents (exit bid minus entry ask), hold-to-official-settlement value and
   missed/protected move comparisons separately. Fees only from recorded exact
   applicable fee evidence; otherwise label gross before fees. No fills,
   slippage or realized P&L are inferred. User-supplied manual fills, if any,
   form a separate execution table with their own provenance.

5. **Missed opportunities:** enumerate every no-BUY contract and its original
   PASS/unavailable/blocked reasons. Distinguish an originally eligible signal
   blocked before publication, a valid PASS that later moved favorably, and
   an interval impossible to judge because data were missing. Any retrospective
   opportunity scan is descriptive and separately labeled, uses only recorded
   same-side executable asks/bids, and discloses observation resolution and
   subsequent price horizon. Do not invent unobserved intra-gap moves or count
   hindsight opportunities as signals the strategy emitted. Report missing
   source/quote/publication readiness as infrastructure misses, not model errors.

6. **Authoritative settlements:** exact ticker, official boundary/target,
   original status/result bytes and hash, original HTTP receipt, acceptance and
   native settlement journal identity. Verify duplicate/conflicting results.
   BRTI closeout is useful supporting evidence, not a substitute for missing
   authoritative Kalshi settlement. Keep pending/canceled/void separate.

## Post-evaluation decisions

Present engineering completeness and EARLY behavior as separate verdicts.
Review demonstrated weaknesses in entry quality, timing, qualification,
management and exits. Any later correction requires a separately reviewed
commit and fresh forward evidence; do not retune against this cohort and then
relabel the same observations an untouched success. Complete production
acceptance (including producer recovery and live timing) before launching the
signal-only bot. Reassess after several days of new forward live evidence.

This document creates no scheduled automation and authorizes no capture,
deployment, configuration change, restart, order or bot launch.
