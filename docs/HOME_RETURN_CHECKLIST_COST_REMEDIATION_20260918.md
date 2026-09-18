# HOME RETURN CHECKLIST — COST REMEDIATION

Only manual prerequisite currently blocked by Railway 50-service cap:

1. Open project noble-warmth.
2. Select exactly: v81-30-45-dashboard-validation
   - NOT v3
   - v2 was already deleted.
3. Confirm it remains dormant before deletion: historical audit showed 0 CPU / 0 RAM / 0 network for 7 days and no domains.
4. Delete that service and commit/apply Railway change.
5. Stop. Do not delete or modify anything else.

Then automated/assistant sequence:
A. Deploy scalp-incremental-disk-v2-20260918 in freed slot.
B. Attach producer PATH_EXPORT_TOKEN by Railway reference and private producer URL.
C. Run V2 static/functional/protocol gates + >=3 live refreshes + RAM threshold.
D. If V2 passes, deploy isolated Regime canary against V2.
E. Require exact source/evidence parity at common SHA.
F. Only after parity, begin bounded-state RAM optimization; protected live Regime stays control until proof.
G. No broad migration on any failed gate.
