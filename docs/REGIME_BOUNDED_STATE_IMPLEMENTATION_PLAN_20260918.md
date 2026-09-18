# REGIME BOUNDED-STATE IMPLEMENTATION PLAN — 2026-09-18

## Proven before this step
- V2 disk transport steady-state ~0.03-0.05 GB, zero public TX, read-only/no-orders.
- Exact V2 delta reconstruction is SHA/byte gated.
- Identical frozen Regime analyzer fed by V2 reproduces live-control Regime evolution closely.
- Full Regime analyzer still costs ~2.8-3.2 GB steady, with larger reconstruction spikes.
Conclusion: remaining cost is consumer object-graph/full-history analysis, not transport.

## Non-negotiable semantic invariants
- VERSION BTC15_SCALP_REGIME_FORWARD_OBSERVATION_V1_1_FROZEN.
- cutoff 2026-09-16T11:03:16+00:00.
- ARM_GAIN=0.05, GIVEBACK=0.04.
- readiness 100 future full contracts / 50 protected exits.
- fixed V1.1 regime tags and boolean semantics.
- no threshold selection, no signal suppression/rescue, automatic_promotion=false, orders=false.
- same contract denominator definition: first passive observation >= cutoff AND fully observed >=840s through <=60s.
- same serial opportunity lifecycle/economics.

## Bounded-state architecture
1. Consume V2 deltas incrementally; never materialize entire canonical CSV in Python heap.
2. Parse complete CSV records from each chunk with a carry buffer only for partial record.
3. Discard rows that can be proven irrelevant to post-cutoff universe once header/schema metadata is known.
4. Maintain per-contract compact state only for contracts that can qualify at/after cutoff:
   - first_seen/min_seconds_left/max_seconds_left/full-observation flags
   - candidate causal fields required by opportunity builder/schema adapter
   - lifecycle observations needed for +5/+10/+20, protected exit and capture economics
   - opportunity index and finalized compact records
5. Once a contract is finalized, retain only compact finalized records + denominator metadata; discard raw observations.
6. Persist checkpoint atomically to disk with source offset/source SHA/cutoff/version.
7. On restart, resume from checkpoint offset. If V2 generation/source boundary invalidates offset, fail closed and rebuild bounded state from V2 stream.
8. Expose /health /summary /state compatible with frozen Regime observer.

## Acceptance gate
At SAME V2 source boundary:
- exact future_contract_ids
- future_full_contracts
- serial covered IDs/count
- compact overall metrics
- primary/overlapping incidence
- primary regimes
- by-opportunity-index
- evidence readiness
must equal frozen full-history analyzer.
RAM target <=0.35 GB steady and no multi-GB refresh spike.
Any mismatch => STOP; protected Regime unchanged.
