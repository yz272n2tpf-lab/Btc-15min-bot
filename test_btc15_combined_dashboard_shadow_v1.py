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


if __name__ == "__main__":
    unittest.main()
