# BTC15 EARLY Railway feasibility — capacity-only gate (2026-10-15)

Status: CONDITIONAL FEASIBILITY; NO-GO for launching an EARLY recording or claiming continuous capture.

## Current Railway state (read-only)
- Production: 15 services, 7 volumes.
- MAIN mounted volume: 20,000 MB capacity; ~10.72 GB current disk use from service metrics.
- V81 mounted volume: 5,000 MB capacity; ~3.13 GB current disk use.
- MAIN 24-hour average CPU ~2.32 vCPU, peak ~12.01 vCPU; average memory ~2.85 GB, peak ~2.99 GB.
- MAIN and V81 reported resource limits: 24 vCPU, 24 GB RAM per service. Limits are ceilings, not proof the application fits.
- Production staged changes were not accepted.

## Existing 24-hour reader/capture plan
- `ops/live_recording/policy.py` day profile: MAIN 1 GiB compressed, V81 512 MiB, information 512 MiB; decoded 12 GiB, 6,000,000 records; reader work database 48 GiB, index 3 GiB.
- `ops/live_recording/capacity.py`: minimum isolated Codespace work space = 48 GiB DB + 3 GiB index + 3 * 2 GiB total compressed archive + 2 GiB reserve = **59 GiB**. This is a planning minimum, not observed actual footprint; additional overhead and source staging may require more.
- Existing recording must measure >=900 seconds of steady-state throughput and pass projected compressed, decoded and record-count caps. No authenticated full-run rate proof was recovered.
- MAIN current volume cannot safely host a 59 GiB isolated analysis workspace; neither can V81.
- Railway documentation `https://docs.railway.com/volumes/reference` says paid plans support volume resize and Pro self-service up to 1 TB. Each service can have only one volume; volume attachment and access require deliberate design.
- Existing connector can inspect metrics/logs/config, but does not export volume bytes or create a transactionally consistent copy of MAIN's live journal.

## Decision and smallest useful test
1. Do not repeat the existing validator or start a 24h recording campaign.
2. Establish a read-only, consistent, credential-free evidence transfer to a **separate** Railway service/volume, without remounting or modifying MAIN's volume.
3. Size separate scratch storage above 59 GiB after measuring actual archive and reader footprint; do not assume 59 GiB is enough.
4. Run the existing, previously validated reader on a bounded authentic slice first. Measure peak disk, RAM, CPU, read/write throughput, retention, failure reason and exact EARLY evidence coverage.
5. Only then consider a continuous EARLY evidence run; stop if source transfer or complete source coverage cannot be demonstrated.
6. No change to FINAL/EARLY/SCALP model thresholds, no orders.

**This assessment proves storage is provisionable in principle, NOT that the end-to-end workload has passed.**

No new paid service or volume created; no deployment, restart, Railway config mutation or data deletion.
