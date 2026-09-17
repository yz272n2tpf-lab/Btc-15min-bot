import unittest
from unittest.mock import patch

from integrity_sentinel.runtime_v1 import validate_source_url, load_sources


class RuntimeSafetyTests(unittest.TestCase):
    def test_accepts_railway_https(self):
        self.assertEqual(
            validate_source_url("https://example-production.up.railway.app/state"),
            "https://example-production.up.railway.app/state",
        )

    def test_rejects_direct_kalshi(self):
        with self.assertRaises(ValueError):
            validate_source_url("https://external-api.kalshi.com/trade-api/v2/markets")

    def test_rejects_coinbase(self):
        with self.assertRaises(ValueError):
            validate_source_url("https://api.exchange.coinbase.com/products/BTC-USD/ticker")

    def test_rejects_http(self):
        with self.assertRaises(ValueError):
            validate_source_url("http://x.up.railway.app/state")

    def test_default_source_inventory_has_telemetry_and_membership(self):
        with patch.dict("os.environ", {}, clear=True):
            rows = load_sources()
        self.assertEqual({x.kind for x in rows}, {"telemetry", "membership"})
        self.assertTrue(all(x.url.startswith("https://") for x in rows))


if __name__ == "__main__":
    unittest.main()
