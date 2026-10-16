# BTC15 native EARLY recorder targeted burst correction — 2026-10-16

## Scope / decision
**Research candidate PASS for 4/4 focused offline regressions; NO-GO for authentic 24h EARLY recording or production deployment.**

This is a correction to the existing capture/recording implementation, **not a new EARLY validator**, model, strategy, service or signal source. Native MAIN/V81 production releases were **not** changed.

## Root fault measured from preserved Oct-13 capture

Read-only SSH examined original gzip evidence segments with original SHA256 envelopes verified; no original file bytes, credentials or orders were changed.

MAIN:
- 2,942 retained evidence envelopes, 8,576,026 decoded bytes.
- Exactly one `OVERSIZE` loss was reported in the original health/terminal snapshots. The original writer did **not preserve the rejected payload kind**, so its exact kind cannot be recovered from retained envelopes.
- Other retained kinds were below the recorder's 4 MiB admission cap. Do **not** infer or invent what caused the rejected oversized observation.
- Terminal `DRAIN_TIMEOUT`, seal `INCOMPLETE`; no valid full capture.

V81:
- 26,484 retained envelopes, 24,097,297 decoded bytes, 83 `EVIDENCE_GAP` envelopes.
- Normal retained evidence was dominated by `QUOTE_BYTES` (8,793), `QUOTE_RECEIVE` (8,763), and `QUOTE_ACCEPT` (8,738), ~26,294 records out of 26,484.
- Retained regular QUOTE envelopes typically ~880–890 decoded bytes, not giant records.
- Original health reported 1,466 queue-byte drops after ~10.1 seconds; terminal 1,470 drops after ~15.13 seconds. 32 MiB queue at its limit and ~30.1 MB still queued. Terminal `DRAIN_TIMEOUT`; no seal.
- Original `CompressedJournal.append` compresses and `fsync`s **each** line. The archive write throughput is an identified bottleneck, not proof that the 100-GB detached reader volume needs enlargement.

Information:
- Full 1,200s preflight `SEALED` with zero evidence losses. Do not tune unrelated information capture.

## Research-only narrow correction

Paths:
- `ops/live_recording/burst_journal_research.py` adds `BatchedEvidenceJournal` + `BufferedCaptureArchive` + `BufferedProofWriter`.
- `ops/live_recording/capture.py` on **research branch only** opts existing `RoleArchive` and existing proof worker into bounded writer batching.
- Each batch is at most 1 MiB raw or 256 complete **unchanged JSONL envelopes**. The existing `CompressedJournal` compresses and fsyncs each complete batch. The original JSON envelopes/hash chains survive unchanged; a gzip reader expands each original line. START and STOP are synchronously flushed, and missing/failed disk still fails closed.
- This improves off-path data handling only; trading-source, source-clock, quote/decision algorithm and order behavior remain untouched.
- Existing `OVERSIZE` admission limit is NOT raised, relaxed, or treated as success. On the next *separately authorized* preflight, rejected kind and charge size will be visible in bounded health without logging payload contents.

## Offline CI result

GitHub run `38923730465`, commit `b787ec1fcd64aeeccbc58aa06af6988b3644c115`:
**PASS 4 / 4 in 14.026 seconds.**
1. Original identical JSONL envelope and SHA-256 chain vs baseline capture (1,500 records), lower fsync count.
2. Quote-shaped burst: 9,000 unique messages x 3 recording envelopes = 27,000 retained QUOTE_BYTES/QUOTE_RECEIVE/QUOTE_ACCEPT, writer drained within 35s, **zero gaps/drops**, STOP preserved.
3. >4-MiB original response rejected as `OVERSIZE` and safely attributed by kind, no silent acceptance.
4. Synthetic disk quota exhaustion fails closed: no complete STOP recorded.

**Not proven:** production native arrival-rate stability, real unbounded quote bursts, actual MAIN oversized event class, 24h profile quota, production source performance equivalence.

## IMPORTANT day-profile capacity mismatch

The V81 original terminal indicated **26,484 retained records in ~15.134 seconds**. If an equivalent rate (~1,750/s) were sustained:
- Existing V81 *day* role record cap is `6,000,000 / 4 = 1,500,000` records; would be reached in ~14.3 minutes, not 24 hours.
- Existing V81 *preflight* role cap is `300,000 / 4 = 75,000`; would be reached in ~0.71 minutes.
- Existing V81 day-role compressed cap is **512 MiB**; original 3,587,665 bytes over the sampled interval would annualize to ~20.6 GB over one day **if** compression/rate stayed constant. Batching may improve compression ratio but cannot by itself remove the hard event-count cap.
- These are short-window conditional extrapolations, **not proof** the worst burst persists for a full day. The unrecorded dropped observations mean ingress may have been faster than the retained rate.
- MAIN and V81 production volumes remain finite (20 GB / 5 GB respectively). The detached 100-GB Railway reader volume does NOT increase MAIN/V81 native recorder space.

## Required next gates before live 24h GO

1. Review capture-only batching against full source/reader compatibility, including same-interval real native preflight data and abrupt termination.
2. Determine actual MAIN oversized kind with a newly authorized, bounded native preflight. If persistent, correct its specific observation framing WITHOUT dropping/forging evidence.
3. Recalculate the preflight/day capacity profiles from genuine sustained V81 event rates and storage on the **producer** volumes; preserve enough exact source/quote/proof events to judge EARLY fairly.
4. Only after bounds can support actual evidence growth, prepare reviewed release manifests and authorize controlled MAIN/V81 restart/rollover. Require all 3 roles SEALED, gap-free, and published native parity.
5. Run the approved 24-hour Railway capture and analyze the original EARLY BUY/exit/price/settlement lifecycles with the existing reader. No new validator, no Codespaces processing, and no orders.

**Production freeze remains in place.** No Railway MAIN/V81 deployments or restarts, no trading-model edits, no production volume deletion/resize, and no credential changes were performed.
