# Correct evidence sampling alias without changing signals

The five-second common observer became synchronized near4.7s into the five-second main producer cycle. It repeatedly saw stale BRTI while independent parity samples proved fresh source states earlier in the same cycles. That evidence cannot certify signal recall or continuous availability.

Use one-second readonly cached-state observations and an explicit observer epoch. This changes neither authenticated CF/BRTI upstream polling nor any detector/model/freshness/target/entry/exit rule. Existing consumer timeout and response-size limits remain. Published source timestamps are retained unchanged.

Start a new durable run ID `clean-source-v2-1s-20260923`, with new event/state/common/manifest paths on the same existing /data. Preserve and export the previous `clean-source-v2-20260923` run before switching. No file, service or volume is removed. Its previously registered20:30 cohort is development/measurement evidence with a documented sampling limitation; do not silently pool replacement data. Register a replacement future cohort before its first official open.

The existing pre-cadence run remains retrievable using an explicit allowlisted run_id on manifest/common/CSV export endpoints. Unknown IDs and filesystem paths are rejected. CSV export hashes and streams one fixed append-only prefix, retaining the checksum identity without loading the whole file.

Existing19 regressions plus2 cadence and2 retained-export tests must pass locally, hosted and at startup. Verify owner request cadence/counters remain consistent, all four cached endpoints respond, actual observer gaps approach1s, source age remains true and mixed-phase fresh/stale states become observable. These remain samples, not continuous availability proof. Check memory, append rate and available storage after cutover. Main/owner/V8.1/serial serving revisions remain unchanged.
