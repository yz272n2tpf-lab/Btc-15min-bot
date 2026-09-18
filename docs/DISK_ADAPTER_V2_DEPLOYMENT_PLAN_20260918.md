# DISK ADAPTER V2 DEPLOYMENT PLAN — 2026-09-18

V2 must not replace the working V1 adapter until isolated/live validation passes.

## Predeploy
- Static source safety gate.
- Synthetic functional reconstruction gate.
- Existing V1 remains serving canary transport.

## Live validation
1. Deploy V2 in a freed temporary slot or temporarily repurpose only an explicitly disposable dormant service.
2. Supply producer PATH_EXPORT_TOKEN by Railway reference variable, never plaintext.
3. Use private producer URL only.
4. Capture V2 manifest bytes/rows/SHA.
5. At the closest common producer boundary compare V2 committed SHA/bytes to canonical export.
6. Fetch V2 deltas from offset 0 through manifest size; reconstruct externally/canary and require exact manifest SHA.
7. Measure V2 steady RAM/CPU for >=3 refresh cycles.
8. V2 RAM acceptance: <=0.20 GB preferred; <=0.35 GB hard engineering threshold. If >0.35 GB, do not promote as cost architecture.
9. Public TX/RX must remain effectively zero except health/control metadata.
10. orders=false/read_only=true.

## Promotion
Only after V2 passes, point isolated Regime canary to V2. Keep V1 until Regime transport parity passes. Then V1 may be retired after evidence record.

## Failure
Any byte/hash/row mismatch, auth failure, public-source fallback, write capability, or excessive RAM => STOP and preserve V1 + live consumers unchanged.
