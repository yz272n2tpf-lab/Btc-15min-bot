#!/usr/bin/env python3
import unittest

from btc15_combined_live_smoke_monitor_v2 import _unwrap_state


class CombinedLiveSmokeMonitorV2Tests(unittest.TestCase):
    def test_direct_dashboard_object(self):
        d = {"contract": "KXBTC15M-X", "time_left_min": 5}
        self.assertIs(_unwrap_state(d), d)

    def test_state_envelope(self):
        d = {"state": {"contract": "KXBTC15M-X"}}
        self.assertEqual(_unwrap_state(d)["contract"], "KXBTC15M-X")

    def test_data_envelope(self):
        d = {"data": {"contract": "KXBTC15M-X"}}
        self.assertEqual(_unwrap_state(d)["contract"], "KXBTC15M-X")

    def test_unknown_envelope_fails_closed(self):
        with self.assertRaises(ValueError):
            _unwrap_state({"payload": {"contract": "KXBTC15M-X"}})

    def test_non_object_fails_closed(self):
        with self.assertRaises(ValueError):
            _unwrap_state([{"contract": "KXBTC15M-X"}])


if __name__ == "__main__":
    unittest.main()
