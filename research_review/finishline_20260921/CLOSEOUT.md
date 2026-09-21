# BTC15 EARLY + SCALP finish-line research — 2026-09-21

**EARLY: NO STABLE CANDIDATE. SCALP: NO STABLE CANDIDATE.**

One hypothesis per lane was fixed before this pass's scoring. Both failed their development advancement screens. No alternate thresholds were tried afterward. These results do not disprove every possible approach; they reject the two exact ideas assessed here.

Production, protected EARLY, FINAL, BRTI, Kalshi plumbing, dashboards, services and volumes were not changed. Nothing was deleted. SIGNAL ONLY / NO ORDERS.

## Research identity

- Repository: `yz272n2tpf-lab/Btc-15min-bot`.
- Isolated branch: `research/early-scalp-finishline-20260921`.
- Pre-scoring specification commit: `2339b23c94d8299f951ad60af8844fc9f2c0823a`.
- Source code/checkpoint revision: `d31922b4c72d5bc7efa590eb1b3c4f86da71fc0d`.
- Newer diagnostic checkpoint: `38a14fc8085090f2965bf93cf831646a1b5aa6c2`.
- Research files: this closeout, `PREREGISTRATION.md`, `replay.py`, `test_replay.py`, `audit.py`, `report.json`, `source_manifest.json`, `fingerprints.json`, and `evidence_outputs.zip` in this directory.
- The closeout commit is the commit containing these files. It is supplied separately in the delivery receipt so the report does not claim a self-referential hash.

The protected EARLY rule was recovered from the research checkpoint and cross-checked against main at `7339b87624e35314b9d2b94e8a4feefef02715dd`: ASK <=45c, fair >=75%, edge >=8pp, 2–10 minutes remaining, absolute target gap >=$25, first qualifying row. It was not modified. Prior protected holdout statistics were not recomputed or represented as this pass's results.

## EARLY — BREAKOUT_RETEST_RECLAIM_V1

**Decision: reject as written.** Affordable, earlier observations did not deliver sufficiently reliable near-term follow-through or stable coverage.

This is a sequential price-structure hypothesis. For UP, BTC must break above the preceding 30-second high with BTC15 >=+$8, pull back while holding that breakout level, then exceed the impulse peak within 30 seconds. DOWN mirrors the geometry. It requires 6–11 minutes remaining, current ASK <=50c, and ASK no more than 2c above the episode-start ASK. It scores the first qualifying entry per contract. Missing history or gaps >10 seconds reset the sequence. The complete state rules, tie-break, data guards and thresholds are in `PREREGISTRATION.md` and `replay.py`.

Unlike the rejected one-minute fair-confidence classifier, prior fair/ask lead-lag rule, and cheap-side momentum conjunction, this uses the order of a breakout, held pullback, and renewed move. It does not select a settlement model or tighten target-gap eligibility. There was one sequence rule and no parameter search.

Development source: 156 September 3–5 contracts; 147 span the full 11-to-6-minute entry window. Nine incomplete-window contracts are explicitly excluded from the primary coverage denominator; none emitted a candidate call. All 51 selected paths have complete two-minute observations. No settlement match is required for an excursion to count.

| Metric | Result |
|---|---:|
| Calls / eligible contracts | 51 / 147 — **34.7% coverage** |
| Calls / all observed contracts | 51 / 156 — 32.7% |
| UP / DOWN | 26 / 25 |
| Mean / median actual ASK | **29.27c / 31c** |
| ASK range | 2.1c–47c |
| Ideal 25–35c entries | 11 / 51 — 21.6% |
| Entries <=35c / <=50c | 31 / 51; 51 / 51 |
| Mean / median minutes remaining | **8.70 / 8.92** |
| Mean breakout-to-entry delay | 16.46 seconds |
| +5c within 120 seconds | 39 / 51 — **76.5%** |
| +10c within 120 seconds | 31 / 51 — **60.8%** |
| +15c within 120 seconds | 29 / 51 — 56.9% |
| +20c within 120 seconds | 23 / 51 — 45.1% |
| Mean / median two-minute MFE | +19.34c / +18c |
| Mean / median two-minute MAE | -2.92c / -1c |
| Worst two-minute adverse excursion | -22c |
| Median time to +5 / +10 / +15 / +20, among hits | 15.0 / 25.0 / 40.0 / 55.0 seconds |

Predeclared development screens failed: coverage >=40%, +5c >=90%, +10c >=80%, and each chronological third's +10c >=70%. These were research advancement requirements declared in this pass, not a claim that the earlier protected excursion study had a numeric promotion gate. Other price, timing, sample-size and side-balance requirements passed.

Chronological thirds, all development:

| Block | Calls / contracts | Coverage | +10c within 120 seconds |
|---|---:|---:|---:|
| First | 21 / 49 | 42.9% | 11 / 21 — 52.4% |
| Middle | 24 / 49 | 49.0% | 16 / 24 — 66.7% |
| Last | 6 / 49 | **12.2%** | 4 / 6 — 66.7% |

The preregistered one-observation reaction check, averaging about five seconds, retained 42 entries (28.6% contract coverage); only 23/42, **54.8%**, reached +10c within two minutes. This is a fixed execution sensitivity, not a second candidate or proof of manual fills.

Full remaining-contract excursions were also measured: 50 complete paths, +5/+10/+15/+20 rates of **88% / 80% / 70% / 62%**. Mean MAE was **-17.63c**, median -19c, worst -46c. One remaining-contract path is incomplete. Allowing the whole remaining contract to hit a target does not erase interim adverse moves or repair the frozen two-minute/coverage failures.

The protected-reference tape covers 101 overlapping source contracts and produces 10 protected-reference calls. Six overlap the new candidate's called contracts; all six new calls occur earlier, with 165-second median lead, but only **three are the same side**. The timing comparison is therefore not six improved replacements. The candidate adds 23 called contracts within the shared source universe. Settlement is secondary only: 9 same-side out of 23 cached matches; 28 candidate calls lack cached official truth. None was discarded from excursion statistics because of missing settlement data.

## SCALP — TARGET_SUPPORTED_QUALITY_TIER_V1

**Decision: reject as an actionable quality filter.** The higher +10c rate comes with excessive loss of opportunities and existing winners, plus less attractive entry prices.

The existing move detector and serial opportunity schedule remain price-neutral. A new quality label checks only the original candidate-time signed distance: UP requires BTC > exact target; DOWN requires BTC < exact target. Gap zero or missing values do not earn the supported tier. The candidate's proposed actionable subset uses that tier plus the existing first actual ASK <=50c within 30 seconds. Other movements remain visible as WATCH. Cent buckets are reporting only.

This directly tests the later checkpoint's target-position observation on a separate preserved historical event cohort. It does not repeat BTC30 >=20, normalized-momentum, or BTC/BRTI parity tuning. The documented BTC30 >=15 and >=120-second source qualification is unchanged.

Recovered raw tape: **91 observed September 13–14 contracts**, 242 CANDIDATE, 40,877 PATH, 240 RESULT and 27,601 SNAPSHOT rows. **89 complete contracts** enter the paired comparison. The startup partial contract and unfinished final contract are excluded. This is not a reconstruction of the missing 352-contract/563-opportunity archive and no exact-hash reproduction of that archive is claimed.

The separately versioned replay implements the later serial lifecycle: **103 movement opportunities across 68 contracts**, up to four per contract. There are **57 EXIT, 11 ENDED_UNARMED, 34 armed/no-exit blocking states and one incomplete blocking state**. ENDED_UNARMED is metadata only. Missing data cannot authorize a reset. Candidate IDs join on (contract, candidate_id); no duplicate CANDIDATE/RESULT keys or orphan PATH/RESULT keys were found.

Value-entry protection is recomputed from the actual delayed ASK. Control and candidate share the same schedule and non-overlap check. Two control paths are incomplete and are retained in coverage, but not silently scored as completed winners/failures.

| Metric | Existing value control | Target-supported candidate |
|---|---:|---:|
| Value entries / complete paths | 53 / 51 | 25 / 25 |
| Entry contracts / eligible contracts | 42 / 89 | 22 / 89 |
| Contract coverage | **47.2%** | **24.7%** |
| Mean / median actual ASK | 33.25c / 36c | **42.32c / 44c** |
| Ideal 25–35c entries | 11 / 53 | 2 / 25 |
| Every entry <=50c | Yes | Yes |
| Mean minutes remaining | 8.99 | 9.14 |
| +5c on complete paths | 48 / 51 — 94.1% | 24 / 25 — 96.0% |
| +10c on complete paths | 41 / 51 — **80.4%** | 23 / 25 — **92.0%** |
| +15c on complete paths | 37 / 51 — 72.5% | 22 / 25 — 88.0% |
| +20c on complete paths | 29 / 51 — 56.9% | 16 / 25 — 64.0% |
| Mean / median full-path MAE | -5.95c / -1c | -7.34c / -1c |
| Worst full-path adverse excursion | -43.9c | -43.9c |
| Median time to +10c, among hits | 25.9 seconds | 18.9 seconds |
| Observed protected exits | 38 | 17 |
| Gross gain among those exits only | +10.07c | +13.12c |
| Armed without observed exit | 11 | 7 |
| Completed never-armed value paths | 3 | 1 |

The candidate keeps **25/53 opportunity IDs (47.2%)**, versus the frozen >=80% requirement, and **23/41 control +10c winner IDs (56.1%)**, versus >=90%. Its complete-entry count is only 25/51 = 49.0% of control. Its +11.6 percentage-point +10c lift and nonnegative chronological lifts pass, but cannot compensate for those retention failures. No additional candidate-only opportunity IDs occurred.

Chronological +10c: control **83.3%, 68.8%, 87.0%**; candidate **100%, 75%, 100%**, from only **6, 8 and 11** candidate entries. These small development blocks are descriptive, not untouched validation.

All protection uses the unchanged +5c arm and first observed 4c peak-giveback exit. Larger observed losses can occur between samples. Full PATH excursion labels can include bids after a protected EXIT: only **12/25** candidate paths reach +20c before or without that exit, compared with 16/25 anywhere on the recorded path. The analogous control count is 24/51, compared with 29/51. Those are still movement observations, not complete realized portfolio returns. Exit-only averages omit unresolved positions, fees, spread changes, depth and manual reaction costs; no total profit claim is made.

## Integrity, validation and reproducibility

Fourteen focused tests passed, covering prefix-causal EARLY detection, price/sequence/gap guards, actual ASK/later BID, first giveback, 30-second boundary, DOWN sign, strict serial ordering, ENDED_UNARMED reset, and armed/missing-path blocking. An independent Decimal calculation checked all **103** selected movement opportunities and found zero protection/reset inconsistencies. These tests verify the replay, not market performance.

Every scoring input is hash-allowlisted. The exact rules were committed before new outcome scoring. Data completeness checks use timestamps; unknown outcomes are not filled with zero. The older tapes lack the new clean feed's exchange-time/sequence provenance and depth, so recorded bid excursions do not guarantee an executable manual fill. No infrastructure investigation was reopened to make that limitation disappear.

The clean post-fix window and its backups were **not opened or scored**. Its original **2026-09-20T19:05:17.147189Z** boundary and prior provisional **20:15:00Z** reservation are unchanged. `membership.json` records all **247 contract IDs** inspected in this pass. The complete union from previous 349/560, 352/563 and 609-entry research remains unavailable; this new manifest does not certify the clean window's independence or move its cutoff.

Source fingerprints and locations are in `source_manifest.json`; per-file checksums are in `fingerprints.json`. `evidence_outputs.zip` contains the full report JSON, per-entry features/results, lifecycle audit, cohort membership, supplemental metrics and verification result. The required raw sources already persist at the listed repository revision or saved-file identity; they are not replaced with a growing service export.

To reproduce, place the four fingerprint-matching CSVs listed in `source_manifest.json` under this directory's `sources/`, then run:

```bash
python3 replay.py
python3 -m unittest -v test_replay.py
python3 audit.py
```

**Recommendation:** retain the existing protected modules and control. Do not promote either hypothesis and do not open the clean validation window for these failed candidates. The bounded research pass is complete; there is no new stable candidate from this evidence.
