# CURRENT STATE — first completed-contract checkpoint

Captured 2026-09-16 at 22:55:13 UTC (6:55 PM Eastern). Archive: `captures/20260916T225513444136Z/`.

Longitudinal tooling milestone: `nextgen_v2_longitudinal.py` now accepts explicit chronological bundle archives, rejects experiment/window drift and rewritten history, and never sums cumulative checkpoints. The first scorecard in `scorecards/first_contract/` accepted both frozen checkpoints and reports the latest totals of 1 contract / 2 signals. The complete read-only review suite passes 27 tests.

- **CONTROL:** All 49 pre-existing deployment IDs match the accepted deployment receipt; no staged Railway changes. Frozen V1 collectors remain untouched.
- **NEW SHADOW:** Combined V2 remains SUCCESS on the accepted deployment and fingerprint listed below. One full eligible contract, two serial opportunities, all four families present, and no review integrity errors. This milestone adds evidence and documentation only to the undeployed review branch.
- **BLOCKED:** 99 more full contracts and 98 more signals are needed to reach the overall manual-review floor. One contract cannot establish an advantage, false-warning rate, or lane-specific sufficiency. No winner is selected.
- **NEXT STEP:** Capture and compare the next coherent snapshot after further full contracts close, while preserving the existing code, cutoff, controls, and exit rule. Continue toward the 100-contract / 100-signal review floor; a separate prospective certification window is still required before production consideration.

## First observations — one contract only

- **SCALP-2 economics:** All three filters skipped the second opportunity at 52 cents. The V1 replay recorded a 72-cent protected exit, or +16 cents after the frozen one-lot taker/taker fee model. This is a missed profitable replay, not evidence that the new filters improve economics.
- **Dynamic Verify:** Confirmed that second opportunity immediately at 52 cents (`IMMEDIATE_STRONG`). The 30-second control entered at 77 cents and had no observed protected exit. Immediate and 5/10/15-second controls entered at the same 52 cents; there is no paired economics improvement against those controls. Dynamic Verify skipped the first opportunity, whose V1 one-lot net replay was -3 cents. These are observations, not proof of prospective filtering skill.
- **Watch:** The confirmed half-cent rule warned 29.079 seconds before the unchanged exit, 0.920 seconds later than V1 on that same opportunity, and did not warn on the other opportunity. Falling-trend V2 warned on neither. Frozen exit timestamps and economics match exactly. No materially earlier warning was demonstrated.
- **Selective Pullback:** Balanced V2 used its immediate-entry path for the same 52-cent opportunity, matching the immediate control's price and protected economics. Price-disciplined V2 and all six fixed-price V1 pullback policies took no entries. No improved pullback entry price was demonstrated.

All economics are shadow replay estimates from observed protected exits, not executed profits or total portfolio P&L. Source paths and first-seen timestamps remain outside the summary audit.

## Previous milestone — review tools

Checked 2026-09-16 at 22:34 UTC (6:34 PM Eastern). This Work thread remains the sole engineering/control authority.

- **CONTROL:** All frozen V1 services remain unchanged. A read-only Railway comparison against this work session's baseline found the same 50 services, zero changed deployment IDs, zero removed services, and no staged changes. The replacement `v81-30-45-live-feed-v2` remains SUCCESS on deployment `ae6976a2-fb93-449a-a05d-f45dc32bd478`.
- **NEW SHADOW:** `scalp-nextgen-shadow-v2` remains SUCCESS on deployment `17cac03e-20a2-46be-b535-c31f63aaf6fa`, commit `f23b4b37c0bb5f2ba5a50915933962b9eb7813a1`. Its four experiment families and 24 policy lanes remain frozen. The new `research_review/` tool belongs only to the undeployed `scalp-nextgen-v2-review-tools` branch; no service or deployment was created for it.
- **BLOCKED:** No complete post-cutoff contracts or eligible signals were present in the archived 22:30:13 UTC checkpoint. There are no performance conclusions. The exported audit also lacks full raw quote paths and contract first-observation timestamps, so independent causal/cutoff verification needs additional source evidence before later certification.
- **NEXT STEP:** Read a fresh coherent snapshot after the first full post-cutoff contract closes (around 22:45 UTC / 6:45 PM Eastern, then allow the next collector poll). Compare outcomes without modifying the frozen service. The overall 100-contract / 100-signal floor permits manual review, not promotion or a claim of lane-specific sufficiency.

## Work completed

Added a standalone, standard-library reviewer; an explicit frozen manifest; 21 passing tests; documentation; and an immutable checkpoint bundle with reproducible JSON/Markdown reports. It validates exported identity/integrity and computes 28 direct policy comparisons, with paired economics, omissions, coverage, warning lead time, and unresolved outcomes kept explicit. It never chooses or promotes a winner.

The executable makes HTTPS GET requests only to the existing shadow service. No collector code, production logic, order handling, deployment configuration, or shared source was changed.

## Accepted experiment identity

- Service: `46b79a18-0fc2-46f0-8f12-d6bac63eecad`
- Code fingerprint: `7f901c87774dd418db79a29f513b05245488a6ba0cedd6e7a8572ac9865ce55f`
- Prospective cutoff: `2026-09-16T22:30:00+00:00`
- Window: `00e73c80479a5ec5d482d33429e5f2115513dcddd93babdf38a7e38c6b7cac67`
- Archived capture: `2026-09-16T22:30:13.718240+00:00`
- Capture result: `WAITING_FOR_FULL_CONTRACT`, 0 full contracts, 0 serial signals, no integrity errors.

Signal-only/manual trading remains mandatory. No orders, production changes, automatic promotion, or same-sample promotion. Any prospective candidate needs a separately frozen future certification window.
