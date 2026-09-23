# Railway dependency inventory — 2026-09-23 UTC

Read-only snapshot. Values and credentials deliberately excluded. No services deleted or redeployed. Raw reference expressions are inaccessible through this connector; externally confirmed owner credential repair is accepted. SUCCESS is deployment status, not proof of useful work.

## Btc-15min-bot

- Service: ab28dca6-7bea-4956-bdb9-dbb7b4c74635
- Commit: 662873c41fde364a994b6a22dc0bb18f21d43fdc
- Branch: main
- Deployment status: SUCCESS
- Start: `/bin/sh -c 'sleep 3; echo "BTC15 VOLUME INVENTORY BEGIN" >&2; du -ah /data 2>/dev/null | sort -hr | head -40 >&2; echo "BTC15 VOLUME INVENTORY END" >&2; sleep 1; exec python -u BTC15_DASHBOARD_INLINE_SCALP_DIAG_V2.py'`
- Domains: btc-15min-bot-production.up.railway.app
- Variable names: BTC15_BRTI_GATEWAY_URL, BTC15_BRTI_SHARED_URL, BTC15_BRTI_TRANSPORT, BTC15_DASH_V13_Z1, BTC15_DASH_V13_Z2, BTC15_DASH_V13_Z3, BTC15_DASH_V13_Z4, BTC15_DASH_V13_Z5, BTC15_INLINE_SCALP_V1, BTC15_KALSHI_QUOTE_PROVENANCE_CANARY, BTC15_USE_SHARED_BRTI, BTC15_VOLUME_DIAG, KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, PORT, PYTHONUNBUFFERED
- Volumes: {'6ced6b1a-3755-4518-a240-c895e936d443': {'mountPath': '/data'}}

## scalp-lead-shadow

- Service: 90d3435e-c98c-43ae-880f-cd629b9606e2
- Commit: 79d96d1249c68ee05b1f013497d3acef7bc5044f
- Branch: main
- Deployment status: SUCCESS
- Start: `python -c "import time; print('PARKED: obsolete scalp-lead-shadow research worker; production unchanged', flush=True); time.sleep(31536000)"`
- Domains: 
- Variable names: KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, LEGACY_RESEARCH_PARKED, PYTHONUNBUFFERED
- Volumes: {}

## scalp-lead-qualified

- Service: f6e62c87-ac2a-4340-8be2-72932ad4c486
- Commit: faa25e8bd59fdc6016073df42d173640698cd52f
- Branch: scalp-lead-research-v3
- Deployment status: SUCCESS
- Start: `python -c "import time; print('PARKED: obsolete scalp-lead-qualified research worker; production unchanged', flush=True); time.sleep(31536000)"`
- Domains: 
- Variable names: KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, LEGACY_RESEARCH_PARKED, PYTHONUNBUFFERED
- Volumes: {}

## scalp-lead-v4

- Service: ca605c00-4608-4b32-b0bb-d1ca9c6b42a5
- Commit: faa25e8bd59fdc6016073df42d173640698cd52f
- Branch: scalp-lead-research-v3
- Deployment status: SUCCESS
- Start: `python -c "import time; print('PARKED: obsolete scalp-lead-v4 research worker; production unchanged', flush=True); time.sleep(31536000)"`
- Domains: 
- Variable names: KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, LEGACY_RESEARCH_PARKED, PYTHONUNBUFFERED
- Volumes: {}

## scalp-lead-v5-live

- Service: 7e643823-456a-414b-a369-0ee40462223f
- Commit: faa25e8bd59fdc6016073df42d173640698cd52f
- Branch: scalp-lead-research-v3
- Deployment status: SUCCESS
- Start: `python -c "import time; print('PARKED: obsolete scalp-lead-v5-live research worker; production unchanged', flush=True); time.sleep(31536000)"`
- Domains: 
- Variable names: KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, PYTHONUNBUFFERED
- Volumes: {}

## scalp-lead-v5-main

- Service: 2b0060ac-e0d1-49a2-a2f6-b577fd9ac478
- Commit: 79d96d1249c68ee05b1f013497d3acef7bc5044f
- Branch: main
- Deployment status: SUCCESS
- Start: `python -c "import time; print('PARKED: obsolete scalp-lead-v5-main research worker; production unchanged', flush=True); time.sleep(31536000)"`
- Domains: 
- Variable names: KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, LEGACY_RESEARCH_PARKED, PYTHONUNBUFFERED
- Volumes: {}

## scalp-lead-v6

- Service: ea6e520b-fa94-49bb-abf9-094817ae3d6b
- Commit: 59c5d7fd8a2dc0a4ecbe5ede340e1fd360c3137c
- Branch: scalp-lead-research-v3
- Deployment status: SUCCESS
- Start: `python -c "import time; print('PARKED: duplicate scalp-lead-v6 research worker; v6-main retained', flush=True); time.sleep(31536000)"`
- Domains: 
- Variable names: KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, PYTHONUNBUFFERED
- Volumes: {}

## scalp-lead-v6-main

- Service: 568716be-9c96-446e-aecb-0fcd16158b8e
- Commit: 662873c41fde364a994b6a22dc0bb18f21d43fdc
- Branch: main
- Deployment status: SUCCESS
- Start: `python -u -c "import time; print('PARKED: V6 superseded during V8.1 production-rate-limit cleanup; no live Kalshi polling', flush=True); time.sleep(31536000)"`
- Domains: 
- Variable names: BTC15_PARK_V6, KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, PYTHONUNBUFFERED
- Volumes: {}

## scalp-v81-sub30-shadow

- Service: 2e63484b-e726-41fc-980a-a117b5efdcfd
- Commit: 5044a309b79d8b2036edba4a3b7952bb8485ce86
- Branch: scalp-lead-research-v3
- Deployment status: SUCCESS
- Start: `python -u -c "import time; print('PARKED: old scalp-v81-sub30-shadow; no live Kalshi polling', flush=True); time.sleep(31536000)"`
- Domains: 
- Variable names: BTC15_PARK_OLD_SUB30, KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, PYTHONUNBUFFERED
- Volumes: {}

## scalp-v81-sub30-shadow-v2

- Service: b883a5e1-7cef-4d3d-b3f6-cffccde53053
- Commit: 5044a309b79d8b2036edba4a3b7952bb8485ce86
- Branch: scalp-lead-research-v3
- Deployment status: SUCCESS
- Start: `python -u -c "print('SUB30_FORWARD_TEST_PARKED')"`
- Domains: 
- Variable names: KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, PYTHONUNBUFFERED, RESEARCH_PARK_TRIGGER
- Volumes: {}

## v81-immutable-test

- Service: 0bda3f3d-90b7-4934-8636-d16a45a3dc32
- Commit: 0a58af58e7c06d6b87e3fe83af2cf2f65f3383ce
- Branch: v81-immutable-20260911
- Deployment status: SUCCESS
- Start: `python -u scalp_lead_sub30_v8_1_locked.py`
- Domains: 
- Variable names: KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, PYTHONUNBUFFERED, RESEARCH_PARK_TRIGGER
- Volumes: {}

## v81-final-isolated-test

- Service: 10045980-cdd0-485a-a827-b50a3f0b4943
- Commit: 0a58af58e7c06d6b87e3fe83af2cf2f65f3383ce
- Branch: v81-immutable-20260911
- Deployment status: SUCCESS
- Start: `python -u scalp_lead_sub30_v8_1_locked.py`
- Domains: 
- Variable names: BTC15_PARK_V81_FINAL_TEST, KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, PYTHONUNBUFFERED
- Volumes: {}

## v81-30-45-dashboard-validation-v3

- Service: 43e53181-102a-4759-a7cd-70875c605cf0
- Commit: 79d96d1249c68ee05b1f013497d3acef7bc5044f
- Branch: main
- Deployment status: SUCCESS
- Start: `python -u BTC15_V81_30_45_DASHBOARD_CANDIDATE_V1.py --self-test`
- Domains: 
- Variable names: 
- Volumes: {}

## v81-30-45-live-feed-v2

- Service: afd8f1f0-65f6-46f0-a79b-ef582f35293f
- Commit: 40a4253bdf982d415058a281b900a08d76a061f8
- Branch: v81-30-45-live-feed-immutable-20260912
- Deployment status: SUCCESS
- Start: `python -u -c "import time; print('PARKED: superseded by v81-live-diagnostics feed; no live Kalshi polling', flush=True); time.sleep(31536000)"`
- Domains: v81-30-45-live-feed-v2-production.up.railway.app
- Variable names: KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, PYTHONUNBUFFERED
- Volumes: {}

## v81-live-diagnostics

- Service: 6025e83e-a41c-4e0a-8c16-f71120bd501b
- Commit: 4b21380a76713a406c9bbb5a129fca37ead5087d
- Branch: v81-live-diagnostics-20260912
- Deployment status: SUCCESS
- Start: `python -u v81_30_45_live_feed.py`
- Domains: v81-live-diagnostics-production.up.railway.app
- Variable names: KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, PYTHONUNBUFFERED, V81_DIAG_LIVE
- Volumes: {}

## scalp-move-shadow-v1

- Service: 8b40a28c-1beb-4020-bdc2-e7e236fe3501
- Commit: bce9ab4a3c067fea081f576f2211ee775e65ea83
- Branch: scalp-move-shadow-v1-20260912
- Deployment status: SUCCESS
- Start: `/bin/sh -c 'if [ -z "$KALSHI_KEY_ID" ] || [ -z "$KALSHI_PRIVATE_KEY_B64" ]; then echo "SCALP MOVE WAITING FOR VARIABLES | NO ORDERS"; sleep 31536000; else python -m unittest -q test_scalp_live_event_cache_v1.py test_btc15_combined_state_bridge_v4.py test_btc15_combined_state_bridge_v3.py test_btc15_main_protected_state_adapter_v1.py test_btc15_cross_service_payload_v4.py test_scalp_integration_state_bridge_v4.py test_scalp_integration_state_bridge_v3.py test_btc15_protected_module_adapter_v1.py test_BTC15_SCALP_SERIAL_STATE_BRIDGE_SHADOW_V1.py test_scalp_integration_state_bridge_v5.py test_btc15_combined_state_bridge_v5.py && exec python -u btc15_combined_state_bridge_v5.py; fi'`
- Domains: scalp-move-shadow-v1-production.up.railway.app
- Variable names: ADAPTER_TEST_TRIGGER, COLLECTOR_RESTORE_TRIGGER, COMBINED_SCALP_UI_SELFTEST_TRIGGER, COMBINED_STATE_BRIDGE_DEPLOY_TRIGGER, DASHBOARD_DOM_PROBE_TRIGGER, EARLY_PIPELINE_RUN_TRIGGER, EARLY_PIPELINE_V3_TRIGGER, INTEGRATION_BRIDGE_TEST_TRIGGER, INTEGRATION_FIXTURE_TRIGGER, INTEGRATION_LATCH_TRIGGER, INTEGRATION_RESEARCH_SUITE_TRIGGER, INTEGRATION_V3_TRIGGER, KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, MAIN_SCHEMA_PROBE_TRIGGER, NESTED_MAIN_ADAPTER_DEPLOY_TRIGGER, PATH_EXPORT_ENABLE, PATH_EXPORT_TOKEN, PROTECTION_TIMING_AUDIT_TRIGGER, PYTHONUNBUFFERED, SCALP_COLLECTOR_SCRIPT, SCALP_EVENT_CSV, SCALP_V4_DEPLOY_TRIGGER, SCORE_RUN_TRIGGER, STABILITY_RUN_TRIGGER, STATE_BRIDGE_V2_TRIGGER, TRANSITION_MONITOR_TRIGGER
- Volumes: {'656da4af-6a3f-4907-95da-2c0c0000cf29': {'mountPath': '/data'}}

## brti-shared-feed-v1

- Service: 0fe5d048-873e-4c1c-a3d4-8e7216e44f3e
- Commit: 98cb9e538d584ad326d19af10924960dbff42672
- Branch: brti-shared-feed-v1-20260913
- Deployment status: SUCCESS
- Start: `repository configuration`
- Domains: brti-shared-feed-v1-production.up.railway.app
- Variable names: BRTI_SHARED_ENABLE, BRTI_SHARED_MAX_429_BACKOFF_S, BRTI_SHARED_MAX_QUAL_AGE_S, BRTI_SHARED_POLL_INTERVAL_S, KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, PYTHONUNBUFFERED
- Volumes: {}

## v81-live-diag-shared-brti-shadow

- Service: 84f579fc-36d0-4170-8a28-6d26c01bb364
- Commit: baf4d3e7376a57a8e117f154cc263f9a7099d5d3
- Branch: v81-live-diag-shared-brti-shadow-20260913
- Deployment status: SUCCESS
- Start: `repository configuration`
- Domains: 
- Variable names: BRTI_SHARED_CLIENT_MAX_AGE_MS, BRTI_SHARED_CLIENT_TIMEOUT_S, BRTI_SHARED_URL, KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, PYTHONUNBUFFERED
- Volumes: {}

## combined-dashboard-shadow-v1

- Service: 142e0fe5-13ce-4cb7-a08b-d4a65539fb47
- Commit: 529ffe00a766c45816fc7524c5b801a19bb9c841
- Branch: scalp-move-shadow-v1-20260912
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_btc15_combined_dashboard_shadow_v1.py && python -u BTC15_DASHBOARD_COMBINED_SCALP_UI_V10.py --self-test && exec python -u btc15_combined_dashboard_shadow_v6.py`
- Domains: combined-dashboard-shadow-v1-production.up.railway.app
- Variable names: 
- Volumes: {}

## scalp-coverage-audit-v1

- Service: f020787f-00fb-4a46-a36c-710f18bbf31e
- Commit: c3851b75bf3dcf13c69f54555217c2848db72b30
- Branch: scalp-move-shadow-v1-20260912
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_BTC15_DIRECT_BRTI_FLIP_RISK_MODEL_V1.py test_BTC15_DIRECT_BRTI_FLIP_RISK_FORWARD_V2.py && echo 'DIRECT BRTI FLIP RISK V1+V2 TESTS PASS | FUTURE-ONLY ISOTONIC SHADOW | NO ORDERS' && exec python -u BTC15_DIRECT_BRTI_FLIP_RISK_FORWARD_V2.py`
- Domains: 
- Variable names: SCALP_PATH_EXPORT_TOKEN
- Volumes: {}

## scalp-unarmed-live-tape-v1

- Service: cc7ca702-ddbc-4f61-8205-873e34b7d740
- Commit: 4f9ccd30b0f3a06f428d1ee4c4246ab3cd4e971f
- Branch: unarmed-health-startup-fix-20260918
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_btc15_scalp_unarmed_live_tape_validator_v1.py test_BTC15_SCALP_TRIGGER_TIGHTENING_RESEARCH_V1.py test_BTC15_SCALP_FAILED_PREARM_RESET_TOURNAMENT_V1.py test_BTC15_SCALP_BLUEPRINT_REVIEW_GATE_V1.py test_BTC15_SCALP_PROTECTION_AUDIT_V1.py test_BTC15_SCALP_BLUEPRINT_COVERAGE_AUDIT_V1.py test_scalp_unarmed_memory_opt_behavior_v1.py && python -u test_scalp_unarmed_memory_opt_static_v1.py && python -u test_scalp_unarmed_supervisor_static_v1.py && exec python -u btc15_scalp_unarmed_supervisor_v1.py`
- Domains: 
- Variable names: FALSE_START_STUDY_TRIGGER, PYTHONUNBUFFERED, SCALP_BLUEPRINT_CUTOFF_UTC, SCALP_PATH_EXPORT_TOKEN, SCALP_PATH_EXPORT_URL, SCALP_UNARMED_LIVE_POLL_SEC
- Volumes: {}

## scalp-display-bridge-v6

- Service: 90046a79-3f57-493f-b473-18d0031e8f0d
- Commit: 8ef764d8d9d575efa555a21147470a918966fc1d
- Branch: scalp-move-shadow-v1-20260912
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_btc15_combined_state_bridge_v6_display.py && exec python -u btc15_combined_state_bridge_v6_display.py`
- Domains: scalp-display-bridge-v6-production.up.railway.app
- Variable names: 
- Volumes: {}

## combined-dashboard-shadow-v11

- Service: 87801206-d705-43d6-8aa2-bfb1b11c1ff6
- Commit: 8dee88475df0dde8ea3177b7102fd9328667c844
- Branch: scalp-move-shadow-v1-20260912
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_btc15_combined_dashboard_shadow_v1.py test_btc15_combined_dashboard_shadow_v7.py && python -u BTC15_DASHBOARD_COMBINED_SCALP_UI_V12.py --self-test && exec python -u btc15_combined_dashboard_shadow_v8.py`
- Domains: combined-dashboard-shadow-v11-production.up.railway.app
- Variable names: 
- Volumes: {}

## final-forward-scorecard-v1

- Service: fbe79688-25ed-4329-b0d6-c9b669559b17
- Commit: 5a767fd40d394f86e9012bd96a9efefabfd081bf
- Branch: scalp-move-shadow-v1-20260912
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_BTC15_FINAL_FORWARD_SCORECARD_V1.py test_BTC15_FINAL_FORWARD_SCORECARD_V2.py test_BTC15_FINAL_FORWARD_SCORECARD_V3.py test_BTC15_FINAL_FORWARD_SCORECARD_V4.py && exec python -u BTC15_FINAL_FORWARD_SCORECARD_V4.py`
- Domains: final-forward-scorecard-v1-production.up.railway.app
- Variable names: FINAL_SCORECARD_POLL_SEC, FINAL_SCORECARD_VERSION
- Volumes: {}

## combined-forward-scorecard-v1

- Service: e9399baa-25a8-4801-a374-ae6c5401060d
- Commit: da5fdbf5dbd8579946cf481d82ce0abfabee2efb
- Branch: scalp-move-shadow-v1-20260912
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_btc15_combined_empirical_scorecard_v2.py test_BTC15_COMBINED_FORWARD_SCORECARD_V2.py test_BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V1.py test_BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V2.py test_BTC15_KALSHI_ROLLOVER_OPERATIONAL_GATE_V3.py test_BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V3.py && exec python -u BTC15_COMBINED_V2_WITH_ROLLOVER_PROBE_V3.py`
- Domains: 
- Variable names: COMBINED_SCORECARD_POLL_SEC, ROLLOVER_PROBE_VERSION
- Volumes: {}

## combined-dashboard-shadow-v13

- Service: b210d5f0-0616-4e39-9812-ce7b41b73d67
- Commit: 6a41d6a35f667228d7e8aab6c95d1e502f9a141c
- Branch: scalp-move-shadow-v1-20260912
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_btc15_combined_dashboard_shadow_v1.py test_btc15_combined_dashboard_shadow_v7.py test_BTC15_DASHBOARD_COMBINED_SCALP_UI_V13.py && python -u BTC15_DASHBOARD_V13_PRESENTATION_AUDIT_V1.py && python -u BTC15_DASHBOARD_COMBINED_SCALP_UI_V13.py --self-test && exec python -u btc15_combined_dashboard_shadow_v9.py`
- Domains: combined-dashboard-shadow-v13-production.up.railway.app
- Variable names: V13_SHADOW_PRESENTATION_ONLY
- Volumes: {}

## early-forward-scorecard-v1

- Service: efb56ace-8c0e-4672-a772-6dd3b8633078
- Commit: 672f83a07a0be2cec3ff0b13cfab25f514952948
- Branch: scalp-move-shadow-v1-20260912
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_BTC15_EARLY_FORWARD_SCORECARD_V2.py test_btc15_main_protected_state_adapter_v1.py test_btc15_protected_module_adapter_v1.py test_btc15_signal_integration_v1.py && exec python -u BTC15_EARLY_FORWARD_SCORECARD_V2.py`
- Domains: early-forward-scorecard-v1-production.up.railway.app
- Variable names: EARLY_SCORECARD_BOOTSTRAP
- Volumes: {}

## early-final-handoff-v1

- Service: 174bd89d-264b-4882-8d5a-b8dbacf97181
- Commit: cb05a536a1164132d4a4b872bb90b7bcd1a804d3
- Branch: scalp-move-shadow-v1-20260912
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_BTC15_EARLY_FINAL_HANDOFF_FORWARD_V1.py && exec python -u BTC15_EARLY_FINAL_HANDOFF_FORWARD_V1.py`
- Domains: 
- Variable names: HANDOFF_SCORECARD_BOOTSTRAP
- Volumes: {}

## early-excursion-forward-v1

- Service: 6b847381-fc63-4421-b7bd-e8111c844e2f
- Commit: 54cf41ea4b8c8cc341f7678921508ee36d8ee06b
- Branch: scalp-move-shadow-v1-20260912
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_BTC15_EARLY_EXCURSION_FORWARD_V1.py && exec python -u BTC15_EARLY_EXCURSION_FORWARD_V1.py`
- Domains: 
- Variable names: EARLY_EXCURSION_BOOTSTRAP
- Volumes: {}

## authoritative-scoreboard-v1

- Service: 6c0ec9d5-2187-4623-97ec-44c3304b8074
- Commit: 4728a5a7d989c9860a07693a37bdd6549bc33b0f
- Branch: scalp-move-shadow-v1-20260912
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_BTC15_AUTHORITATIVE_SCOREBOARD_V1.py test_BTC15_AUTHORITATIVE_SCOREBOARD_LIVE_V1.py test_BTC15_AUTHORITATIVE_SCOREBOARD_V2.py test_BTC15_AUTHORITATIVE_SCOREBOARD_VIEWMODEL_V1.py && python -c "import json; import BTC15_AUTHORITATIVE_SCOREBOARD_LIVE_V3 as m; import BTC15_AUTHORITATIVE_SCOREBOARD_VIEWMODEL_V1 as vm; s=m.collect_live(); v=vm.build_viewmodel(s['scoreboard']); print('SCOREBOARD V3 STARTUP PROBE | '+json.dumps({'connected':s['connected_sources'],'expected':s['expected_sources'],'all':s['all_sources_connected'],'final':v['cards']['final'],'early':v['cards']['early'],'scalp':v['cards']['scalp'],'excursion':v['cards']['early_excursion'],'handoff':v['cards']['handoff'],'flip':v['cards']['flip_risk'],'system':v['cards']['system']},sort_keys=True),flush=True)" && exec python -u BTC15_AUTHORITATIVE_SCOREBOARD_LIVE_V3.py`
- Domains: 
- Variable names: SCOREBOARD_BOOTSTRAP, SCOREBOARD_CONNECTIVITY_PROBE, SCOREBOARD_VERSION
- Volumes: {}

## combined-dashboard-shadow-v14

- Service: c1db8b80-f656-4295-ade8-812c129f6c72
- Commit: 1c63eb3270509f01b976ec9709a5741f66796147
- Branch: scalp-move-shadow-v1-20260912
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_BTC15_DASHBOARD_COMBINED_SCALP_UI_V13.py test_BTC15_DASHBOARD_COMBINED_SCALP_UI_V14.py test_BTC15_DASHBOARD_PRESENTATION_AUDIT_V14.py test_BTC15_DASHBOARD_V14_EXACT_DIFF.py test_btc15_combined_dashboard_shadow_v7.py test_btc15_combined_dashboard_shadow_v10.py && python BTC15_DASHBOARD_COMBINED_SCALP_UI_V14.py --self-test && exec python -u btc15_combined_dashboard_shadow_v10.py`
- Domains: combined-dashboard-shadow-v14-production.up.railway.app
- Variable names: V14_CANDIDATE, V14_DOM_AUDIT_BOOTSTRAP, V14_STABILITY_SOURCE_AUDIT
- Volumes: {}

## final-v4-review-tooling-v1

- Service: 56b8496c-8dea-409b-a236-9e139a9c2e96
- Commit: 5bcfc7e61cf3d6693a0c42d704916ee7de7f4788
- Branch: scalp-move-shadow-v1-20260912
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_BTC15_FINAL_V4_FROZEN_REVIEW_REPORT_V1.py test_BTC15_FINAL_V4_REVIEW_LIVE_V1.py test_BTC15_EARLY_V1_FROZEN_REVIEW_REPORT_V1.py test_BTC15_REVIEW_HUB_LIVE_V1.py test_BTC15_HANDOFF_V1_FROZEN_REVIEW_REPORT_V1.py test_BTC15_EARLY_EXCURSION_V1_FROZEN_REVIEW_REPORT_V1.py test_BTC15_REVIEW_HUB_LIVE_V2.py test_BTC15_FLIP_RISK_V2_FROZEN_REVIEW_REPORT_V1.py && exec python -u BTC15_REVIEW_HUB_LIVE_V2.py`
- Domains: 
- Variable names: EARLY_V1_REVIEW_QA, FINAL_V4_REVIEW_LIVE_QA, FINAL_V4_REVIEW_QA, FLIP_V2_REVIEW_QA, HANDOFF_V1_REVIEW_QA, REVIEW_HUB_V1_QA, REVIEW_HUB_V2_QA
- Volumes: {}

## scalp-entry-profit-holdout-v1

- Service: 4a7f7942-7701-4441-8061-d1c6148d0e81
- Commit: 14ef7cf264eb2e53246082038bd90eef9dde63da
- Branch: scalp-entry-profit-ladder-v1
- Deployment status: CRASHED
- Start: `python -u shadow_diagnostics/scalp_entry_profit_holdout_review_v1.py`
- Domains: 
- Variable names: PYTHONUNBUFFERED, SCALP_ENTRY_PROFIT_HOLDOUT_POLL_SEC, SCALP_ENTRY_PROFIT_HOLDOUT_TRIGGER, SCALP_PATH_EXPORT_TOKEN, SCALP_PATH_EXPORT_URL
- Volumes: {}

## scalp-reversal-reentry-holdout-v1

- Service: a0f417fe-9bfe-4d80-bcd0-5647a582a1e7
- Commit: b124c54ea9d015d88c5237d5e0bc45ded8a37f36
- Branch: scalp-reversal-reentry-ladder-v1
- Deployment status: CRASHED
- Start: `python -u shadow_diagnostics/scalp_reversal_reentry_holdout_review_v1.py`
- Domains: 
- Variable names: PYTHONUNBUFFERED, SCALP_PATH_EXPORT_TOKEN, SCALP_PATH_EXPORT_URL, SCALP_REVERSAL_REENTRY_HOLDOUT_POLL_SEC, SCALP_REVERSAL_REENTRY_HOLDOUT_TRIGGER
- Volumes: {}

## scalp-incremental-disk-v2

- Service: f4d0996f-9dd1-47ba-a237-67353acd5bec
- Commit: 652b52f0330c68ef9fe3ba1ee5c1fb57151d6d08
- Branch: scalp-incremental-disk-v2-20260918
- Deployment status: SUCCESS
- Start: `python -u scalp_incremental_evidence_disk_v2.py`
- Domains: 
- Variable names: PATH_EXPORT_TOKEN, SCALP_INCREMENTAL_POLL_SEC, SCALP_PATH_EXPORT_URL
- Volumes: {}

## scalp-finalprod-clean-v1

- Service: b369287c-d8a1-4427-84de-25e39fe9fdf7
- Commit: f59276fd4733bbc374be53aaa4bb8063ed0f81ab
- Branch: scalp-finalprod-clean-v1-20260920
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_scalp_move_finalprod_clean_static.py && exec env SCALP_COLLECTOR_SCRIPT=scalp_move_shadow_v2_finalprod_clean.py python -u scalp_path_export_bridge_v1.py`
- Domains: scalp-finalprod-clean-v1-production.up.railway.app
- Variable names: BTC15_BRTI_GATEWAY_URL, BTC15_BRTI_TRANSPORT, BTC15_DATA_DIR, BTC15_FINAL_PROD_STATE_URL, BTC15_KALSHI_QUOTE_PROVENANCE_CANARY, BTC15_USE_SHARED_BRTI, KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, PATH_EXPORT_ENABLE, PORT, PYTHONUNBUFFERED, SCALP_EVENT_CSV, SCALP_STATE_JSON
- Volumes: {}

## scalp-developing-move-v1-forward

- Service: fcfb3a93-f007-4061-9cb8-bdae28f72cc2
- Commit: 996876246ace08c3b2bf8afa43b5b223336c13c7
- Branch: research/scalp-developing-move-filter-v1-20260921
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_score_scalp_developing_move_filter_v1.py && exec python -u scalp_developing_move_filter_v1_forward_observer.py`
- Domains: 
- Variable names: 
- Volumes: {}

## rollover-alt-discovery-probe-v1

- Service: 5a3eda51-3074-42aa-9e46-06695d47a378
- Commit: cceca7356e1d97645ab2b1fa408515eee7f66888
- Branch: research/rollover-alternate-discovery-probe-v1-20260921
- Deployment status: SUCCESS
- Start: `python -u btc15_rollover_alternate_discovery_probe_v1.py`
- Domains: 
- Variable names: 
- Volumes: {}

## rollover-prediscovery-shadow-v1

- Service: 9a566a85-0b12-4ab7-9c95-cced457e3bf5
- Commit: 0912a86440b9ef6e6573ea5ad2158a4a498c9e8a
- Branch: research/rollover-prediscovery-shadow-v1-20260922
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_btc15_rollover_prediscovery_shadow_v1.py && exec python -u btc15_rollover_prediscovery_shadow_v1.py`
- Domains: 
- Variable names: 
- Volumes: {}

## rollover-regression-v1

- Service: 331072c6-1ab4-47dc-a6b4-c3af053e4975
- Commit: ce401294cf5d7e46d03e7ade267abfba20bd7566
- Branch: research/rollover-production-regression-v1-20260922
- Deployment status: SUCCESS
- Start: `python -m unittest -q test_expose_btc15_generated_runtime_v1.py && python expose_btc15_generated_runtime_v1.py && python run_btc15_rollover_regression_v1.py`
- Domains: 
- Variable names: 
- Volumes: {}

## rollover-core-integration-live-shadow

- Service: ab491df9-2b75-43f2-92da-bc2a6db1cf6d
- Commit: ce401294cf5d7e46d03e7ade267abfba20bd7566
- Branch: research/rollover-production-regression-v1-20260922
- Deployment status: CRASHED
- Start: `python -u bot_two_output_build_v4_13_rollover_prediscovery_integration_shadow.py`
- Domains: 
- Variable names: 
- Volumes: {}

## rollover-canary-predeploy-check

- Service: fd54c023-b855-4ccb-90ca-4cbf772bdf4a
- Commit: edd16ff4624e2cffa0018b8e119d11d5b5d4c767
- Branch: research/rollover-production-canary-v1-20260922
- Deployment status: SUCCESS
- Start: `python -m py_compile btc15_rollover_production_canary_v1.py bot_two_output_build_v4_13_profit_protection_shadow.py && python -c "import btc15_rollover_production_canary_v1 as c; print('CANARY IMPORT PASS | OBSERVE ONLY | NO ORDERS')"`
- Domains: 
- Variable names: 
- Volumes: {}

## rollover-handoff-predeploy-check

- Service: cf307d3c-064f-4675-a2d5-c61ec0429f62
- Commit: 85a7ce60c34974396d441b75b640aa40f315f72f
- Branch: fix/rollover-staged-handoff-v1-20260922
- Deployment status: SUCCESS
- Start: `python -m py_compile btc15_rollover_production_canary_v1.py bot_two_output_build_v4_13_profit_protection_shadow.py test_btc15_rollover_staged_handoff_prod_v1.py && python -m unittest -v test_btc15_rollover_staged_handoff_prod_v1.py`
- Domains: 
- Variable names: 
- Volumes: {}
