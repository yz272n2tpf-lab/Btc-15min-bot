#!/usr/bin/env python3
import unittest

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V13 as v13


class V13PlainLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = v13.build_dashboard()
        cls.text = cls.path.read_text(encoding="utf-8", errors="replace")

    def test_plain_language_actions_present(self):
        for phrase in (
            "◉ SCALP OPPORTUNITY",
            "WATCHING FOR SCALP",
            "HOLD · MOVE STILL BUILDING",
            "EXIT NOW · PROTECT PROFITS",
            "TRACKING ONLY · DON'T CHASE",
            "TRACKING ONLY · NO POSITION ASSUMED",
            "CURRENT SELL PRICE",
            "PROFIT NOW",
            "Entry Quality",
            "Profit Protection",
            "WAIT · DATA NOT FRESH",
            "WAIT · SYNCING CONTRACT",
        ):
            self.assertIn(phrase, self.text)

    def test_backend_safety_invariants_survive(self):
        for invariant in (
            "BTC15_COMBINED_STATE_BRIDGE_V6",
            "scalp_ended_unarmed_is_actionable_exit===false",
            "scalp_armed_no_exit_reset_allowed===false",
            "scalp_entry_guidance_is_display_only===true",
            "scalp_entry_price_filter_applied===false",
            "scalp_completed_display_actionable===false",
            "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS",
        ):
            self.assertIn(invariant, self.text)
        self.assertNotIn("flip_risk_percent", self.text)

    def test_backend_jargon_removed_only_from_visible_copy(self):
        for phrase in (
            " ENDED UNARMED · SCANNING ",
            " ended unarmed · reset only ",
            "Prior scalp ended unarmed · lifecycle reset only",
            "Prior ended unarmed · reset only",
            "WAIT · FEED STALE",
            "WAIT · CONTRACT SYNC",
            "SCALP ACTIVE · BUILDING",
            "EXIT / PROTECT PROFITS NOW",
            "MODEL TRACKING ONLY · no manual position assumed",
        ):
            self.assertNotIn(phrase, self.text)

    def test_no_position_tracking_never_becomes_entry_filter(self):
        self.assertIn("currentGuideZone==='TOO_EXPENSIVE'", self.text)
        self.assertIn("scalp_entry_price_filter_applied===false", self.text)
        self.assertIn("TRACKING ONLY · DON'T CHASE", self.text)

    def test_reason_height_is_stable(self):
        self.assertIn("btc15-scalp-v13-language-style", self.text)
        self.assertIn("min-height:2.7em;max-height:2.7em;overflow:hidden", self.text)


if __name__ == "__main__":
    unittest.main()
