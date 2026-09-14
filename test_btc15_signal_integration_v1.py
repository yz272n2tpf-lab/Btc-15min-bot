#!/usr/bin/env python3
import unittest

from btc15_signal_integration_v1 import (
    EarlyState,
    FinalState,
    ScalpState,
    compose_contract_state,
)


class IntegrationStateTests(unittest.TestCase):
    def test_watch_and_pass_are_not_actionable(self):
        x = compose_contract_state("T")
        self.assertFalse(x.union_actionable)
        self.assertEqual(x.actionable_paths, ())
        self.assertEqual(x.headline, "FINAL_WATCH")

    def test_early_qualified_is_actionable(self):
        x = compose_contract_state(
            "T",
            early=EarlyState("QUALIFIED", "UP", ask=.34, fair=.78, edge=.10),
        )
        self.assertTrue(x.union_actionable)
        self.assertEqual(x.actionable_paths, ("EARLY",))
        self.assertEqual(x.headline, "EARLY_QUALIFIED")

    def test_final_lock_has_display_priority_over_active_scalp(self):
        x = compose_contract_state(
            "T",
            final=FinalState("LOCK", "UP", fair=.94),
            scalp=ScalpState("ACTIVE", "UP", entry_ask=.71),
        )
        self.assertEqual(x.headline, "FINAL_LOCK")
        self.assertEqual(x.actionable_paths, ("FINAL", "SCALP"))
        self.assertIn("ALIGNED", x.context_labels)

    def test_scalp_exit_has_safety_priority_and_keeps_final_visible(self):
        x = compose_contract_state(
            "T",
            final=FinalState("LOCK", "UP", fair=.93),
            scalp=ScalpState("EXIT", "DOWN", entry_ask=.42, current_bid=.51),
        )
        self.assertEqual(x.headline, "SCALP_EXIT")
        self.assertEqual(x.actionable_paths, ("FINAL", "SCALP"))
        self.assertIn("COUNTERTREND_SCALP", x.context_labels)
        self.assertIn("MIXED_HORIZONS", x.context_labels)

    def test_early_final_divergence_is_explicit(self):
        x = compose_contract_state(
            "T",
            early=EarlyState("QUALIFIED", "DOWN", ask=.31, fair=.77, edge=.09),
            final=FinalState("QUALIFIED", "UP", fair=.91),
        )
        self.assertIn("EARLY_FINAL_DIVERGENCE", x.context_labels)
        self.assertIn("MIXED_HORIZONS", x.context_labels)

    def test_scalp_active_alone_counts_once_for_union(self):
        x = compose_contract_state(
            "T",
            scalp=ScalpState("ACTIVE", "DOWN", entry_ask=.82),
        )
        self.assertTrue(x.union_actionable)
        self.assertEqual(x.actionable_paths, ("SCALP",))
        self.assertEqual(x.headline, "SCALP_ACTIVE")

    def test_price_does_not_gate_scalp_in_composer(self):
        low = compose_contract_state("L", scalp=ScalpState("ACTIVE", "UP", entry_ask=.05))
        high = compose_contract_state("H", scalp=ScalpState("ACTIVE", "UP", entry_ask=.95))
        self.assertTrue(low.union_actionable)
        self.assertTrue(high.union_actionable)

    def test_qualified_states_require_side(self):
        with self.assertRaises(ValueError):
            compose_contract_state("T", early=EarlyState("QUALIFIED"))
        with self.assertRaises(ValueError):
            compose_contract_state("T", final=FinalState("LOCK"))
        with self.assertRaises(ValueError):
            compose_contract_state("T", scalp=ScalpState("ACTIVE"))

    def test_serialized_payload_has_no_order_or_numeric_flip_risk_value(self):
        x = compose_contract_state("T")
        payload = x.to_dict()
        self.assertTrue(payload["manual_execution_only"])
        self.assertFalse(payload["numeric_flip_risk_validated"])
        self.assertNotIn("order", payload)
        self.assertNotIn("flip_risk_percent", payload)


if __name__ == "__main__":
    unittest.main()
