#!/usr/bin/env python3
import http.client
import json
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer

import btc15_combined_dashboard_shadow_v1 as shadow


class CombinedDashboardShadowV1Tests(unittest.TestCase):
    def setUp(self):
        shadow.DASHBOARD_PATH = Path("BTC_Kalshi_App_Live_v13.html")
        shadow.DASHBOARD_BYTES = b"<html>shadow-dashboard</html>"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), shadow.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def request(self, method, path):
        c = http.client.HTTPConnection(self.host, self.port, timeout=2)
        c.request(method, path)
        r = c.getresponse()
        body = r.read()
        headers = dict(r.getheaders())
        c.close()
        return r.status, headers, body

    def test_health_is_read_only_shadow(self):
        status, headers, body = self.request("GET", "/health")
        self.assertEqual(status, 200)
        d = json.loads(body)
        self.assertTrue(d["ok"])
        self.assertTrue(d["shadow_only"])
        self.assertFalse(d["orders"])
        self.assertTrue(d["generalized_scalp_ui"])
        self.assertTrue(d["combined_state_probe"])
        self.assertEqual(headers.get("Cache-Control"), "no-store")

    def test_root_serves_dashboard(self):
        status, _, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"shadow-dashboard", body)

    def test_write_methods_are_rejected(self):
        status, _, body = self.request("POST", "/")
        self.assertEqual(status, 405)
        d = json.loads(body)
        self.assertFalse(d["orders"])
        self.assertEqual(d["error"], "read_only_shadow")

    def test_unknown_path_fails_closed(self):
        status, _, body = self.request("GET", "/nope")
        self.assertEqual(status, 404)
        self.assertFalse(json.loads(body)["orders"])

    def test_shadow_status_preserves_protected_states(self):
        main = {
            "contract": "KXBTC15M-X",
            "timer": {"seconds_left": 300.0},
            "market": {
                "target": 78000.0,
                "up_bid": 0.33,
                "up_ask": 0.35,
                "down_bid": 0.65,
                "down_ask": 0.67,
            },
            "early": {"ready": True, "side": "UP", "ask": 0.35, "fair": 0.80, "edge": 0.10},
            "final": {
                "ready": False,
                "recorded_final_call": False,
                "side": "UP",
                "confidence": 0.88,
            },
        }
        combined = {
            "version": "BTC15_COMBINED_STATE_BRIDGE_V3",
            "manual_execution_only": True,
            "orders": False,
            "order_action": None,
            "numeric_flip_risk_validated": False,
            "contract": "KXBTC15M-X",
            "canonical_seconds_left": 299.2,
            "early": {"state": "QUALIFIED", "side": "UP", "ask": 0.35, "fair": 0.80, "edge": 0.10},
            "final": {"state": "WATCH", "side": "UP", "fair": None},
            "scalp": {"state": "ACTIVE", "side": "UP"},
            "scalp_contract_aligned": True,
            "scalp_source_fresh": True,
            "scalp_integration_ready": True,
            "scalp_block_reason": None,
            "context_labels": [],
            "scalp_management_message": "SCALP ACTIVE · BUILDING",
        }
        d = shadow.build_shadow_status(main, combined)
        self.assertTrue(d["contract_match"])
        self.assertTrue(d["early_preserved"])
        self.assertTrue(d["final_preserved"])
        self.assertTrue(d["safety_envelope"])
        self.assertTrue(d["actionable_scalp_guarded"])
        self.assertTrue(d["all_safety_checks_pass"])
        self.assertAlmostEqual(d["cross_fetch_timer_delta_sec"], 0.8)

    def test_shadow_status_rejects_unguarded_actionable_scalp(self):
        main = {
            "contract": "KXBTC15M-X",
            "timer": {"seconds_left": 300.0},
            "early": {"ready": False, "side": "UP", "ask": 0.35, "fair": 0.70, "edge": 0.01},
            "final": {"ready": False, "recorded_final_call": False, "side": "UP", "confidence": 0.80},
        }
        combined = {
            "version": "BTC15_COMBINED_STATE_BRIDGE_V3",
            "manual_execution_only": True,
            "orders": False,
            "order_action": None,
            "numeric_flip_risk_validated": False,
            "contract": "KXBTC15M-X",
            "canonical_seconds_left": 300.0,
            "early": {"state": "PASS", "side": "UP", "ask": 0.35, "fair": 0.70, "edge": 0.01},
            "final": {"state": "WATCH", "side": "UP", "fair": None},
            "scalp": {"state": "ACTIVE", "side": "UP"},
            "scalp_contract_aligned": True,
            "scalp_source_fresh": False,
            "scalp_integration_ready": False,
        }
        d = shadow.build_shadow_status(main, combined)
        self.assertFalse(d["actionable_scalp_guarded"])
        self.assertFalse(d["all_safety_checks_pass"])


if __name__ == "__main__":
    unittest.main()
