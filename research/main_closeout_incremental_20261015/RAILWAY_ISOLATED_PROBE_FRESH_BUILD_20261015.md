# Isolated Railway EARLY capacity probe — fresh deployment checkpoint

This file exists solely to pin a new source revision for a **fresh build** after Railway's `redeploy` reused a deployment snapshot with an outdated start command. No production source, validator code, thresholds, or data are changed.

Required isolated service settings:
- Service `existing-reader-capacity-probe` in project `btc15-early-capacity-test`
- 64 GiB dedicated volume mounted at `/research-evidence`
- Start command `python -m ops.live_recording.qualify_duration /research-evidence/early_capacity_probe_second_attempt`
- Restart policy NEVER; 4 vCPU and 8 GB memory limits
- Research-only synthetic duration qualification, no live feed, no orders

Acceptance: verify the **new deployment logs** actually use the new output path, then record whether the existing capacity reader completes and its resource usage. Never claim EARLY profitability, live capture or source equivalence from this synthetic test.

Production MAIN/V81/BRTI/SCALP and journals remain unchanged.
