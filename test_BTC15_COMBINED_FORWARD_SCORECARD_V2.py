#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

import BTC15_COMBINED_FORWARD_SCORECARD_V2 as v2

NOW = datetime(2026, 9, 15, 18, 15, 1, tzinfo=timezone.utc)


def combined(contract="A", left=500.0, early_state="PASS", final_state="WATCH"):
    return {
        "version": "BTC15_COMBINED_STATE_BRIDGE_V5",
        "contract": contract,
        "canonical_seconds_left": left,
        "orders": False,
        "manual_execution_only": True,
        "order_action": None,
        "numeric_flip_risk_validated": False,
        "scalp_lifecycle_metadata_only": True,
        "scalp_ended_unarmed_is_actionable_exit": False,
        "scalp_armed_no_exit_reset_allowed": False,
        "up_ask": 0.34,
        "down_ask": 0.66,
        "early": {
            "state": early_state,
            "side": "UP" if early_state == "QUALIFIED" else None,
            "ask": 0.34,
            "fair": 0.78,
            "edge": 0.11,
            "seconds_left": left,
        },
        "final": {
            "state": final_state,
            "side": "UP" if final_state in {"QUALIFIED", "LOCK"} else None,
            "fair": 0.94,
            "seconds_left": left,
        },
    }


def scalp(contract="A", state="PASS", *, cid=None, idx=1, terminals=None, fresh=True, ready=True):
    return {
        "version": "GENERALIZED_SCALP_INTEGRATION_V5",
        "contract": contract,
        "orders": False,
        "manual_execution_only": True,
        "order_action": None,
        "lifecycle_ended_unarmed_is_actionable_exit": False,
        "armed_no_exit_reset_allowed": False,
        "source_fresh": fresh,
        "integration_ready": ready,
        "state": state,
        "candidate_id": cid,
        "opportunity_index": idx,
        "side": "DOWN" if cid else None,
        "entry_price": 0.41 if cid else None,
        "current_bid": 0.47 if cid else None,
        "exec_gain": 0.06 if cid else None,
        "peak_exec_gain": 0.08 if cid else None,
        "entry_seconds_left": 820.0 if cid else None,
        "terminal_history": list(terminals or []),
    }


class CombinedForwardV2Tests(unittest.TestCase):
    def setUp(self):
        v2.reset_state_for_tests()

    def _startup(self):
        v2.observer_cycle(combined("A", 300), scalp("A"), observed_at=NOW)

    def test_main_rollover_captured_before_scalp_alignment(self):
        self._startup()
        v2.observer_cycle(combined("B", 899.0, early_state="QUALIFIED"), scalp("A"), observed_at=NOW)
        rec = v2.STATE["records"]["B"]
        self.assertTrue(rec["full_observation_eligible"])
        self.assertAlmostEqual(rec["first_seen_lag_sec"], 1.0)
        self.assertEqual(rec["early"]["state"], "QUALIFIED")
        self.assertEqual(rec["scalps"], [])
        self.assertFalse(rec["scalp_alignment_seen"])

    def test_scalp_can_catch_up_later_without_losing_early(self):
        self._startup()
        v2.observer_cycle(combined("B", 899.0, early_state="QUALIFIED"), scalp("A"), observed_at=NOW)
        v2.observer_cycle(combined("B", 870.0, early_state="QUALIFIED"), scalp("B", "ACTIVE", cid="b1"), observed_at=NOW)
        rec = v2.STATE["records"]["B"]
        self.assertEqual(rec["early"]["side"], "UP")
        self.assertTrue(rec["scalp_alignment_seen"])
        self.assertEqual(len(rec["scalps"]), 1)
        self.assertEqual(rec["scalps"][0]["candidate_id"], "b1")

    def test_late_first_seen_contract_is_excluded_from_gate(self):
        self._startup()
        v2.observer_cycle(combined("B", 890.0, early_state="QUALIFIED"), scalp("A"), observed_at=NOW)
        s = v2.summarize_state()
        self.assertEqual(s["diagnostic_seen_contracts"], 1)
        self.assertEqual(s["contracts"], 0)
        self.assertEqual(s["excluded_late_start_n"], 1)
        self.assertIn("B", s["excluded_late_start_contracts"])
        self.assertFalse(s["sample_ready"])

    def test_two_serial_scalps_still_one_union_contract(self):
        self._startup()
        v2.observer_cycle(combined("B", 899.5), scalp("A"), observed_at=NOW)
        terminals = [
            {"candidate_id": "b1", "opportunity_index": 1, "terminal_state": "EXIT", "actionable_exit": True,
             "side": "UP", "entry_price": 0.31, "exit_gain": 0.08, "peak_exec_gain": 0.12},
            {"candidate_id": "b2", "opportunity_index": 2, "terminal_state": "ENDED_UNARMED", "actionable_exit": False,
             "side": "DOWN", "entry_price": 0.44, "peak_exec_gain": 0.03, "adverse_exec_gain": -0.06},
        ]
        v2.observer_cycle(combined("B", 700.0), scalp("B", terminals=terminals), observed_at=NOW)
        s = v2.summarize_state()
        self.assertEqual(s["contracts"], 1)
        self.assertEqual(s["scalp_contracts"], 1)
        self.assertEqual(s["scalp"]["opportunities"], 2)
        self.assertEqual(s["union_actionable_contracts"], 1)
        self.assertEqual(s["scalp"]["ended_unarmed_n"], 1)
        self.assertTrue(s["scalp"]["ended_unarmed_non_actionable_exit_invariant"])

    def test_early_final_and_scalp_share_one_contract_record(self):
        self._startup()
        v2.observer_cycle(combined("B", 899.0, early_state="QUALIFIED"), scalp("A"), observed_at=NOW)
        v2.observer_cycle(combined("B", 600.0, early_state="QUALIFIED", final_state="LOCK"), scalp("B", "ACTIVE", cid="b1"), observed_at=NOW)
        v2.STATE["records"]["B"]["official_side"] = "UP"
        s = v2.summarize_state()
        self.assertEqual(s["early_contracts"], 1)
        self.assertEqual(s["scalp_contracts"], 1)
        self.assertEqual(s["final_contracts"], 1)
        self.assertEqual(s["union_actionable_contracts"], 1)
        self.assertEqual(s["early"]["accuracy"], 1.0)
        self.assertEqual(s["final"]["accuracy"], 1.0)

    def test_actionable_ended_unarmed_terminal_is_rejected(self):
        self._startup()
        v2.observer_cycle(combined("B", 899.0), scalp("A"), observed_at=NOW)
        bad_terminal = [{
            "candidate_id": "bad", "opportunity_index": 1,
            "terminal_state": "ENDED_UNARMED", "actionable_exit": True,
            "side": "UP", "entry_price": 0.33, "peak_exec_gain": 0.02,
        }]
        with self.assertRaises(ValueError):
            v2.observer_cycle(combined("B", 850.0), scalp("B", terminals=bad_terminal), observed_at=NOW)

    def test_first_full_contract_is_only_eligible_rollover(self):
        self._startup()
        v2.observer_cycle(combined("B", 890.0), scalp("A"), observed_at=NOW)
        self.assertIsNone(v2.STATE.get("first_full_contract"))
        v2.observer_cycle(combined("C", 899.0), scalp("B"), observed_at=NOW)
        self.assertEqual(v2.STATE.get("first_full_contract"), "C")


if __name__ == "__main__":
    unittest.main()
