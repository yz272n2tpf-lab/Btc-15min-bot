# V1 -> V2 HANDOFF RECORD — 2026-09-18

## Common source
Both adapters read the same canonical private producer:
scalp-move-shadow-v1.railway.internal:8080/research/path-export
Both authenticate by Railway secret reference, are read-only, orders=false, public TX=0.

## Boundary observation
V1 latest captured: rows=573871 bytes=366902057 sha=37dfee81f235e1aa27e464213d2b5ec79999367432aa1a786281cec514474fd6.
V2 latest captured near same time: rows=573861 bytes=366895786 sha=da8d827b27bff286bd5f82d6eb5e6a4bd2a925c41c3007881d097d90fb48605f.
These are NOT claimed as same-SHA parity: source was growing and polls occurred at different instants. Row delta=10 is consistent with asynchronous polling.

## Functional equivalence already established for V2 transport
V2 streams canonical source, commits only complete newline-terminated snapshot, computes exact committed SHA/row count, exposes bounded deltas with per-chunk SHA/source-size/source-SHA, read-only.
V2 completed repeated monotonic refreshes with no public TX and no orders.

## Resource handoff
V1 ~0.79 GB avg RAM latest hour.
V2 steady after page-cache advisory fell to ~0.02-0.05 GB between refreshes; transient refresh spikes observed.
V2 is the intended shared layer, subject to consumer same-boundary parity.

## Retirement rule
V1 may be retired to free the canary slot because:
- it is temporary proof infrastructure, not protected research;
- no protected consumer has been migrated to depend on it;
- V2 reads the same canonical producer directly;
- V2 has passed repeated refresh/read-only/network/RAM gates.
Exact consumer evidence parity is still required in the Regime isolated canary before any protected consumer promotion.

Deleting V1 does not delete canonical scalp evidence; canonical producer remains untouched.
