#!/usr/bin/env python3
import inspect
import unittest

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V14 as v14
import btc15_combined_dashboard_shadow_v10 as server


class V14ShadowServerTests(unittest.TestCase):
    def test_server_imports_v14_builder(self):
        src = inspect.getsource(server)
        self.assertIn("from BTC15_DASHBOARD_COMBINED_SCALP_UI_V14 import build_dashboard", src)
        self.assertIn("v7.base.build_dashboard = build_dashboard", src)

    def test_server_remains_display_only(self):
        src = inspect.getsource(server)
        self.assertIn("DISPLAY / ACCEPTANCE ONLY", src)
        self.assertIn("NO ORDERS", src)
        for forbidden in ("place_order", "create_order", "submit_order", "orders=True"):
            self.assertNotIn(forbidden, src)

    def test_generated_page_is_v14_and_single_timer(self):
        p = v14.build_dashboard()
        text = p.read_text(encoding="utf-8", errors="replace")
        self.assertIn(v14.MARKER, text)
        self.assertEqual(text.count('id="timerRemaining"'), 1)
        self.assertNotIn('<span>Contract time left</span>', text)
        self.assertIn("canonical_seconds_left", text)

    def test_v6_safety_envelope_and_v13_copy_survive(self):
        p = v14.build_dashboard()
        text = p.read_text(encoding="utf-8", errors="replace")
        for anchor in (
            "BTC15_COMBINED_STATE_BRIDGE_V6",
            "BTC15_COMBINED_SCALP_UI_V13_PLAIN_LANGUAGE",
            "scalp_entry_price_filter_applied===false",
            "scalp_entry_guidance_is_display_only===true",
            "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS",
        ):
            self.assertIn(anchor, text)
        self.assertNotIn("flip_risk_percent", text)


if __name__ == "__main__":
    unittest.main()
