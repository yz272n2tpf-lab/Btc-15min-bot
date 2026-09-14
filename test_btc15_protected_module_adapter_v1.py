#!/usr/bin/env python3
import unittest

from btc15_protected_module_adapter_v1 import (
    early_state_from_snapshot,
    final_state_from_snapshot,
    scalp_state_from_events,
    compose_dashboard_payload,
)


BASE_SNAPSHOT = {
    "contract": "KXBTC15M-TEST",
    "time_left_min": 5.0,
    "kalshi_target": 78000.0,
    "up_ask": 0.62,
    "down_ask": 0.39,
    "fair_preferred_side": "UP",
    "fair_preferred": 0.79,
    "preferred_kalshi_ask": 0.34,
    "fair_edge_vs_ask": 0.45,
    "entry_tournament_ready": True,
    "opportunity_status": "OPPORTUNITY",
    "final_status": "FINAL CALL",
    "final_side": "UP",
    "final_confidence": 0.94,
    "final_call_source": "TOURNAMENT WINNER",
}

BASE_CANDIDATE = {
    "record_type": "CANDIDATE",
    "candidate_id": "C1",
    "contract": "KXBTC15M-TEST",
    "side": "DOWN",
    "seconds_left": 300,
    "entry_ask": 0.40,
    "btc30": 22.0,
}


def path(gain, peak=None, elapsed=5):
    return {
        "record_type": "PATH",
        "candidate_id": "C1",
        "elapsed_sec": elapsed,
        "exec_gain": gain,
        "peak_exec_gain": gain if peak is None else peak,
    }


class ProtectedModuleAdapterTests(unittest.TestCase):
    def test_protected_early_maps_to_qualified(self):
        e = early_state_from_snapshot(BASE_SNAPSHOT)
        self.assertEqual(e.state, "QUALIFIED")
        self.assertEqual(e.side, "UP")
        self.assertAlmostEqual(e.ask, 0.34)
        self.assertAlmostEqual(e.fair, 0.79)
        self.assertAlmostEqual(e.seconds_left, 300.0)

    def test_early_watch_does_not_become_actionable(self):
        row = dict(BASE_SNAPSHOT, entry_tournament_ready=False, opportunity_status="WATCH")
        e = early_state_from_snapshot(row)
        self.assertEqual(e.state, "PASS")

    def test_protected_final_call_maps_to_lock(self):
        f = final_state_from_snapshot(BASE_SNAPSHOT)
        self.assertEqual(f.state, "LOCK")
        self.assertEqual(f.side, "UP")
        self.assertAlmostEqual(f.fair, 0.94)
        self.assertAlmostEqual(f.seconds_left, 300.0)

    def test_non_tournament_final_cannot_lock(self):
        row = dict(BASE_SNAPSHOT, final_call_source="LEGACY DIAGNOSTIC")
        f = final_state_from_snapshot(row)
        self.assertEqual(f.state, "WATCH")

    def test_scalp_frozen_gate_fails_closed(self):
        late = dict(BASE_CANDIDATE, seconds_left=119)
        weak = dict(BASE_CANDIDATE, btc30=14.99)
        self.assertEqual(scalp_state_from_events(late).state, "PASS")
        self.assertEqual(scalp_state_from_events(weak).state, "PASS")

    def test_scalp_active_before_arm(self):
        s = scalp_state_from_events(BASE_CANDIDATE, [path(0.03)])
        self.assertEqual(s.state, "ACTIVE")
        self.assertAlmostEqual(s.exec_gain, 0.03)

    def test_scalp_protect_appears_as_soon_as_validated_arm_fires(self):
        s = scalp_state_from_events(BASE_CANDIDATE, [path(0.05)])
        self.assertEqual(s.state, "PROTECT")
        self.assertAlmostEqual(s.peak_exec_gain, 0.05)

    def test_big_winner_stays_protect_before_four_cent_giveback(self):
        rows = [
            path(0.05, elapsed=5),
            path(0.12, elapsed=10),
            path(0.21, elapsed=15),
            path(0.19, peak=0.21, elapsed=20),
        ]
        s = scalp_state_from_events(BASE_CANDIDATE, rows)
        self.assertEqual(s.state, "PROTECT")
        self.assertAlmostEqual(s.peak_exec_gain, 0.21)
        self.assertAlmostEqual(s.exec_gain, 0.19)

    def test_four_cent_giveback_triggers_exit(self):
        rows = [
            path(0.05, elapsed=5),
            path(0.12, elapsed=10),
            path(0.21, elapsed=15),
            path(0.17, peak=0.21, elapsed=20),
        ]
        s = scalp_state_from_events(BASE_CANDIDATE, rows)
        self.assertEqual(s.state, "EXIT")
        self.assertAlmostEqual(s.exec_gain, 0.17)

    def test_dashboard_payload_keeps_countertrend_scalp_visible(self):
        payload = compose_dashboard_payload(
            BASE_SNAPSHOT,
            scalp_candidate=BASE_CANDIDATE,
            scalp_path_rows=[path(0.06)],
        ).to_dict()
        self.assertEqual(payload["headline"], "SCALP_PROTECT")
        self.assertEqual(payload["scalp_management_message"], "PROTECT PROFITS")
        labels = payload["combined"]["context_labels"]
        self.assertIn("COUNTERTREND_SCALP", labels)
        self.assertIn("MIXED_HORIZONS", labels)
        self.assertTrue(payload["manual_execution_only"])
        self.assertFalse(payload["numeric_flip_risk_validated"])
        self.assertNotIn("order", payload)
        self.assertNotIn("flip_risk_percent", payload)

    def test_contract_mismatch_fails_closed(self):
        wrong = dict(BASE_CANDIDATE, contract="OTHER")
        with self.assertRaises(ValueError):
            compose_dashboard_payload(BASE_SNAPSHOT, scalp_candidate=wrong)


if __name__ == "__main__":
    unittest.main()
