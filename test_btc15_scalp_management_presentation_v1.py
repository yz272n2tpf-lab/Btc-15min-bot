#!/usr/bin/env python3
import unittest

from btc15_scalp_management_presentation_v1 import management_presentation


class ScalpManagementPresentationTests(unittest.TestCase):
    def test_before_arm_is_active(self):
        x = management_presentation(state="ACTIVE", peak_exec_gain=.04, exec_gain=.04)
        self.assertEqual(x.state, "ACTIVE")
        self.assertEqual(x.message, "SCALP ACTIVE · BUILDING")
        self.assertFalse(x.protection_armed)

    def test_arm_at_five_cents_is_visible_before_pullback(self):
        x = management_presentation(state="PROTECT", peak_exec_gain=.05, exec_gain=.05)
        self.assertEqual(x.state, "PROTECT")
        self.assertEqual(x.message, "PROTECTION ARMED · WINNER RUNNING")
        self.assertTrue(x.protection_armed)
        self.assertFalse(x.pullback_detected)
        self.assertFalse(x.exit_now)

    def test_large_winner_at_peak_stays_running_with_protection_armed(self):
        x = management_presentation(state="PROTECT", peak_exec_gain=.21, exec_gain=.21)
        self.assertEqual(x.message, "PROTECTION ARMED · WINNER RUNNING")
        self.assertFalse(x.pullback_detected)

    def test_first_observed_pullback_warns_before_four_cent_exit(self):
        x = management_presentation(state="PROTECT", peak_exec_gain=.21, exec_gain=.20)
        self.assertEqual(x.state, "PROTECT")
        self.assertEqual(x.message, "PROTECT PROFITS · PULLBACK DETECTED")
        self.assertTrue(x.pullback_detected)
        self.assertFalse(x.exit_now)
        self.assertAlmostEqual(x.giveback_from_peak, .01)

    def test_three_cent_pullback_still_warns_but_not_exit(self):
        x = management_presentation(state="PROTECT", peak_exec_gain=.21, exec_gain=.18)
        self.assertEqual(x.message, "PROTECT PROFITS · PULLBACK DETECTED")
        self.assertFalse(x.exit_now)

    def test_four_cent_pullback_is_exit(self):
        x = management_presentation(state="EXIT", peak_exec_gain=.21, exec_gain=.17)
        self.assertEqual(x.state, "EXIT")
        self.assertEqual(x.message, "EXIT / PROTECT PROFITS NOW")
        self.assertTrue(x.exit_now)

    def test_pass_is_nonactionable(self):
        x = management_presentation(state="PASS", peak_exec_gain=None, exec_gain=None)
        self.assertEqual(x.state, "PASS")
        self.assertEqual(x.message, "NO QUALIFIED SCALP")
        self.assertTrue(x.manual_execution_only)


if __name__ == "__main__":
    unittest.main()
