#!/usr/bin/env python3
import unittest

import btc15_scalp_memory_guard_v1 as memory


def model(contract="C1", *, lifecycle="PASS", opp=None, completed=0,
          tracking=False, manual=False, scanning=False):
    return {
        "contract": contract,
        "cards": {
            "SCALP_OPPORTUNITY": {
                "underlying_lifecycle_state": lifecycle,
                "opportunity_index": opp,
                "serial_opportunities_completed": completed,
                "tracking_only": tracking,
                "manual_entry_path_available": manual,
                "scanning_for_next": scanning,
            }
        },
    }


class ScalpMemoryGuardV1Tests(unittest.TestCase):
    def test_protected_exit_is_remembered_when_scanning_next(self):
        prev = model(lifecycle="EXIT", opp=1, completed=1, manual=True)
        cur = model(lifecycle="PASS", opp=None, completed=1, scanning=True)
        d = memory.remember_previous_scalp(prev, cur)
        self.assertTrue(d.same_contract)
        self.assertTrue(d.progression_detected)
        self.assertIsNone(d.blocked_reason)
        self.assertEqual(d.memory["headline"], "#1 COMPLETE · PROTECTED EXIT")
        self.assertIn("scanning for #2", d.memory["detail"].lower())
        self.assertFalse(d.memory["actionable"])

    def test_protected_exit_is_remembered_when_later_opportunity_starts(self):
        prev = model(lifecycle="EXIT", opp=2, completed=2, manual=True)
        cur = model(lifecycle="ACTIVE", opp=3, completed=2, manual=True)
        d = memory.remember_previous_scalp(prev, cur)
        self.assertEqual(d.memory["headline"], "#2 COMPLETE · PROTECTED EXIT")
        self.assertIn("#3", d.memory["detail"])

    def test_unprotected_end_uses_plain_language(self):
        prev = model(lifecycle="ACTIVE", opp=1, completed=0, manual=True)
        cur = model(lifecycle="PASS", opp=None, completed=1, scanning=True)
        d = memory.remember_previous_scalp(prev, cur)
        self.assertEqual(d.memory["headline"], "#1 ENDED · NO PROTECTED EXIT")
        self.assertEqual(d.memory["terminal_kind"], "ENDED_UNPROTECTED")
        self.assertNotIn("ENDED_UNARMED", d.memory["headline"])

    def test_tracking_only_end_never_invents_position(self):
        prev = model(lifecycle="EXIT", opp=1, completed=1, tracking=True, manual=False)
        cur = model(lifecycle="PASS", completed=1, scanning=True)
        d = memory.remember_previous_scalp(prev, cur)
        self.assertEqual(d.memory["headline"], "#1 ENDED · TRACKING ONLY")
        self.assertFalse(d.memory["manual_position_assumed"])
        self.assertIn("no manual position assumed", d.memory["detail"].lower())

    def test_protect_without_real_exit_cannot_be_memorialized_as_complete(self):
        prev = model(lifecycle="PROTECT", opp=2, completed=1, manual=True)
        cur = model(lifecycle="ACTIVE", opp=3, completed=2, manual=True)
        d = memory.remember_previous_scalp(prev, cur)
        self.assertIsNone(d.memory)
        self.assertEqual(d.blocked_reason, "ARMED_NO_EXIT_HANDOFF_BLOCKED")

    def test_no_progression_no_memory(self):
        prev = model(lifecycle="ACTIVE", opp=1, completed=0, manual=True)
        cur = model(lifecycle="ACTIVE", opp=1, completed=0, manual=True)
        d = memory.remember_previous_scalp(prev, cur)
        self.assertFalse(d.progression_detected)
        self.assertIsNone(d.memory)

    def test_contract_rollover_is_not_handled_here(self):
        prev = model("C1", lifecycle="EXIT", opp=1, completed=1, manual=True)
        cur = model("C2", lifecycle="PASS", completed=0)
        d = memory.remember_previous_scalp(prev, cur)
        self.assertFalse(d.same_contract)
        self.assertIsNone(d.memory)
        self.assertIsNone(d.blocked_reason)

    def test_safety_is_non_actionable_and_signal_neutral(self):
        d = memory.remember_previous_scalp(
            model(lifecycle="EXIT", opp=1, completed=1, manual=True),
            model(lifecycle="PASS", completed=1, scanning=True),
        )
        self.assertFalse(d.actionable)
        self.assertFalse(d.signal_filtering)
        self.assertFalse(d.signal_suppression)
        self.assertFalse(d.orders)
        self.assertFalse(d.memory["orders"])
        self.assertIsNone(d.memory["order_action"])


if __name__ == "__main__":
    unittest.main()
