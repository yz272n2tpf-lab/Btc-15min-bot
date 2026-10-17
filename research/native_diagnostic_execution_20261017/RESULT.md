# Native diagnostic execution: FAIL / NO-GO for 20-minute preflight

Executed once on 2026-10-17 under the explicit authorization for
`c60556e143c57ef58433b6fa564b643a4b5615ab`. The approved producer installations,
single diagnostic, one finisher/reader invocation and exact-source rollback
were performed. No diagnostic retry, 20-minute preflight or 10-hour evaluation
was run. No strategy, entry-price, timing, freshness threshold or signal-policy
change, orders, resize, new service or new volume was performed.

Result branch: `research/native-diagnostic-result-20261017`.
New repository content is execution receipts and the bounded operator commands
used to perform the authorized provisioning, finishing and rollback checks.
No reader, validator or producer package code was edited.

## Actual result

| Measurement | MAIN | V81 | Information |
| --- | ---: | ---: | ---: |
| Terminal elapsed seconds, including drain/seal | 33.953510 | 28.489482 | 60.211068 |
| Stop reason | HOOK_OVER_5MS:QUOTE_ACCEPT | HOOK_OVER_5MS:QUOTE_RECEIVE | DURATION_LIMIT |
| Seal status | INCOMPLETE | INCOMPLETE | SEALED |
| Archive records | 4,346 | 45,832 | 234 |
| Compressed bytes | 2,475,953 | 8,105,094 | 309,739 |
| Admitted / durable observations | 3,000 / 3,000 | 30,644 / 30,644 | 146 / 146 |
| Peak queued charge bytes / 33,554,432 budget | 1,880,889 | 778,256 | 521,189 |
| Queue items / queued bytes / unfinished observations at terminal | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Recorded writer losses / oversizes | 0 / 0 | 0 / 0 | 0 / 0 |
| Drain timed out | false | false | false |
| Reported not-yet-durable charge bytes | 1,982,092 | 21,880,904 | 0 |
| Maximum recorded hook wall time (ms) | 72.054830 | 21.521287 | No hook samples |
| Maximum writer fsync (ms) | 149.929609 | 325.824835 | 48.211612 |

These are terminal elapsed values, not independently measured admission-open
durations. MAIN and V81 stopped early under the unchanged >5-ms guard. The
maximum hook figures cover all measured labels, rather than claiming each is
the exact failing callback's duration. Information's 0.211-second overshoot
reflects the existing half-second watchdog/drain semantics; it was not extended
or restarted. The underlying native owners were not killed to stop capture.

All three roles closed admission and reached a seal. The mechanical drain
completed without timeout and admitted/durable item counts agree. However,
MAIN/V81 admitted-charge and durable-charge counters disagree despite empty
queues and zero unfinished observations. These are **charge-accounting
deficits**, not a proven count of missing raw payload bytes. Loss-free completion
is not established. Native proof queues reported zero drops/rejections and zero
unfinished work. Seven `INFORMATION_FAILURE` records independently report
`INPUT_NOT_PUBLISHED`; a SEALED information stream is not a qualified campaign.

## Existing reader qualification

The existing finisher ran **once**, attempt 1, transferred and SHA-256 verified
**9 objects / 10,902,671 bytes**. Transfer took **7.088704 seconds** and total
finisher time **15.661395 seconds**. Process exit was 0, but its explicit result
is **INCOMPLETE**, not PASS. The reader used a **31,186,944-byte DB**, within the
1-GiB ceiling and 240-second budget. No replacement reader or capacity test ran.

| Requested qualification | Actual evidence |
| --- | --- |
| MAIN completed-candle associations | FAIL: `RECORD_VERIFICATION`, `COMPLETED_CANDLE_BEFORE_ACCEPTANCE`, session `6e5064b7967a49cc95acfe1964bd4ae1`, sequence **308**, partition 2, kind `CANDLE_ACCEPTANCE`. |
| MAIN native associations | Four native/admin records admitted, including one original native commit. No qualified association ledger entries; `MAIN_APPLICABLE_DECISION_LINKS_MISSING`. |
| V81 native associations | 27 input observations and 112 native/admin records admitted (28 original native commits, 84 admin commits). **0 qualified causal matches**; `V81_APPLICABLE_DECISION_LINKS_MISSING`. |
| Information | Seven `INPUT_NOT_PUBLISHED` failures, sequences 141, 158, 185, 189, 209, 215, 227 in session `fa9847b012c249da8107f9e0767c84f2`. `INFORMATION_LINKS_MISSING`. |
| Source freshness and timing alignment | NOT QUALIFIED. Freshness/alignment checks were not relaxed; incomplete/quarantined scope does not certify them. Native logs reporting a qualified source are not substituted for reader proof. |
| Campaign scope | `ROLE_RUN_OR_INCOMPLETE`; 50,099 records quarantined after failure. Raw evidence remains preserved; quarantine is not deletion or proof that those records were physically lost. |

The reader counted 7,199 original completed candles and 50,399 completed-cache
rows whose upstream receipt is unknown. Those counters do not establish valid
MAIN associations. Both association ledgers are empty. No BUY accuracy, entry
price quality, management, exits or authoritative settlements are claimed from
this failed diagnostic. The reader's `production_authorization=NOT_AUTHORIZED`
is its conservative report field; the actual installation/capture was expressly
authorized by the user. `live_transport_verified=false` in the reader summary
is distinct from the finisher's authentic `live_retrieval=true` receipt.

## Deployment and rollback proof

| Role | Diagnostic source | Diagnostic deployment | Restored source | Rollback deployment |
| --- | --- | --- | --- | --- |
| MAIN + information | e2294683d2ec268d921df0277f5a9cb518f2e67d | 9fb6061a-7ed3-4ed6-a18a-32c4b74edc9c | dd46b7bc2fcc49865c49dc59eb7ad7d7316f6d72 | 3d4b26ce-d11c-4b3c-ac8c-1ed5a403f3c9 |
| V81 | f7c32d04556335632c862515a9ee1b742ad88ad3 | 1b5183a4-fca3-411f-9846-0a6ab860d283 | c14b3f9b04caea13e62bcdd6fb0e5990049aa17b | c04d806f-d279-4a0b-8b3b-5f6316c985a6 |

All four producer deployments reached SUCCESS. Rollback SUCCESS was observed
at 12:46:44 UTC for MAIN and 12:46:59 UTC for V81. Afterwards both services had
one running replica, zero crashed replicas and no reported platform issues.
Read-only pinned SSH at approximately 12:48:15–16 UTC verified exact original
source hashes (36 MAIN / 17 V81), the new rollback deployment IDs, and
`BTC15_RECORDING_ENABLED=0` in both actual runtimes. All three seals and all nine
listed producer evidence objects still matched their original hashes.
The approved campaign config and evidence are retained on the producer volumes.

The exact six activation and six rollback service calls are recorded in
`EXECUTION_RECEIPTS.json` and `AFTER.json`. The four staged changes were read
back unchanged after every production mutation. Patch
`ead9997e-b5b7-4668-a612-e8417e197838` remains STAGED with four changes solely
for shadow service `84bbacb1-56a4-4370-aa1c-0f8ae8ae42c1`. No environment-wide
staged-patch commit occurred. All seven historical volume IDs, sizes and mounts
match the before-state. No historical file deletion/overwrite was requested;
normal native application journaling continued. This is not a whole-volume
byte-for-byte audit of every historical file.

Signal-only/no-orders runtime identities were observed for both candidate
sources, which retain the protected strategy and entry policy bytes. Rollback
restores the original pinned packages. Platform/native source health here is
not broader production acceptance or a claim of zero deployment interruption.

## Space and preserved evidence

Actual available bytes immediately before the exclusive config writes:
MAIN **9,129,291,776**, V81 **2,608,533,504**; both exceeded the approved
2,449,473,536-byte floor. After rollback: MAIN **9,112,469,504**, V81
**2,583,113,728**. No resize was required. Research is now stopped with zero
running replicas; its original deferred start command was restored without
starting another job. Account billing/credits remain unavailable; no actual
account spend or remaining monthly headroom is asserted.

Producer originals (three role subdirectories `main`, `information`, `v81`):
`/data/btc15_recordings/DIAG_20261017_e2294683_f7c32d04/`

Research evidence and existing reader output:
`/research-evidence/DIAG_20261017_e2294683_f7c32d04-reader/`

Operational/health/rollback receipts:
`/research-evidence/native-diagnostic-execution-DIAG_20261017_e2294683_f7c32d04/`

The reader directory preserves raw compressed objects, seals, config, terminal
receipts, reader DB/checkpoint state, ledgers, logs, PDF and recovery archive.
The research volume is `2dba2ef6-b84d-4abf-9d04-58a1e77082c5`.

| Evidence | SHA-256 |
| --- | --- |
| MAIN seal | 3fa068b200a9a6d156535a82f312739a91d47b834f84eb78afe0a823e4916c53 |
| V81 seal | 04241db43ec9efee1c9d2e4c466b1d60b493d69a640a412294af88cc417ded96 |
| Information seal | d0892237646c0edccf1899efe50c768304967166a5984f6253bc5d2b4ea1ff80 |
| Sealed source inventory | 24b6b898951aa48a775632b1d09e8d5d523b1e7c772f0c66c669c6e02ad92a6c |
| Existing finisher PDF | 4ea5cb2201c7bd7dfc852454d910c54ad3a4742c34bcf0ca09222f382b40a3bc |
| Existing finisher recovery.zip | 7fd332deeee7fd2c6a1d3ce4c2e0acf137bfc27f1e81982559f42344a21b9b18 |

The small receipts copied into this result branch were reconstructed from
bounded research logs and individually SHA-256 verified. Full raw evidence,
PDF and ZIP remain on the existing research volume, not fabricated or replaced.

## Operational deviation and research deployment identities

An initial research retained-build redeploy unexpectedly reused the previous
deployment's start-command snapshot despite the verified new service command.
It unintentionally repeated the old read-only operational/lease probe. This was
an execution error, disclosed during the operation; it did not change production
or start capture. No diagnostic was repeated. The correction used a fresh
service-scoped source connection pinned to the same research source `950e4b5`.
Do not use retained-build redeploy to apply a newly changed start command.

- Unintended read-only replay: `8094fc56-72b3-4d0c-8bee-bb9c11aaaaea`;
  receipt `/research-evidence/native-operational-052adb70196541eabb55cae6585fa5d4.json`,
  SHA-256 `588e7e74e9b64708cc9bc08de48e955677797df32d542428bd7dad5eda5355e6`.
- Approved config provisioning: `558f3a22-b5bc-4899-935a-9d35a450d8c7`.
- Single finisher/reader: `6e0aa773-d0b7-42e4-9832-b143bc6e54e8`.
- Read-only rollback/evidence verification, no reader rerun:
  `857eb927-5090-42c9-973f-eba0c62998ac`.

## Exact remaining blockers

1. Native recorder hook wall time breaches the existing 5-ms limit in both
   producers. Diagnose the measured quote hook paths using this preserved run;
   do not relax timing, strategy cadence or freshness limits.
2. MAIN candle chronology still fails `COMPLETED_CANDLE_BEFORE_ACCEPTANCE` at
   sequence 308. Resolve against that authentic payload and original producer
   timestamp semantics before another native attempt.
3. MAIN/V81 charge accounting remains nonzero after all admitted observations
   are marked durable. Reconcile charge definitions and ledger consistency;
   do not call the discrepancy proven payload loss or silently discard it.
4. Seven information inputs were not published. Establish their authentic
   upstream cause and full association coverage; do not fabricate missing input.

These failures prevent reader qualification and a trustworthy source-freshness/
association claim. No correction was deployed and no second diagnostic was
started. The next work is limited to these demonstrated failures; a subsequent
native diagnostic requires authorization. **20-minute preflight: NO-GO.**
