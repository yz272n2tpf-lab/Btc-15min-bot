#!/usr/bin/env python3
import unittest

from btc15_dashboard_reason_slot_guard_v1 import normalize_reason, reason_slot


class DashboardReasonSlotGuardV1Tests(unittest.TestCase):
    def test_collapses_whitespace_and_newlines(self):
        self.assertEqual(
            normalize_reason(" Momentum   and\n price   distance agree. "),
            "Momentum and price distance agree.",
        )

    def test_short_reason_is_unchanged(self):
        x = reason_slot("Momentum and price distance agree.")
        self.assertEqual(x.visible_text, x.detail_text)
        self.assertFalse(x.truncated)
        self.assertEqual(x.max_lines, 2)
        self.assertTrue(x.fixed_slot)

    def test_long_reason_is_capped_but_full_detail_preserved(self):
        text = (
            "Momentum and price distance agree, but cross-source confirmation is still developing "
            "and the current Kalshi entry has already become expensive for a new manual entry."
        )
        x = reason_slot(text, max_chars=88)
        self.assertLessEqual(len(x.visible_text), 88)
        self.assertTrue(x.visible_text.endswith("…"))
        self.assertEqual(x.detail_text, text)
        self.assertTrue(x.truncated)

    def test_truncates_at_word_boundary_when_practical(self):
        x = reason_slot("one two three four five six seven eight nine ten eleven twelve", max_chars=30)
        self.assertTrue(x.visible_text.endswith("…"))
        self.assertFalse(x.visible_text.endswith("e…"))

    def test_blank_reason_gets_stable_default(self):
        x = reason_slot("   \n ")
        self.assertEqual(x.visible_text, "Waiting for validated evidence.")
        self.assertEqual(x.detail_text, "Waiting for validated evidence.")
        self.assertFalse(x.truncated)

    def test_invalid_max_chars_fails_closed(self):
        with self.assertRaises(ValueError):
            reason_slot("x", max_chars=0)


if __name__ == "__main__":
    unittest.main()
