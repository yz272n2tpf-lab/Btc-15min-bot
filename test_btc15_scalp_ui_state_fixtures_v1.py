#!/usr/bin/env python3
import unittest

from btc15_scalp_ui_state_fixtures_v1 import FIXTURES


class ScalpUIStateFixtureV1Tests(unittest.TestCase):
    def test_fixture_set_is_complete(self):
        self.assertEqual(
            set(FIXTURES),
            {
                "WAIT",
                "ACTIVE_IDEAL",
                "ACTIVE_CAUTION_ABOVE_50",
                "PROTECT_PULLBACK",
                "EXIT",
                "SCANNING_NEXT",
                "STALE_FAIL_CLOSED",
            },
        )

    def test_expected_display_states(self):
        self.assertEqual(FIXTURES["WAIT"]["display_state"], "WAIT")
        self.assertEqual(FIXTURES["ACTIVE_IDEAL"]["display_state"], "ACTIVE")
        self.assertEqual(FIXTURES["ACTIVE_CAUTION_ABOVE_50"]["display_state"], "ACTIVE")
        self.assertEqual(FIXTURES["PROTECT_PULLBACK"]["display_state"], "PROTECT")
        self.assertEqual(FIXTURES["EXIT"]["display_state"], "EXIT")
        self.assertEqual(FIXTURES["SCANNING_NEXT"]["display_state"], "WAIT")
        self.assertEqual(FIXTURES["STALE_FAIL_CLOSED"]["display_state"], "WAIT")

    def test_entry_guidance_states(self):
        self.assertEqual(FIXTURES["ACTIVE_IDEAL"]["entry_guidance"]["tier"], "IDEAL_25_35")
        self.assertEqual(
            FIXTURES["ACTIVE_CAUTION_ABOVE_50"]["entry_guidance"]["tier"],
            "CAUTION_ABOVE_50",
        )
        self.assertEqual(FIXTURES["ACTIVE_CAUTION_ABOVE_50"]["lifecycle_state"], "ACTIVE")

    def test_serial_context_states(self):
        self.assertEqual(FIXTURES["PROTECT_PULLBACK"]["opportunity_index"], 2)
        self.assertEqual(FIXTURES["PROTECT_PULLBACK"]["serial_opportunities_completed"], 1)
        self.assertTrue(FIXTURES["SCANNING_NEXT"]["scanning_for_next"])
        self.assertEqual(FIXTURES["SCANNING_NEXT"]["serial_opportunities_completed"], 2)

    def test_safety_and_hidden_research_fields_hold_for_every_fixture(self):
        for name, fixture in FIXTURES.items():
            with self.subTest(name=name):
                self.assertTrue(fixture["manual_execution_only"])
                self.assertFalse(fixture["orders"])
                self.assertIsNone(fixture["order_action"])
                self.assertFalse(fixture["watch_warning"]["visible"])
                self.assertFalse(fixture["watch_warning"]["certified"])
                self.assertFalse(fixture["numeric_flip_risk"]["visible"])
                self.assertIsNone(fixture["numeric_flip_risk"]["value"])

    def test_stale_fixture_is_explicitly_fail_closed(self):
        x = FIXTURES["STALE_FAIL_CLOSED"]
        self.assertTrue(x["source"]["fail_closed"])
        self.assertFalse(x["source"]["app_ready"])


if __name__ == "__main__":
    unittest.main()
