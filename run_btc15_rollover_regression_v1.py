#!/usr/bin/env python3
"""Combined offline rollover regression suite. No network. No orders."""
import unittest
MODULES=[
"test_btc15_rollover_handoff_model_v1",
"test_btc15_rollover_stage_selector_v1",
"test_btc15_rollover_static_regression_gate_v1",
"test_expose_btc15_generated_runtime_v1",\n"test_replay_btc15_rollover_live_evidence_v1",\n"test_btc15_rollover_negative_paths_v1",\n"test_btc15_rollover_change_scope_gate_v1",\n"test_btc15_rollover_alignment_gate_v1",\n"test_btc15_rollover_provenance_gate_v1",\n"test_btc15_rollover_publication_gate_v1",\n"test_btc15_rollover_lifecycle_v1",\n"test_btc15_rollover_idempotency_gate_v1",\n"test_btc15_rollover_monotonic_gate_v1",\n"test_btc15_rollover_stage_expiry_gate_v1",\n"test_btc15_rollover_stage_immutability_gate_v1",
]
if __name__=="__main__":
 suite=unittest.TestSuite()
 loader=unittest.defaultTestLoader
 for m in MODULES:suite.addTests(loader.loadTestsFromName(m))
 r=unittest.TextTestRunner(verbosity=2).run(suite)
 if not r.wasSuccessful():raise SystemExit(1)
 print("BTC15 ROLLOVER REGRESSION SUITE PASS | OFFLINE | SIGNAL ONLY | NO ORDERS")
