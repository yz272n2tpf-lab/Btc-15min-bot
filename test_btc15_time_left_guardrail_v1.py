#!/usr/bin/env python3
import unittest

import btc15_time_left_guardrail_v1 as g


class TimeLeftGuardrailV1Tests(unittest.TestCase):
    def test_normal_above_five_minutes(self):
        x = g.time_left_guardrail(301)
        self.assertEqual(x.band, "NORMAL")
        self.assertEqual(x.label, "CONTRACT ACTIVE")

    def test_exact_five_minutes_enters_caution(self):
        x = g.time_left_guardrail(300)
        self.assertEqual(x.band, "CAUTION_5M")
        self.assertEqual(x.label, "5M CAUTION")

    def test_exact_three_minutes_enters_guardrail(self):
        x = g.time_left_guardrail(180)
        self.assertEqual(x.band, "GUARD_3M")
        self.assertEqual(x.label, "3M GUARD RAIL")

    def test_zero_is_rollover(self):
        x = g.time_left_guardrail(0)
        self.assertEqual(x.band, "ROLLOVER")
        self.assertEqual(x.label, "NEXT CONTRACT SYNCING")

    def test_unavailable_fails_neutral(self):
        x = g.time_left_guardrail(None)
        self.assertEqual(x.band, "UNAVAILABLE")
        self.assertEqual(x.label, "TIME CHECK")
        self.assertIsNone(x.seconds_left)

    def test_presentation_never_filters_or_changes_rules(self):
        for seconds in (900, 301, 300, 181, 180, 1, 0, None):
            with self.subTest(seconds=seconds):
                x = g.time_left_guardrail(seconds)
                self.assertFalse(x.signal_filtering)
                self.assertFalse(x.signal_suppression)
                self.assertFalse(x.changes_entry_rule)
                self.assertFalse(x.changes_exit_rule)
                self.assertFalse(x.orders)


if __name__ == "__main__":
    unittest.main()
