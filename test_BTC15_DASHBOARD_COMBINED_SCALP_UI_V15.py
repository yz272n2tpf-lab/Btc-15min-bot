#!/usr/bin/env python3
import unittest

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V14 as v14
import BTC15_DASHBOARD_COMBINED_SCALP_UI_V15 as v15


class V15ResponsiveCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_path = v14.build_dashboard()
        cls.base = base_path.read_text(encoding="utf-8", errors="replace")
        candidate_path = v15.build_dashboard()
        cls.text = candidate_path.read_text(encoding="utf-8", errors="replace")

    def test_v15_marker_style_script_unique(self):
        self.assertEqual(self.text.count(v15.MARKER), 1)
        self.assertEqual(self.text.count(v15.STYLE_ID), 1)
        self.assertEqual(self.text.count(v15.SCRIPT_ID), 1)

    def test_v14_presentation_stability_survives(self):
        for fragment in (
            v14.MARKER,
            'id="btc15-v14-stability-style"',
            "#btcPrice.data-pulse{animation:none!important;transition:none!important;}",
            "height:2.8em!important",
            "font-variant-numeric:tabular-nums lining-nums!important",
        ):
            self.assertIn(fragment, self.text)

    def test_core_card_markup_is_not_duplicated_or_deleted(self):
        for anchor in v15.CARD_ANCHORS:
            self.assertEqual(self.base.count(anchor), 1, anchor)
            self.assertEqual(self.text.count(anchor), 1, anchor)

    def test_single_canonical_timer_preserved(self):
        self.assertEqual(self.base.count('id="timerRemaining"'), 1)
        self.assertEqual(self.text.count('id="timerRemaining"'), 1)
        self.assertIn("canonical_seconds_left", self.text)

    def test_no_new_network_or_poller(self):
        for primitive in v15.NETWORK_PRIMITIVES:
            self.assertEqual(self.text.count(primitive), self.base.count(primitive), primitive)

    def test_phone_tablet_desktop_layouts_present(self):
        self.assertIn('grid-template-areas:', self.text)
        self.assertIn('"final"\n    "early"\n    "timer"\n    "scalp"', self.text)
        self.assertIn('@media (min-width:768px) and (max-width:1180px)', self.text)
        self.assertIn('"final final"\n      "early timer"\n      "scalp scalp"', self.text)
        self.assertIn('@media (min-width:1181px)', self.text)
        self.assertIn('"final early"\n      "timer scalp"', self.text)

    def test_runtime_dom_guard_matches_real_v14_stack_hierarchy(self):
        for fragment in (
            "guarded-missing-card",
            "guarded-left-stack-drift",
            "guarded-right-stack-drift",
            "guarded-primary-grid-drift",
            "earlyCard.parentElement!==leftStack",
            "scalpCard.parentElement!==rightStack",
            "rightStack.parentElement!==primaryGrid",
        ):
            self.assertIn(fragment, self.text)

    def test_existing_stack_nodes_are_reused_not_recreated(self):
        self.assertIn("primaryGrid.classList.add('v15-primary-grid')", self.text)
        self.assertIn("leftStack.classList.add('v15-left-stack')", self.text)
        self.assertIn("rightStack.classList.add('v15-right-stack')", self.text)
        self.assertIn("FINAL_EARLY_TIMER_SCALP", self.text)
        self.assertNotIn("document.createElement('section')", self.text)
        self.assertNotIn("appendChild(card)", self.text)

    def test_no_position_and_safety_wording_survive(self):
        for phrase in (
            "TRACKING ONLY · DON'T CHASE",
            "TRACKING ONLY · NO POSITION ASSUMED",
            "scalp_entry_price_filter_applied===false",
            "scalp_entry_guidance_is_display_only===true",
            "scalp_completed_display_actionable===false",
            "scalp_ended_unarmed_is_actionable_exit===false",
            "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS",
        ):
            self.assertIn(phrase, self.text)

    def test_numeric_flip_risk_remains_hidden(self):
        self.assertNotIn("flip_risk_percent", self.text)

    def test_v15_patch_is_idempotent(self):
        path = v15.build_dashboard()
        again = path.read_text(encoding="utf-8", errors="replace")
        self.assertEqual(again.count(v15.MARKER), 1)
        self.assertEqual(again.count(v15.STYLE_ID), 1)
        self.assertEqual(again.count(v15.SCRIPT_ID), 1)


if __name__ == "__main__":
    unittest.main()
