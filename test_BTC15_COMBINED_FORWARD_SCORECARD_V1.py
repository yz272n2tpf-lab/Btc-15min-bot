#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

import BTC15_COMBINED_FORWARD_SCORECARD_V1 as m


def combined(contract, *, early=None, final=None, up_ask=.55, down_ask=.46, left=600):
    return {
        "version": "BTC15_COMBINED_STATE_BRIDGE_V6",
        "contract": contract,
        "canonical_seconds_left": left,
        "up_ask": up_ask,
        "down_ask": down_ask,
        "early": early or {"state": "PASS"},
        "final": final or {"state": "WATCH"},
        "orders": False,
        "manual_execution_only": True,
        "order_action": None,
        "numeric_flip_risk_validated": False,
        "scalp_entry_price_filter_applied": False,
    }


def scalp_state(contract, *, state="PASS", cid=None, idx=1, terminal_history=None, entry=.35, peak=.0, left=600):
    return {
        "version": "GENERALIZED_SCALP_INTEGRATION_V5",
        "contract": contract,
        "state": state,
        "candidate_id": cid,
        "opportunity_index": idx,
        "side": "UP" if idx % 2 else "DOWN",
        "entry_price": entry,
        "current_bid": entry + peak,
        "exec_gain": peak,
        "peak_exec_gain": peak,
        "entry_seconds_left": left,
        "terminal_history": terminal_history or [],
        "orders": False,
        "manual_execution_only": True,
        "order_action": None,
        "lifecycle_ended_unarmed_is_actionable_exit": False,
        "armed_no_exit_reset_allowed": False,
    }


def ts(h, minute=0, sec=1):
    return datetime(2026, 9, 15, h, minute, sec, tzinfo=timezone.utc)


class CombinedForwardScorecardV1Tests(unittest.TestCase):
    def setUp(self):
        m.reset_state_for_tests()

    def arm(self):
        # Startup contract is excluded even though process starts after cutoff.
        m.observer_cycle(combined("A"), scalp_state("A"), observed_at=ts(18, 2))
        self.assertFalse(m.STATE["live_scoring_armed"])
        self.assertEqual(m.STATE["startup_contract"], "A")
        self.assertEqual(len(m.STATE["records"]), 0)
        # First rollover after startup is first full counted contract.
        m.observer_cycle(combined("B"), scalp_state("B"), observed_at=ts(18, 15))
        self.assertTrue(m.STATE["live_scoring_armed"])
        self.assertEqual(m.STATE["first_full_contract"], "B")
        self.assertIn("B", m.STATE["records"])

    def test_startup_contract_excluded_and_full_rollover_arms(self):
        self.arm()
        s = m.summarize_state()
        self.assertEqual(s["contracts"], 1)
        self.assertEqual(s["startup_contract_excluded"], "A")
        self.assertFalse(s["partial_start_contract_counted"])

    def test_early_two_serial_scalps_final_is_one_union_contract(self):
        self.arm()
        e = {"state": "QUALIFIED", "side": "UP", "ask": .33, "fair": .80, "edge": .10, "seconds_left": 430}
        m.observer_cycle(combined("B", early=e), scalp_state("B", state="ACTIVE", cid="s1", idx=1, entry=.34, peak=.02, left=420), observed_at=ts(18, 16))

        t1 = {
            "candidate_id": "s1", "opportunity_index": 1, "terminal_state": "EXIT",
            "actionable_exit": True, "side": "UP", "entry_price": .34,
            "exit_gain": .09, "peak_exec_gain": .13, "terminal_time_utc": "2026-09-15T18:17:00Z",
        }
        m.observer_cycle(
            combined("B", early=e),
            scalp_state("B", state="ACTIVE", cid="s2", idx=2, terminal_history=[t1], entry=.41, peak=.03, left=300),
            observed_at=ts(18, 18),
        )

        f = {"state": "LOCK", "side": "UP", "fair": .95, "seconds_left": 270}
        m.observer_cycle(
            combined("B", early=e, final=f, up_ask=.94, down_ask=.07, left=270),
            scalp_state("B", state="ACTIVE", cid="s2", idx=2, terminal_history=[t1], entry=.41, peak=.04, left=300),
            observed_at=ts(18, 18, 30),
        )

        s = m.summarize_state()
        self.assertEqual(s["contracts"], 1)
        self.assertEqual(s["early_contracts"], 1)
        self.assertEqual(s["scalp_contracts"], 1)
        self.assertEqual(s["final_contracts"], 1)
        self.assertEqual(s["scalp"]["opportunities"], 2)
        self.assertEqual(s["scalp"]["multi_scalp_contracts"], 1)
        self.assertEqual(s["union_actionable_contracts"], 1)
        self.assertEqual(s["path_pattern_counts"]["EARLY+SCALP+FINAL"], 1)
        self.assertEqual(s["final"]["avg_ask"], .94)
        self.assertEqual(s["final"]["ask_le_50c_n"], 0)

    def test_ended_unarmed_stays_non_actionable_exit_and_next_scalp_is_preserved(self):
        self.arm()
        u1 = {
            "candidate_id": "u1", "opportunity_index": 1, "terminal_state": "ENDED_UNARMED",
            "actionable_exit": False, "side": "UP", "entry_price": .39,
            "peak_exec_gain": .03, "adverse_exec_gain": -.05,
            "terminal_time_utc": "2026-09-15T18:16:30Z",
        }
        m.observer_cycle(
            combined("B"),
            scalp_state("B", state="ACTIVE", cid="u2", idx=2, terminal_history=[u1], entry=.36, peak=.06),
            observed_at=ts(18, 17),
        )
        s = m.summarize_state()
        self.assertEqual(s["scalp"]["opportunities"], 2)
        self.assertEqual(s["scalp"]["ended_unarmed_n"], 1)
        self.assertEqual(s["scalp"]["protected_exit_n"], 0)
        self.assertTrue(s["scalp"]["ended_unarmed_non_actionable_exit_invariant"])

    def test_contract_mismatch_fails_closed(self):
        with self.assertRaises(ValueError):
            m.observer_cycle(combined("A"), scalp_state("B"), observed_at=ts(18, 1))

    def test_order_capable_payload_fails_closed(self):
        c = combined("A")
        c["orders"] = True
        with self.assertRaises(ValueError):
            m.observer_cycle(c, scalp_state("A"), observed_at=ts(18, 1))

    def test_ended_unarmed_actionable_exit_violation_fails_closed(self):
        self.arm()
        bad = {
            "candidate_id": "bad", "opportunity_index": 1, "terminal_state": "ENDED_UNARMED",
            "actionable_exit": True, "side": "UP", "entry_price": .40,
            "peak_exec_gain": .02,
        }
        with self.assertRaises(ValueError):
            m.observer_cycle(combined("B"), scalp_state("B", terminal_history=[bad]), observed_at=ts(18, 16))

    def test_safety_and_cutoff_are_frozen(self):
        self.assertEqual(m.LIVE_CUTOFF_RAW, "2026-09-15T18:00:00Z")
        self.assertEqual(m.MIN_FULL_CONTRACTS, 30)
        self.assertEqual(m.MIN_SETTLED_CONTRACTS, 25)
        self.arm()
        s = m.summarize_state()
        self.assertFalse(s["orders"])
        self.assertTrue(s["manual_execution_only"])
        self.assertFalse(s["module_thresholds_changed"])
        self.assertFalse(s["production_behavior_changed"])
        self.assertFalse(s["numeric_flip_risk_validated"])


if __name__ == "__main__":
    unittest.main()
