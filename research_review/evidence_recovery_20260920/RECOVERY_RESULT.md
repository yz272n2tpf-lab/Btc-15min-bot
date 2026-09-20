# BTC15 evidence recovery result — 2026-09-20

**Recommendation: BLOCKED by authenticated access to the original historical tape.** The original collector's volume is still attached. Its files and backups could not be inspected through the available authenticated routes; this is not evidence that the tape has been deleted. A durable clean-tape backup was successfully preserved without reading performance results.

Resume point: branch `scalp-ladder-evidence-review-20260920`, commit `47b5b20c553873b4c84bc797efa8b69e6481be7b`. Its saved closeout, manifest, and exact-hash requirements were read first. This recovery adds only this report, `inventory.json`, and `clean_membership_metadata.json` in `research_review/evidence_recovery_20260920/`.

## Recovered and preserved

| Artifact | Verified facts |
|---|---|
| `BTC15_CLEAN_RAW_BACKUP_20260920T203114Z.zip` | Durable save succeeded; 126,484 bytes; contains the unchanged raw CSV and its download receipt |
| ZIP SHA256 | `2cc0000be3624885ccc5044e64d490fdd1f1ec5c64261d57cf906f939f8b017d` |
| Raw CSV SHA256 | `f380e55ff9e87dfbe3279d0f750d299afd1a052edb47b48713e5454c963bff5d` |
| Raw CSV size | 1,077,238 bytes; equals HTTP Content-Length |
| Integrity | Downloaded-body hash equals `X-Source-SHA256`; local rehash and ZIP-member rehash also match; ZIP integrity check passed |
| Capture time | GET began 20:31:00.186312Z and completed 20:31:14.344019Z |
| Metadata inventory | 1,927 CSV records; 7 observed contract IDs; observed timestamps 19:05:35.172109Z through 20:31:09.605652Z |

Only `contract` and `timestamp_utc` were inspected for the metadata inventory. No bid, ask, feature, outcome, exit, P&L, hit rate, or clean-window score was opened or calculated. Seven observed IDs do not mean seven complete or eligible validation contracts. The metadata file lists every observed clean contract ID and its first/last timestamp. This is one point-in-time backup, not an ongoing backup job or a replacement for historical development evidence.

The source was the existing read-only `/research/path-export` on `scalp-finalprod-clean-v1`. No endpoint was added and no authentication setting was changed. A separate collector's raw tape is not proof of production-bot signal history.

## Historical recovery inventory

- Original service: `8b40a28c-1beb-4020-bdc2-e7e236fe3501` (`scalp-move-shadow-v1`).
- Verified attached volume: `656da4af-6a3f-4907-95da-2c0c0000cf29`, mounted at `/data`, reported capacity 5,000 MB.
- Latest deployment reported `SUCCESS`: `88ffe129-a6dd-418d-8261-f95bbe453fbf`, created 2026-09-15T04:28:23.885Z. This metadata does not verify file contents or collector health.
- The existing historical export returned **HTTP 401** at 20:31:00Z. Its response body was not used as evidence.
- Configuration confirms a `PATH_EXPORT_TOKEN` variable, but the connected OAuth tool explicitly redacts all variable values. No credential was exposed or guessed.
- The available connector has no direct volume-file listing/download or backup-download action. The documented [Railway volume file download](https://docs.railway.com/cli/volume#download-a-file-from-a-volume) route exists, but this workspace has no Railway CLI, CLI login, or Railway authentication token.
- The browser was not signed in. Secure GitHub sign-in was offered; credential entry was declined and sign-in was not completed. No further sign-in request or authentication workaround was attempted.
- The volume directory, rotations, and backup inventory remain **uninspected**, rather than verified absent. No historical raw bytes were recovered in this pass.

## Exact historical reproduction and lifecycle status

| Cohort | Required evidence / result |
|---|---|
| 352 full contracts / 563 opportunities | Required SHA256 `8dbd61e1e04057b8d123760209c108ccf14d58fd342fbcbe6a82907eda35927a`; raw tape and complete membership still missing; **archived reproduction BLOCKED** |
| Earlier 349 contracts / 560 opportunities | Kept separate; exact raw fingerprint, byte boundary, and complete membership not recovered |
| Separate 609-entry protection study | Kept separate (373 development / 236 historical holdout); exact raw fingerprint and complete inspected-contract membership not recovered |

The previous manifest records the required source hash but no exact original raw byte count. Without the raw tape, no prefix hash can be verified. Row counts and a growing export must not substitute for that verification. The September 3 1,474-event True Scalp dataset remains excluded.

The exact historical scorer remains unchanged, with verified dependency SHA256 `7f901c87774dd418db79a29f513b05245488a6ba0cedd6e7a8572ac9865ce55f`. Its aggregate results were recovered in the prior review; they were not upgraded to raw-tape proof here.

**Latest-lifecycle comparison: not performed.** The earlier isolated tests documented that the historical opportunity builder stops after a never-armed RESULT. It therefore does not implement the established ENDED_UNARMED reset. The +5¢ arm / first observed 4¢ giveback rule and armed/no-exit blocking remain preserved. No corrected scorer was introduced, no threshold search ran, and no market performance was inferred from the earlier 48 passing synthetic/offline tests. No strategy tests were rerun during this evidence-only pass.

## Validation remains provisional

- Candidate freeze remains `e86075aa058d0e6f90c6f97e818748a2c7351457`, committed **2026-09-20T19:44:37Z**. No candidate rule changed.
- Clean collection's original boundary remains **2026-09-20T19:05:17.147189Z**.
- The **20:15:00Z** reservation remains provisional and unchanged. No holdout is declared eligible.
- Every contract ID used in any development inspection must be excluded across all services, including the 349/560, 352/563, and 609-entry cohorts. Their complete union is not yet available.
- Complete-contract qualification and development disjointness remain unverified. No score was used to choose exclusions or move the cutoff.
- Clean service `b369287c-d8a1-4427-84de-25e39fe9fdf7` still reports no attached volume; deployment `93f2b49c-9078-4653-bd27-567d093df57a` reports `SUCCESS`. Its continuity was preserved, and this backup protects the captured bytes only.

## Smallest concrete recovery request

**Upload a read-only export of `/data/scalp_move_shadow_v1_events.csv` from the original `scalp-move-shadow-v1` collector.** This is the documented default source path; the actual volume file listing has not been inspected. If the file was rotated, include its corresponding rotations/backups. Do not upload passwords, API keys, or the export token.

Once that file is supplied, preserve its bytes, verify the exact required whole-file/prefix hash, and recover source membership before any scoring. Recover any additional development-cohort manifest only if the raw file and archived boundaries are insufficient. If the original prefix cannot be verified, keep the historical reproduction blocked. No replacement experiment is authorized by this request.

No Railway service, deployment, variable, volume attachment, production file, collector, BRTI component, quote-ingestion path, FINAL/EARLY rule, or dashboard was changed. No cleanup occurred. SIGNAL ONLY / MANUAL EXECUTION / NO ORDERS.

**BLOCKED — authenticated read/export of the original historical CSV is unavailable; the clean raw backup is preserved.**
