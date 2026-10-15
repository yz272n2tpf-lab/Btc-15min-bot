# BTC15 Railway cleanup audit — October 15, 2026

## Status (read-only inventory after authorized retirement operations)
- Initial services: 60; currently visible: 27; removals already reconciled: 33.
- Staged patch now visible: ead9997e-b5b7-4668-a612-e8417e197838, STAGED. The pre-existing, unrelated source patch is ead9997e-b5b7-4668-a612-e8417e197838 and must not be committed as part of cleanup.
- Zero-deployment research stubs: 22 removed, no volumes involved; see railway_preflight_20261015.json.
- Removed after configuration archive: combined-dashboard-shadow-v1, scalp-finalprod-clean-v1, btc15-v2-main-qualification, btc15-v2-v81-qualification, brti-shared-feed-shadow-1s-20261005, brti-1s-contract-monitor-20261005, btc15-1s-main-contract-monitor-20261005, v81-product-contract-monitor-20261005, scalp-coverage-audit-v1, combined-forward-scorecard-v1.
- scalp-move-shadow-v1 deletion accepted, but still APPLYING when this audit was written. Do not claim completion until Railway removes it.
- The old original production GitHub build, tested MAIN/V81 code and journals remain unchanged. No orders or production deployments were launched.

## Protected services and observations
- Btc-15min-bot: SUCCESS; deployment c0993600-34b7-4501-92cd-b8d4a934b68a.
- v81-live-diagnostics: SUCCESS; deployment 21bf7fd3-c294-46d9-8a0a-f551cce7a303.
- brti-shared-feed-v1: SUCCESS; deployment b0ddbbbb-7d7a-43ba-888f-9d7e8c6b3fd8.
- btc15-operator-cockpit-readonly: SUCCESS; deployment 5b326cf3-8998-4fba-854f-8aaad7c60c61.
- early-excursion-forward-v1: SUCCESS; deployment b6c7e09a-e6bd-4c36-a98c-48a50e72d0cf.
- early-final-handoff-v1: SUCCESS; deployment 43e32eee-afea-4986-a944-803a53945852.
- final-forward-scorecard-v1: SUCCESS; deployment 48b86488-3688-40d3-82b4-ad5fe028a61f.
- EARLY excursion service still reports 41 completed excursions out of 2,568 coverage-eligible observations; handoff service reports 42 EARLY records, 7 EARLY-to-FINAL handoffs and 733 settled FINAL records. These are not complete independent accuracy/profit proof. Do NOT retire or delete their ephemeral data without export.
- V81 producer and MAIN native journal are the working current signal-only architecture. Cockpit server reads only MAIN and V81 public paths; legacy scorecards/SCALP research endpoints are not its data dependencies.

## Preserved volumes (NO volume deletion performed)
- scalp-finalprod-clean-v1-volume: 50000 MB provisioned; attached to nobody (retained); ID 93e974dc-b8bb-4658-bed5-dc4815308396.
- scalp-move-shadow-v1-volume: 5000 MB provisioned; attached to nobody (retained); ID 656da4af-6a3f-4907-95da-2c0c0000cf29.
- btc15-v2-v81-journal: 2048 MB provisioned; attached to nobody (retained); ID 97cc9dcd-ef90-495e-a1be-ffda31eac1b3.
- btc15-v2-main-journal: 2048 MB provisioned; attached to nobody (retained); ID b6304c46-7027-4bfd-932d-94bb9c67da8e.
- btc15-main-shadow-1s-brti-volume: 1024 MB provisioned; attached to nobody (retained); ID 3ed8bbca-31aa-43c0-b672-60a7a75b062b.
- btc-15min-bot-volume: 20000 MB provisioned; attached to Btc-15min-bot; ID 6ced6b1a-3755-4518-a240-c895e936d443.
- btc15-v81-ladder-journal-v2: 5000 MB provisioned; attached to v81-live-diagnostics; ID d5eeafca-e0fc-42f0-b7d1-4705907720c6.

## Why filesystem pruning was not done
- Railway connector does not provide read-only SSH/file export/snapshot of volume bytes. Retained historical data are not yet verified off-platform backups.
- MAIN /data inventory reports ~8.6 GB used: root historical CSVs ~4.07 GB, btc15_v2_product ~2.52 GB, ground_zero ~1.30 GB, segmented information ~0.66 GB. Many are original research evidence and could still be needed for EARLY. Current native SQLite WAL files are open by the live process and must not be copied/deleted naively.
- Do not delete older research volumes, MAIN files, native journals, or private keys until an immutable verified independent backup and scope review. Detached volumes may still incur storage cost.

## Remaining candidates and stop condition
- Removed: no-volume undeployed stubs and the listed redundant workers. Configuration snapshots were preserved separately on this maintenance branch without secret values.
- Keep for now: in-memory EARLY forward observers, FINAL forward evaluator and any legacy artifact that is the only source of a research sample.
- Review separately: failed/crashed no-volume services, one-shot information identity/rollover review services, older publicly accessible UI previews, remaining standalone scoreboard, and staged main shadow. The live iPad UI link is not independently confirmed.
- Stop all further retirement actions while Railway reports an APPLYING patch. Verify original MAIN/V81 deployments and 4 unrelated staged source fields are unchanged after each change.
- This record is NOT an invoice or verified dollar savings. Use the Railway usage/billing page for charges.

## Exact current nonprotected service names
- information-identity-integration-v2 — SUCCESS
- final-v4-review-tooling-v1 — FAILED
- operator-cockpit-ipad-preview-20261006 — SUCCESS
- rollover-regression-v1 — SUCCESS
- rollover-core-integration-live-shadow — CRASHED
- csv-diagnostic-scan — CRASHED
- rollover-canary-predeploy-check — SUCCESS
- recovered-native-identity-qualification-v1 — CRASHED
- scalp-unarmed-live-tape-v1 — FAILED
- combined-dashboard-shadow-v11 — FAILED
- rollover-handoff-predeploy-check — SUCCESS
- scalp-display-bridge-v6 — FAILED
- information-identity-audit-v1 — SUCCESS
- information-identity-integration-v1 — SUCCESS
- authoritative-scoreboard-v1 — SUCCESS
- combined-dashboard-shadow-v14 — FAILED
- recovered-v11-preview-pr47 — SUCCESS
- recovered-v11-identity-pr49 — CRASHED
- recovered-v11-identity-pr48 — FAILED
- btc15-main-shadow-1s-brti-20261005 — SUCCESS
