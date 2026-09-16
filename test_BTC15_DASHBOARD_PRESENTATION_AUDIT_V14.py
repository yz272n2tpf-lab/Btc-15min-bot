#!/usr/bin/env python3
import inspect
import unittest

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V14 as v14


class V14PresentationOnlyAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = inspect.getsource(v14)

    def test_no_network_client_added(self):
        for forbidden in (
            "import requests", "urllib.request", "httpx", "aiohttp",
            "requests.get(", "requests.post(", "urlopen(",
        ):
            self.assertNotIn(forbidden, self.src)

    def test_no_order_path_added(self):
        for forbidden in (
            "place_order", "create_order", "submit_order", "order_action=",
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

    def test_patch_is_v13_generated_html_only(self):
        self.assertIn("import BTC15_DASHBOARD_COMBINED_SCALP_UI_V13 as v13", self.src)
        self.assertIn("html = v13.build_dashboard()", self.src)
        self.assertIn("patch_v14(html)", self.src)

    def test_numeric_flip_risk_not_added(self):
        self.assertNotIn("flip_risk_percent", self.src)
        self.assertIn("numeric Flip Risk", self.src)

    def test_price_change_is_display_only_exact_anchor(self):
        self.assertIn("price.style.color=record&&!current?'var(--yellow)':'';", self.src)
        self.assertIn("price.style.color='';", self.src)
        self.assertIn("presentation", self.src.lower())


if __name__ == "__main__":
    unittest.main()
