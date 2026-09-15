#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

from scalp_integration_state_bridge_v5 import (
    SOURCE_FRESH_MAX_AGE_SECONDS,
    build_state,
)

NOW = datetime(2026, 9, 15, 4, 0, 0, tzinfo=timezone.utc)
CONTRACT = "KXBTC15M-TEST"


def row(kind, seconds_ago=2, **kw):
    d = datetime.fromtimestamp(NOW.timestamp() - seconds_ago, tz=timezone.utc)
    out = {
        "record_type": kind,
        "timestamp_utc": d.isoformat().replace("+00:00", "Z"),
        "contract": CONTRACT,
    }
    out.update(kw)
    return out


class ScalpIntegrationStateBridgeV5Tests(unittest.TestCase):
    def test_ended_unarmed_hands_off_to_second_scalp(self):
        x = build_state([
            row("SNAPSHOT", 1, seconds_left=300),
            row("CANDIDATE", 120, candidate_id="a", side="UP", seconds_left=420, entry_ask=.31, btc30=20),
            row("PATH", 110, candidate_id="a", elapsed_sec=10, exec_gain=.02),
            row("RESULT", 90, candidate_id="a"),
            row("CANDIDATE", 80, candidate_id="b", side="DOWN", seconds_left=380, entry_ask=.42, btc30=22),
            row("PATH", 70, candidate_id="b", elapsed_sec=10, exec_gain=.03),
        ], now=NOW)
        self.assertEqual(x["state"], "ACTIVE")
        self.assertEqual(x["candidate_id"], "b")
        self.assertEqual(x["opportunity_index"], 2)
        self.assertEqual(x["last_terminal_state"], "ENDED_UNARMED")
        self.assertFalse(x["last_terminal_actionable_exit"])
        self.assertEqual(x["ended_unarmed_count"], 1)
        self.assertFalse(x["lifecycle_ended_unarmed_is_actionable_exit"])
        self.assertTrue(x["source_fresh"])
        self.assertTrue(x["integration_ready"])
        self.assertTrue(x["actionable_for_integration"])

    def test_armed_no_exit_remains_first_protected_scalp_and_blocks_overlap(self):
        x = build_state([
            row("SNAPSHOT", 1, seconds_left=300),
            row("CANDIDATE", 120, candidate_id="a", side="UP", seconds_left=420, entry_ask=.31, btc30=20),
            row("PATH", 110, candidate_id="a", elapsed_sec=10, exec_gain=.06),
            row("PATH", 100, candidate_id="a", elapsed_sec=20, exec_gain=.04),
            row("RESULT", 90, candidate_id="a"),
            row("CANDIDATE", 80, candidate_id="b", side="DOWN", seconds_left=380, entry_ask=.42, btc30=22),
            row("PATH", 70, candidate_id="b", elapsed_sec=10, exec_gain=.20),
        ], now=NOW)
        self.assertEqual(x["candidate_id"], "a")
        self.assertEqual(x["opportunity_index"], 1)
        self.assertEqual(x["state"], "PROTECT")
        self.assertEqual(x["serial_opportunities_completed"], 0)
        self.assertIsNone(x["last_terminal_state"])
        self.assertEqual(x["ended_unarmed_count"], 0)
        self.assertFalse(x["armed_no_exit_reset_allowed"])

    def test_protected_exit_hands_off_to_next_scalp(self):
        x = build_state([
            row("SNAPSHOT", 1, seconds_left=300),
            row("CANDIDATE", 120, candidate_id="a", side="UP", seconds_left=420, entry_ask=.31, btc30=20),
            row("PATH", 110, candidate_id="a", elapsed_sec=10, exec_gain=.06),
            row("PATH", 100, candidate_id="a", elapsed_sec=20, exec_gain=.01),
            row("RESULT", 90, candidate_id="a"),
            row("CANDIDATE", 80, candidate_id="b", side="DOWN", seconds_left=380, entry_ask=.42, btc30=22),
            row("PATH", 70, candidate_id="b", elapsed_sec=10, exec_gain=.02),
        ], now=NOW)
        self.assertEqual(x["candidate_id"], "b")
        self.assertEqual(x["opportunity_index"], 2)
        self.assertEqual(x["last_terminal_state"], "EXIT")
        self.assertTrue(x["last_terminal_actionable_exit"])
        self.assertEqual(x["ended_unarmed_count"], 0)

    def test_ended_unarmed_without_next_candidate_is_pass_scanning(self):
        x = build_state([
            row("SNAPSHOT", 1, seconds_left=300),
            row("CANDIDATE", 120, candidate_id="a", side="UP", seconds_left=420, entry_ask=.31, btc30=20),
            row("PATH", 110, candidate_id="a", elapsed_sec=10, exec_gain=.02),
            row("RESULT", 90, candidate_id="a"),
        ], now=NOW)
        self.assertEqual(x["state"], "PASS")
        self.assertTrue(x["scanning_for_next"])
        self.assertEqual(x["last_terminal_state"], "ENDED_UNARMED")
        self.assertFalse(x["actionable_for_integration"])
        self.assertIn("WATCHING", x["management_message"])

    def test_stale_source_fails_closed_without_rewriting_serial_state(self):
        x = build_state([
            row("SNAPSHOT", 30, seconds_left=300),
            row("CANDIDATE", 30, candidate_id="a", side="UP", seconds_left=420, entry_ask=.31, btc30=20),
        ], now=NOW)
        self.assertEqual(x["state"], "ACTIVE")
        self.assertFalse(x["source_fresh"])
        self.assertFalse(x["integration_ready"])
        self.assertFalse(x["actionable_for_integration"])
        self.assertEqual(x["integration_block_reason"], "SCALP SOURCE STALE")

    def test_safety_envelope_and_frozen_rules_are_preserved(self):
        x = build_state([row("SNAPSHOT", 1, seconds_left=300)], now=NOW)
        self.assertEqual(x["version"], "GENERALIZED_SCALP_INTEGRATION_V5")
        self.assertTrue(x["manual_execution_only"])
        self.assertFalse(x["orders"])
        self.assertIsNone(x["order_action"])
        self.assertFalse(x["numeric_flip_risk_validated"])
        self.assertFalse(x["owns_final_outcome"])
        self.assertFalse(x["owns_early_opportunity"])
        self.assertFalse(x["armed_no_exit_reset_allowed"])
        self.assertIsNone(x["frozen_rule"]["entry_price_filter"])
        self.assertAlmostEqual(float(x["frozen_rule"]["arm_gain"]), .05)
        self.assertAlmostEqual(float(x["frozen_rule"]["giveback"]), .04)
        self.assertEqual(x["canonical_contract_authority"], "MAIN_DASHBOARD")
        self.assertEqual(x["canonical_clock_authority"], "MAIN_DASHBOARD")
        self.assertEqual(x["source_fresh_max_age_sec"], SOURCE_FRESH_MAX_AGE_SECONDS)


if __name__ == "__main__":
    unittest.main()
