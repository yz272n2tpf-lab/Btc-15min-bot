#!/usr/bin/env python3
import inspect
import unittest

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V15 as v15


class V15PresentationOnlyAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = inspect.getsource(v15)

    def test_wraps_v14_only(self):
        self.assertIn("import BTC15_DASHBOARD_COMBINED_SCALP_UI_V14 as v14", self.src)
        self.assertIn("html = v14.build_dashboard()", self.src)
        self.assertIn("patch_v15(html)", self.src)

    def test_no_python_network_client_added(self):
        for forbidden in (
            "import requests", "urllib.request", "httpx", "aiohttp",
            "requests.get(", "requests.post(", "urlopen(",
        ):
            self.assertNotIn(forbidden, self.src)

    def test_v15_javascript_adds_no_network_or_polling(self):
        for forbidden in (
            "fetch(", "XMLHttpRequest", "WebSocket", "EventSource",
            "setInterval(", "setTimeout(",
        ):
            self.assertNotIn(forbidden, v15.V15_JS)

    def test_no_order_path_added(self):
        for forbidden in (
            "place_order", "create_order", "submit_order",
            "manual_execution_only=False", "orders=True",
        ):
            self.assertNotIn(forbidden, self.src)
        self.assertIn("NO ORDERS", self.src)

    def test_no_strategy_threshold_constants_added(self):
        for forbidden in (
            "BTC5_MIN", "BTC15_MIN", "BTC30_FLOOR", "MIN_ACCEL",
            "CONFIRM_COUNT", "CONFIRM_WINDOW", "MIN_LEFT",
            "ARM_GAIN", "GIVEBACK", "FINAL_ELIGIBILITY",
        ):
            self.assertNotIn(forbidden, self.src)

    def test_patch_owns_layout_not_signal_content(self):
        self.assertIn("responsive core layout", self.src.lower())
        self.assertIn("V15 owns layout only", v15.V15_CSS)
        self.assertIn("Frozen semantic order: FINAL, EARLY, canonical TIMER, SCALP", v15.V15_JS)
        self.assertNotIn("innerHTML=", v15.V15_JS)
        self.assertNotIn("textContent=", v15.V15_JS)

    def test_numeric_flip_risk_not_emitted(self):
        self.assertNotIn("flip_risk_percent", v15.V15_CSS)
        self.assertNotIn("flip_risk_percent", v15.V15_JS)

    def test_candidate_is_explicitly_not_production(self):
        self.assertIn("NOT a production deployment", self.src)
        self.assertIn("SHADOW PRESENTATION CANDIDATE ONLY", self.src)


if __name__ == "__main__":
    unittest.main()
