# BTC15 information ingress rollout — 2026-09-28

## Qualified and deployed identity

- Local approved candidate: `c9c563ff56046467f0b5f0c60aa503c929f634de`.
- Published branch: `audit/information-ingress-fix-20260928`.
- Published candidate: `5b93ad956b146c2a8767b8f0e3b546035b4733d4`.
- PR: https://github.com/yz272n2tpf-lab/Btc-15min-bot/pull/51
- Hosted tested merge: `503dae9cfa7f6fbcb61551fdafd21936d05a944f`.
- Production merge: `abe212b513827c8cec28a2f64e0161e79296bd82`.
- All four commits have identical tree `8021dc82d5ba43b4e34845d90150b48f6f2bd95b`; verified with git tree identities and empty diffs. The authenticated connector assigned different commit metadata when publishing; it did not change any file.
- Railway production deployment: `94b2fe67-70af-4d44-b751-735e4aa732c0`, SUCCESS, updated 19:57:17.337Z.
- Existing preview unchanged: `9626115d3e017c235c55eaaae97b09e057992eb2`, deployment `4d3f54c5-0508-4912-874c-db017dec72c1`, SUCCESS.

## Root cause and correction

The native completed-candle cache is initialized at startup while qualified rolling ticks continue to support native FAIR. In later contracts, the export's current-contract candle slice becomes empty. The old `COMPLETED_BOUND` minimum incorrectly rejected that representation and cleared the export anchor. Allowing a truthful empty candle slice restores ingress; the unchanged native feature builder still requires sufficient causal rolling support. No substitute data, freshness extension, owner bypass or identity-source change was introduced.

Runtime changes are confined to `btc15_information_v1.py` (completed slice lower bound) and `btc15_information_service_v1.py` (failure-boundary diagnostics). Added regression files are `test_btc15_information_ingress_recovery.py` and `test_btc15_information_ingress_preview.js`, plus the original recovery audit. Model, strategy, ladder, native timing, Kalshi/BRTI owners and contracts, recovered preview, cohort code and production configuration are unchanged.

## Qualification

Local pinned qualification: 392/392 tests and 3/3 packaged authority gates PASS.

Hosted Actions run `36475307989`, job `109107415653`: 392 tests in 84.039 seconds, OK; all three packaged authority gates PASS. This ran the exact candidate tree before the expected-head-guarded production merge. Coverage includes the reproduced original failure through the actual native exporter and frozen feature builder, later contracts, loopback ingress, matching identity, all phases, missing/gapped/stale/future data, ownership/rollover changes, lock contention, evaluation/journal failures and exact recovered-preview script lifecycle/nonce/expiry redaction.

## Live evidence

Read-only observation started before rollout. Brief deployment unavailability was observed around 19:56:52Z; startup returned WAIT before first observed AVAILABLE at 19:58:09Z. This interval is retained in the observation record.

- Production first AVAILABLE: ticker `KXBTC15M-26SEP281600-00`, 3M_GUARD, BRTI age 3.2302 seconds, Flip Risk 10.0898%; nonce-bound identity returned 200 with matching ticker, anchor and native epoch.
- Existing preview browser at 19:58:32Z: 3M GUARD, Flip Risk 9.9%, qualified BRTI fresh 2.4 seconds.
- Next contract after 20:00Z: `KXBTC15M-26SEP281615-15`, production and preview AVAILABLE in NORMAL. Browser showed NORMAL WINDOW, Flip Risk 40.9%, qualified BRTI fresh 4.0 seconds.
- At approximately 20:10Z, both endpoints returned AVAILABLE in 5M_CAUTION. Browser showed 5M CAUTION, Flip Risk 9.4%, qualified BRTI fresh 3.9 seconds.
- Live unqualified intervals cleared browser values to Flip Risk em dash, DATA NOT FRESH and qualified BRTI unavailable. WAIT responses redacted source fields; identity failed closed with 503. Independent requests can straddle a qualification expiry, correctly producing AVAILABLE followed by identity 503; the browser must reject such a pair.

Final observation through 2026-09-28T20:16:38.562227+00:00: 1100 endpoint attempts, 212 AVAILABLE information responses, 142 redacted WAIT responses, 213 identity 200 responses, and 209 same-batch exact ticker/anchor/native-epoch identity matches. No detected nonce, schema, freshness, lease, source-redaction or signal-only/no-orders violations. Transport timeouts and independent expiry-straddling requests remain in the raw record and are not counted as matched successes.

After the 20:15Z rollover, both production and preview returned AVAILABLE for `KXBTC15M-26SEP281630-30` in NORMAL with matching identity. At 20:16Z the preview browser displayed NORMAL WINDOW, Flip Risk 31.5%, qualified BRTI fresh 2.5 seconds. Production example: checked_ts 1790626572.6109028, BRTI age 1.6109027863 seconds, Flip Risk 31.505492532%, anchor `d0ab2c89213bf6e010aa7cdbb8ff002c6ec68bfd1e281bd034e1fa0730f3fac0`, native epoch `24022ccc-5df6-433f-86eb-a978eb251e64`. All three phases were observed on both API paths and in the existing browser preview; qualification persisted into a later contract beyond the startup candle slice.

Availability was intermittent, including a WAIT interval before and through rollover; the fix does not promise continuous qualification. No safety gates were loosened to hide these intervals. This is a cloud-browser functional observation, not a physical iPad/iPhone test.

## Cohort preservation

Same production volume `6ced6b1a-3755-4518-a240-c895e936d443`, mount `/data`; no configuration or writer changes. Startup inventory at 19:57:04.847085415Z retained `/data/btc15_cohort_native_v1.jsonl` at 42 MB (earlier startup inventory was 40 MB). Startup at 19:57:08.050930502Z reported PRESERVED_EXISTING for the existing evidence archive and NO ORDERS. This proves the prior archive was retained, not that it freshly copied the entire current cohort.

Immutable FAIR weights `95fc4e893c9032f29b9732d03c4a2e0cd62755ba93b36106a1d0c8c094520ba6` and artifact `1bf10e755fc81584bab3c3682b16103353f84582c27bb003664de883e7e7c816` were logged with NO STARTUP FIT. At 20:00:02.762098275Z, native BRTI finalized the prior contract with 60/60 readings and complete=True.

No cohort reset, rewrite, filtering, scoring or tuning was performed. The rollout gap is retained as operational evidence. These checks establish retained storage and unchanged append semantics; they are not a forensic byte-for-byte audit of the inaccessible live cohort file.

## Remaining before Wednesday

Prospective cohort review, separately authorized ladder tuning, physical iPad/iPhone lifecycle/layout checks, final UI polish and go-live preparation. The legacy static caption below Flip Risk still says the probability feed is not connected even when the qualified numeric value is present; leave the exact qualified preview unchanged here and address wording during UI polish. Signal-only/no-orders remains in force.
