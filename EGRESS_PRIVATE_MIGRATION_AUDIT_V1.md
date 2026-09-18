# BTC15 Private-Network Egress Migration Audit V1

Read-only/signal-only research infrastructure migration record. No strategy thresholds, provider polling, cutoffs, order logic, or production trading behavior are changed by this audit record.

## Completed no-boundary consumers

1. `scalp-reversal-reentry-holdout-v1`
   - Service ID: `a0f417fe-9bfe-4d80-bcd0-5647a582a1e7`
   - Private URL applied: `http://scalp-move-shadow-v1.railway.internal:8080/research/path-export`
   - Post-migration deployment: `9933e54a-dad2-4c39-ae07-657d73eef847`
   - Post-migration status: SUCCESS
   - First post-migration fetch: 492,437 rows
   - Runtime executable files verified byte-identical to prior deployment despite branch-head commit metadata drift.
   - NO ORDERS / shadow-only.

2. `scalp-entry-profit-holdout-v1`
   - Service ID: `4a7f7942-7701-4441-8061-d1c6148d0e81`
   - Private URL applied: `http://scalp-move-shadow-v1.railway.internal:8080/research/path-export`
   - Post-migration deployment: `82056b10-b4be-4016-83d5-4388017fd9ab`
   - Post-migration status: SUCCESS
   - First post-migration fetch: 495,456 rows
   - Source SHA256: `67d9eff7306177c60420aa9e64e54ec7b639eb076b6063522a4cab792c1a8281`
   - Analysis status: `FROZEN_ROLES_HOLDOUT_REVEALED`
   - Runtime files verified byte-identical to prior deployment.
   - NO ORDERS / shadow-only.

3. `scalp-specialist-review-v3`
   - Service ID: `fbf35c65-2043-49e8-9715-3c9151ea941b`
   - Private URL applied: `http://scalp-move-shadow-v1.railway.internal:8080/research/path-export`
   - Post-migration deployment: `fd95b152-f923-40f8-8b4f-224779b5a78f`
   - Post-migration status: SUCCESS
   - Deployment Git SHA unchanged: `22b8371bd12a714544396f4d073fccc7e038353f`
   - First post-migration analysis: `GAP_RECOVERY_FEATURE_AUDIT_READY`
   - NO ORDERS / shadow-only.

## Protected consumer migration segment 1 — Coverage Rescue

Service: `scalp-coverage-rescue-forward-v1`
Service ID: `d357294c-05e7-4a2b-89bf-0aaa4509b8fb`

### Pre-change evidence boundary

- Pre-change deployment: `f4fc1620-3cd9-46c8-9101-6fede77d8d71`
- Git SHA: `22b8371bd12a714544396f4d073fccc7e038353f`
- Frozen cutoff: `2026-09-16T05:00:21+00:00`
- Last recorded pre-change analysis timestamp: `2026-09-18T04:01:17.967850260Z`
- Pre-change status: `COLLECTING_FUTURE_RESCUE_V1`
- Pre-change future full contracts: 156
- Pre-change incremental rescue contracts: 1
- Pre-change qualification pass: false
- Orders: false
- Automatic promotion: false
- Runtime branch head equals deployed Git SHA; no code drift before migration.

This timestamp is an explicit infrastructure/evidence segment boundary. Evidence before and after the URL migration must not be described as operationally uninterrupted. The original frozen cutoff remains unchanged; the boundary is for infrastructure provenance, not strategy re-freezing.

### Post-change verification

- Private URL applied: `http://scalp-move-shadow-v1.railway.internal:8080/research/path-export`
- Post-change deployment: `5c5b28fb-e1bc-4018-86bd-5ea84049d653`
- Deployment Git SHA: `22b8371bd12a714544396f4d073fccc7e038353f` — unchanged.
- Railway deployment status: SUCCESS.
- Healthcheck: PASS.
- First post-change analysis timestamp: `2026-09-18T04:08:11.068469700Z`
- Frozen cutoff remained exactly `2026-09-16T05:00:21+00:00`.
- Post-change status remained `COLLECTING_FUTURE_RESCUE_V1`.
- Post-change future full contracts: 156.
- Post-change incremental rescue contracts: 1.
- Post-change qualification pass: false.
- Baseline, rescue, union, and mechanical-reconciliation aggregate values matched the last pre-change state at the segment boundary.
- The scorer rebuilds its state from the full source export on every refresh; no in-memory timer/evidence state is authoritative across restart.
- NO ORDERS / shadow-only / no automatic promotion.

Result: PRIVATE NETWORK MIGRATION SEGMENT PASS for Coverage Rescue. The infrastructure boundary remains recorded for provenance and later certification accounting.

## Protected consumer migration segment 2 — Economics Forward

Service: `scalp-economics-forward-v1`
Service ID: `a09d4dbc-8fa7-4d9f-bbc3-215533c4cf2b`

### Pre-change evidence boundary

- Pre-change deployment: `0cf8e2e8-ef60-4b09-86cf-93b2aff44f6e`
- Deployed Git SHA: `f5bc64eeb3608ee7822040f13e568148dd13cc97`
- Current branch head: `ebae93d1260c9ec8a91de8a746a14b498972a1e1`
- All four watched runtime/freeze files are byte-identical between deployed SHA and current branch head.
- Frozen cutoff: `2026-09-16T10:31:55+00:00`
- Last recorded pre-change analysis timestamp: `2026-09-18T04:08:48.171575320Z`
- Pre-change status: `READY_FOR_MANUAL_ECONOMICS_REVIEW`
- Pre-change future full contracts: 139
- OVERALL sample_ready: true
- OVERALL manual-review break-even evidence pass: true
- Orders: false
- Automatic promotion: false

This timestamp is the explicit infrastructure/evidence segment boundary for the Economics Forward scorer. The frozen strategy cutoff is not changed.

### Post-change verification

- Private URL applied: `http://scalp-move-shadow-v1.railway.internal:8080/research/path-export`
- Post-change deployment: `c0332514-8c3c-41c5-8ca4-78076cc7e4f7`
- Deployment Git SHA: `ebae93d1260c9ec8a91de8a746a14b498972a1e1` — unchanged.
- Railway deployment status: SUCCESS.
- Healthcheck: PASS.
- First post-change analysis timestamp: `2026-09-18T04:16:42.415966826Z`
- Frozen cutoff remained exactly `2026-09-16T11:10:33+00:00`.
- Future full contracts advanced from 138 to 139 from new source data.
- Immediate serial signals advanced from 237 to 239.
- Development-comparison sample_ready remained true.
- No same-sample promotion; selected policy would still require a later fresh certification window.
- NO ORDERS / no automatic promotion.

Result: PRIVATE NETWORK MIGRATION SEGMENT PASS for Candidate→Verify Forward.

## Protected consumer migration segment 3 — Candidate→Verify Forward

Service: `scalp-economics-exit-review-v1`
Service ID: `f6ae8e92-dbd9-4439-817e-abda52981ab1`

### Pre-change evidence boundary

- Pre-change deployment: `19c72496-8ea1-4a4b-8e09-564e1074dbef`
- Git SHA: `ebae93d1260c9ec8a91de8a746a14b498972a1e1`
- Frozen cutoff: `2026-09-16T11:10:33+00:00`
- Last recorded pre-change analysis timestamp: `2026-09-18T04:10:27.372156784Z`
- Pre-change future full contracts: 138
- Pre-change immediate serial signals: 237
- Development-comparison sample_ready: true
- Orders: false
- Automatic promotion: false
- Runtime branch head equals deployed Git SHA.

This timestamp is the explicit infrastructure/evidence segment boundary. The frozen cutoff and comparison policy are not changed.

### Post-change verification

- Private URL applied: `http://scalp-move-shadow-v1.railway.internal:8080/research/path-export`
- Post-change deployment: `385f960a-edfe-41c9-a5b9-c22c79b5b137`
- Deployment Git SHA: `bccb066d6f8853d34a503da7bd8b01586c5b190e` — unchanged.
- Railway deployment status: SUCCESS.
- Healthcheck: PASS.
- First post-change analysis timestamp: `2026-09-18T04:20:02.876025647Z`
- Frozen cutoff remained exactly `2026-09-16T11:03:16+00:00`.
- Status remained `READY_FOR_MANUAL_DESCRIPTIVE_REVIEW`.
- Pre/post descriptive aggregates remained continuous, with the same 139-contract universe at the boundary.
- Descriptive-only interpretation and no-threshold-selection guardrail remained intact.
- NO ORDERS / no automatic promotion.

Result: PRIVATE NETWORK MIGRATION SEGMENT PASS for Regime Observation V1.1.

## Protected consumer migration segment 4 — Regime Observation V1.1

Service: `scalp-regime-review-v1`
Service ID: `979ad780-249d-407a-ae73-c8488c1d047f`

### Pre-change evidence boundary

- Pre-change deployment: `0e00dbd2-efa3-4954-9cd7-e199861b9c72`
- Git SHA: `bccb066d6f8853d34a503da7bd8b01586c5b190e`
- Frozen cutoff: `2026-09-16T11:03:16+00:00`
- Last recorded pre-change analysis timestamp: `2026-09-18T04:15:42.521439877Z`
- Pre-change status: `READY_FOR_MANUAL_DESCRIPTIVE_REVIEW`
- Pre-change future full contracts: 139
- Descriptive sample_ready: true
- Orders: false
- Automatic promotion: false
- Runtime branch head equals deployed Git SHA.

This timestamp is the explicit infrastructure/evidence segment boundary. The frozen cutoff and descriptive-only interpretation are not changed.

### Post-change verification

- Private URL applied: `http://scalp-move-shadow-v1.railway.internal:8080/research/path-export`
- Post-change deployment: `7877b573-6e9e-4440-a560-700d912001f5`
- Deployment Git SHA: `14ef7cf264eb2e53246082038bd90eef9dde63da` — unchanged.
- Railway deployment status: SUCCESS.
- Healthcheck: PASS.
- First post-change analysis timestamp: `2026-09-18T04:24:01.803336963Z`
- Frozen cutoff remained exactly `2026-09-16T11:48:06+00:00`.
- Status remained `READY_FOR_MANUAL_WATCH_EXIT_REVIEW`.
- Future full contracts remained 136.
- Armed signals remained 191.
- Development-comparison sample_ready remained true.
- Watch policy still does not change the exit; selected rule still requires a later fresh certification window.
- NO ORDERS / no automatic promotion.

Result: PRIVATE NETWORK MIGRATION SEGMENT PASS for Watch→Exit Forward.

## Protected consumer migration segment 5 — Watch→Exit Forward

Service: `scalp-entry-profit-review-v1`
Service ID: `b3080f5e-c625-4891-8aa2-eae860d6c174`

### Pre-change evidence boundary

- Pre-change deployment: `71f6718d-1901-4196-b629-2e514ea5a327`
- Git SHA: `14ef7cf264eb2e53246082038bd90eef9dde63da`
- Frozen cutoff: `2026-09-16T11:48:06+00:00`
- Last recorded pre-change analysis timestamp: `2026-09-18T04:19:00.120649803Z`
- Pre-change status: `READY_FOR_MANUAL_WATCH_EXIT_REVIEW`
- Pre-change future full contracts: 136
- Pre-change armed signals: 191
- Development-comparison sample_ready: true
- Orders: false
- Automatic promotion: false
- Runtime branch head equals deployed Git SHA.

This timestamp is the explicit infrastructure/evidence segment boundary. The frozen Watch→Exit rules and cutoff are not changed.

### Post-change verification

- Private URL applied: `http://scalp-move-shadow-v1.railway.internal:8080/research/path-export`
- Post-change deployment: `057504f6-cb85-41ea-8a9c-9a4d0c577b6b`
- Deployment Git SHA: `b124c54ea9d015d88c5237d5e0bc45ded8a37f36` — unchanged.
- Railway deployment status: SUCCESS.
- Healthcheck: PASS.
- First post-change analysis timestamp: `2026-09-18T04:27:25.271428495Z`
- Frozen cutoff remained exactly `2026-09-16T11:56:59+00:00`.
- Status remained `READY_FOR_MANUAL_DENSITY_REVIEW`.
- Future full contracts remained 136.
- Sample_ready remained true.
- Density remains descriptive only and does not select/suppress signals.
- NO ORDERS / no automatic promotion.

Result: PRIVATE NETWORK MIGRATION SEGMENT PASS for Opportunity Density Forward.

## Protected consumer migration segment 6 — Opportunity Density Forward

Service: `scalp-reversal-reentry-review-v1`
Service ID: `c45a77d2-c91c-4c7c-b1f9-de52d7348ff9`

### Pre-change evidence boundary

- Pre-change deployment: `265e87a4-754f-4d6e-a116-12ac67b80c95`
- Git SHA / current branch head: `b124c54ea9d015d88c5237d5e0bc45ded8a37f36`
- Frozen cutoff: `2026-09-16T11:56:59+00:00`
- Last recorded pre-change analysis timestamp: `2026-09-18T04:22:08.281827375Z`
- Pre-change status: `READY_FOR_MANUAL_DENSITY_REVIEW`
- Pre-change future full contracts: 136
- Sample_ready: true
- Orders: false
- Automatic promotion: false

This timestamp is the explicit infrastructure/evidence segment boundary. Density remains descriptive and does not select or suppress signals.

### Post-change verification

- Private URL applied: `http://scalp-move-shadow-v1.railway.internal:8080/research/path-export`
- Post-change deployment: `cbca0472-9f3c-48c9-924a-3c0e58cf0eb9`
- Deployment Git SHA: `b786be9bf13c8c4ad80d9073f2e498904a609f23` — unchanged.
- Railway deployment status: SUCCESS.
- Healthcheck: PASS.
- First post-change analysis timestamp: `2026-09-18T04:32:16.052824525Z`
- Frozen cutoff remained exactly `2026-09-16T12:05:59+00:00`.
- Status remained `READY_FOR_MANUAL_PULLBACK_DEVELOPMENT_REVIEW`.
- Future full contracts advanced from 135 to 136 from new source data.
- Immediate signals advanced from 228 to 229.
- Development-comparison sample_ready remained true.
- Selected pullback rule still requires a new fresh certification window.
- NO ORDERS / no automatic promotion.

Result: PRIVATE NETWORK MIGRATION SEGMENT PASS for Pullback Entry Forward.

## Protected consumer migration segment 7 — Pullback Entry Forward

Service: `scalp-ladder-research-v1`
Service ID: `7ef27913-4f4d-40fc-9b32-91d79852f13d`

### Pre-change evidence boundary

- Pre-change deployment: `74ff8af6-74c4-45be-8325-a40b9918663f`
- Git SHA / current branch head: `b786be9bf13c8c4ad80d9073f2e498904a609f23`
- Frozen cutoff: `2026-09-16T12:05:59+00:00`
- Last recorded pre-change analysis timestamp: `2026-09-18T04:28:35.923515421Z`
- Pre-change status: `READY_FOR_MANUAL_PULLBACK_DEVELOPMENT_REVIEW`
- Pre-change future full contracts: 135
- Pre-change immediate signals: 228
- Development-comparison sample_ready: true
- Orders: false
- Automatic promotion: false
- Runtime branch head equals deployed Git SHA.

This timestamp is the explicit infrastructure/evidence segment boundary. Pullback remains development comparison only and any selected rule still requires a new fresh certification window.

### Post-change verification

The explicit `set_variables` call to the private target produced no new deployment, while the service continued healthy on deployment `c0332514-8c3c-41c5-8ca4-78076cc7e4f7`. This indicates the configured value already matched the private target before this verification attempt.

- Confirmed target: `http://scalp-move-shadow-v1.railway.internal:8080/research/path-export`
- Active deployment remained: `c0332514-8c3c-41c5-8ca4-78076cc7e4f7`
- Git SHA remained: `ebae93d1260c9ec8a91de8a746a14b498972a1e1`
- Frozen cutoff remained `2026-09-16T11:10:33+00:00`.
- Service continued producing healthy analysis after the verification attempt.
- No new restart/deployment occurred from this no-op variable set.
- NO ORDERS / shadow-only / no automatic promotion.

Audit correction: the 12:25:49 timestamp above is a verification boundary, not the original public-to-private switch boundary. The exact earlier switch time is not asserted from redacted variable history. Current private-path state is verified operationally.

## Protected consumer migration segment 3 — Candidate Verify

Service: `scalp-economics-exit-review-v1`
Service ID: `f6ae8e92-dbd9-4439-817e-abda52981ab1`

### Pre-change evidence boundary

- Pre-change deployment: `c0332514-8c3c-41c5-8ca4-78076cc7e4f7`
- Git SHA: `ebae93d1260c9ec8a91de8a746a14b498972a1e1`
- Frozen cutoff: `2026-09-16T11:10:33+00:00`
- Last recorded pre-change analysis timestamp: `2026-09-18T12:25:49.454450288Z`
- Pre-change status: `READY_FOR_MANUAL_DEVELOPMENT_COMPARISON`
- Pre-change future full contracts: 171
- Pre-change immediate serial signals: 296
- Pre-change observed 30s verified signals: 296
- Pre-change sample_ready: true
- Policy selection: false
- Same-sample promotion: false
- Automatic promotion: false
- Orders: false
- Runtime branch head equals deployed Git SHA.

This timestamp is the explicit infrastructure/evidence segment boundary for Candidate Verify. The frozen strategy cutoff remains unchanged.

### Post-change verification

The explicit variable set to the private target created no new deployment, so the configured value already matched the private target before this verification attempt.

- Confirmed target: `http://scalp-move-shadow-v1.railway.internal:8080/research/path-export`
- Active deployment remained `385f960a-edfe-41c9-a5b9-c22c79b5b137`.
- Git SHA remained `bccb066d6f8853d34a503da7bd8b01586c5b190e`.
- Frozen cutoff remained `2026-09-16T11:03:16+00:00`.
- Service continued healthy with no restart from the no-op set.
- NO ORDERS / shadow-only / no automatic promotion.

Audit correction: this is a verification boundary, not the original public-to-private switch boundary. Current private-path state is verified operationally.

## Protected consumer migration segment 4 — Regime Observation

Service: `scalp-regime-review-v1`
Service ID: `979ad780-249d-407a-ae73-c8488c1d047f`

### Pre-change evidence boundary

- Active deployment: `385f960a-edfe-41c9-a5b9-c22c79b5b137`
- Git SHA: `bccb066d6f8853d34a503da7bd8b01586c5b190e`
- Current branch head equals deployed SHA.
- Frozen cutoff: `2026-09-16T11:03:16+00:00`
- Last recorded analysis timestamp before verification: `2026-09-18T12:30:33.609640113Z`
- Status: `READY_FOR_MANUAL_DESCRIPTIVE_REVIEW`
- Future full contracts: 172
- sample_ready: true
- Automatic promotion: false
- Orders: false

This timestamp is the infrastructure/evidence verification boundary for Regime Observation. The strategy cutoff remains unchanged.

### Post-change

PENDING.

## Protected consumer migration segment 5 — Watch Exit

Service: `scalp-entry-profit-review-v1`
Service ID: `b3080f5e-c625-4891-8aa2-eae860d6c174`

### Pre-change evidence boundary

- Active deployment: `7877b573-6e9e-4440-a560-700d912001f5`
- Git SHA: `14ef7cf264eb2e53246082038bd90eef9dde63da`
- Current branch head equals deployed SHA.
- Frozen cutoff: `2026-09-16T11:48:06+00:00`
- Last recorded analysis timestamp before verification: `2026-09-18T12:31:07.088490516Z`
- Future full contracts: 169
- Armed signals: 238
- sample_ready: true
- Watch does not change exit: true
- Watch policy selection: false
- Automatic promotion: false
- Orders: false

This timestamp is the infrastructure/evidence verification boundary for Watch Exit. The frozen strategy cutoff remains unchanged.

### Post-change verification

Setting the private target caused no new deployment, indicating the configured URL already matched the private target before this verification attempt.

- Active deployment remained `7877b573-6e9e-4440-a560-700d912001f5`.
- Git SHA remained `14ef7cf264eb2e53246082038bd90eef9dde63da`.
- Frozen cutoff remained unchanged.
- No restart occurred from the no-op set.
- NO ORDERS / no policy selection / no automatic promotion.

Current private-path state is verified operationally.

## Protected consumer migration segment 6 — Opportunity Density

Service: `scalp-reversal-reentry-review-v1`
Service ID: `c45a77d2-c91c-4c7c-b1f9-de52d7348ff9`

### Pre-change evidence boundary

- Active deployment: `057504f6-cb85-41ea-8a9c-9a4d0c577b6b`
- Git SHA: `b124c54ea9d015d88c5237d5e0bc45ded8a37f36`
- Current branch head equals deployed SHA.
- Frozen cutoff: `2026-09-16T11:56:59+00:00`
- Last recorded analysis timestamp before verification: `2026-09-18T12:31:37.217815185Z`
- Status: `READY_FOR_MANUAL_DENSITY_REVIEW`
- Future full contracts: 169
- Total serial opportunities: 289
- True contract coverage: 0.9763313609467456
- sample_ready: true
- Orders: false

This timestamp is the infrastructure/evidence verification boundary for Opportunity Density. The frozen strategy cutoff remains unchanged.

### Post-change

PENDING.

## Protected consumer migration segment 7 — Pullback Entry

Service: `scalp-ladder-research-v1`
Service ID: `7ef27913-4f4d-40fc-9b32-91d79852f13d`

### Pre-change evidence boundary

- Active deployment: `cbca0472-9f3c-48c9-924a-3c0e58cf0eb9`
- Git SHA: `b786be9bf13c8c4ad80d9073f2e498904a609f23`
- Current branch head equals deployed SHA.
- Frozen cutoff: `2026-09-16T12:05:59+00:00`
- Last recorded analysis timestamp before verification: `2026-09-18T12:32:19.486613570Z`
- Status: `READY_FOR_MANUAL_PULLBACK_DEVELOPMENT_REVIEW`
- Future full contracts: 168
- Signals: 286
- sample_ready: true
- Orders: false

This timestamp is the infrastructure/evidence verification boundary for Pullback Entry. The frozen strategy cutoff remains unchanged.

### Post-change verification

Setting the private target caused no new deployment, indicating the configured URL already matched the private target before this verification attempt.

- Active deployment remained `cbca0472-9f3c-48c9-924a-3c0e58cf0eb9`.
- Git SHA remained `b786be9bf13c8c4ad80d9073f2e498904a609f23`.
- Frozen cutoff remained unchanged.
- No restart occurred from the no-op set.
- NO ORDERS / shadow-only.

Current private-path state is verified operationally.

## Protected consumer migration segment 8 — Nextgen V2

Service: `scalp-nextgen-shadow-v2`
Service ID: `46b79a18-0fc2-46f0-8f12-d6bac63eecad`

### Pre-change evidence boundary

- Active deployment: `17cac03e-20a2-46be-b535-c31f63aaf6fa`
- Git SHA: `f23b4b37c0bb5f2ba5a50915933962b9eb7813a1`
- Current branch head equals deployed SHA.
- Frozen cutoff: `2026-09-16T22:30:00+00:00`
- Window ID: `00e73c80479a5ec5d482d33429e5f2115513dcddd93babdf38a7e38c6b7cac67`
- Expected code fingerprint: `7f901c87774dd418db79a29f513b05245488a6ba0cedd6e7a8572ac9865ce55f`
- Last recorded analysis timestamp before migration: `2026-09-18T12:34:04.534060529Z`
- Status: `READY_FOR_MANUAL_V2_COMPARISON`
- Future full contracts: 135
- Serial signals: 221
- Source SHA256: `c1448ecc9eccb2858e8bf6a17811c8bfde870508e8cd75e1bb7ad2f851230dbd`
- Runtime integrity all checks pass: true
- Safety remains shadow-only/manual-execution/orders=false/no automatic promotion.

The Nextgen process recomputes state and audit_records from the full source export on refresh; the restart does not rely on an authoritative in-memory timer state. This timestamp is the explicit infrastructure/evidence segment boundary. The frozen cutoff, code fingerprint, and window ID must remain unchanged.

### Post-change

PENDING.