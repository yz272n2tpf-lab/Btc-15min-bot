# Prospective sampling amendment — 2026-09-23

The original 20:30 UTC cohort manifest remains immutable (SHA256 d5c59e6a031f7b0e1212d583f70cfe4f149f2af7368bbdbbd4b3ed331694cf82). Five-second observation cadence aliased the main producer's five-second cycle: sampled states could all be stale while independent parity logs showed fresh frames. It cannot certify continuous availability or complete call coverage. Preserve every original scheduled slot, observation and missing interval as development evidence. Do not pool it with the replacement.

PR27 deployed collector e98576f23e247349b90717aea3a3ad832d409354 successfully at 20:53:18 UTC, deployment df8385ff-46a2-4dfb-af0a-07c25e5382aa. Startup passed 23 tests in 1.052s. The new run clean-source-v2-1s-20260923 samples the same four cached HTTP endpoints once per second and records observer epoch, real request/receipt times and failures. No additional authenticated upstream BRTI requests are introduced. Detector/source gates, models and main c482468 remain unchanged.

The original collector's last downloaded main observation began 20:53:12.117636 UTC. Its complete retained journal is 5,695,101 bytes with no CRC damage; the final CSV is 570,729 bytes, SHA256 1753367edbe40904772f6f12c679f62388173a17241ebc260c633380aceeae02. Its 456,431-byte pre-cutover CSV remains an exact prefix. Both run IDs have explicit read-only export routes from the same persistent /data volume. Historical Sep20–22 evidence retains its separate 9c82646867c34b4534e6cf72b498bb760e08d531cf10187757a130e7a6911a3a identity.

Replacement cohort btc15-common-20260923T211500Z begins prospectively at 21:15 UTC. It reserves 96 development slots, 96 validation slots and 1,344 untouched-holdout slots in separate windows, subject to runtime/revision identity and qualification. These reservations do not certify the current model. Known historical candle availability, wall-clock cold-start and publication limitations remain blockers. Any strategy revision requires a separate prospective policy identity; no outcome-based extension, reassignment or merging is allowed.

V8.1 exit hypotheses retain their numeric rules and are registered separately against the replacement cohort. They remain offline research, with no connected production exit advice. One-second samples still do not prove continuous availability, complete executable paths or browser delivery.

BRTI recorded its first upstream error around 20:53 UTC after 13,229 successful requests. It recovered to PRIMARY_OK; 429 count remained zero. Do not describe the interval as error-free or continuously available based only on heartbeats.

SIGNAL ONLY. NO ORDERS.
