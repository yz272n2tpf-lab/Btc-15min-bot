"""Offline live-parity cases; no network, credentials, or orders."""
import copy
import io
import json
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import btc15_kalshi_parity_shadow_gateway_v1 as parity


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


class LiveParityTests(unittest.TestCase):
    def setUp(self):
        self.now = 1789842600.0
        self.data = {
            "contract": "KXBTC15M-26SEP191445-45",
            "source_timestamp_utc": iso(self.now - 1),
            "generated_utc": iso(self.now - .5), "source_age_sec": .5,
            "timer": {"close_utc": iso(self.now + 600), "seconds_left": 601,
                      "remaining_at_generation_sec": 600.5},
            "safety": {"read_only": True, "orders_enabled": False},
            "health": {k: True for k in ("source_fresh", "paired_quotes", "brti_fresh", "market_open")},
            "market": {"brti_age_seconds": 1, "brti_ready": True, "target": 81000,
                       "brti_value": 81020, "brti_gap": 20, "up_bid": .49, "up_ask": .5,
                       "down_bid": .5, "down_ask": .51}}
        self.official = {"ticker": self.data["contract"], "floor_strike": 81000,
                         "open_time": iso(self.now - 300), "close_time": iso(self.now + 600),
                         "yes_bid_dollars": ".49", "yes_ask_dollars": ".50",
                         "no_bid_dollars": ".50", "no_ask_dollars": ".51"}
        self.before = {"owner_epoch": "epoch-1", "sequence": 10,
                       "source_ts_ms": int((self.now - 1) * 1000),
                       "value": 81099, "orders": False, "signal_only": True}
        self.after = dict(self.before)
        self.ring = {"orders": False, "ticks": [
            {"index_id": "BRTI", "owner_epoch": "epoch-1", "sequence": 9,
             "source_ts_ms": int((self.now - 2) * 1000), "value": "81020",
             "orders": False, "signal_only": True},
            {"index_id": "BRTI", "owner_epoch": "epoch-1", "sequence": 10,
             "source_ts_ms": int((self.now - 1) * 1000), "value": "81099",
             "orders": False, "signal_only": True}]}

    def evaluate(self, now=None):
        return parity.evaluate(self.data, self.official, self.before, self.ring,
                               self.after, self.now if now is None else now)

    def test_matches_historical_tick_not_current_price(self):
        r = self.evaluate()
        self.assertEqual(r["status"], "PASS")
        self.assertEqual(r["brti_delta"], 0)
        self.assertEqual(r["match_delta_ms"], 0)
        self.assertFalse(r["cutover_approved"])

    def test_timestamp_tolerance_requires_corresponding_tick(self):
        for shift, expected in [(250, "PASS"), (251, "WAIT")]:
            with self.subTest(shift=shift):
                self.ring["ticks"][0]["source_ts_ms"] = int((self.now - 2) * 1000) + shift
                self.assertEqual(self.evaluate()["status"], expected)

    def test_missing_tick_is_wait(self):
        self.ring["ticks"] = self.ring["ticks"][1:]
        r = self.evaluate()
        self.assertEqual(r["status"], "WAIT")
        self.assertIn("NO_MATCHING_BRTI_TICK", r["reasons"])

    def test_brti_age_boundary(self):
        self.assertEqual(self.evaluate(self.now + 3)["status"], "PASS")
        self.assertEqual(self.evaluate(self.now + 3.001)["status"], "WAIT")

    def test_old_source_not_refreshed_by_generated_time(self):
        self.data["source_timestamp_utc"] = iso(self.now - 300)
        self.data["source_age_sec"] = 299.5
        self.data["timer"]["seconds_left"] = 900
        self.assertEqual(self.evaluate()["status"], "WAIT")

    def test_contract_change_and_expiry_are_wait(self):
        self.official["ticker"] = "KXBTC15M-OTHER"
        self.assertEqual(self.evaluate()["status"], "WAIT")
        self.official["ticker"] = self.data["contract"]
        self.assertEqual(self.evaluate(self.now + 600)["status"], "WAIT")

    def test_gateway_restart_and_sequence_regression_are_wait(self):
        self.after["owner_epoch"] = "epoch-2"
        self.assertEqual(self.evaluate()["status"], "WAIT")
        self.after["owner_epoch"] = "epoch-1"
        self.after["sequence"] = 8
        self.assertEqual(self.evaluate()["status"], "WAIT")

    def test_gateway_stale_future_and_safety_are_wait(self):
        for key, value in [("source_ts_ms", (self.now - 5.001) * 1000),
                           ("source_ts_ms", (self.now + 1) * 1000),
                           ("orders", True), ("signal_only", False)]:
            with self.subTest(key=key, value=value):
                self.after = dict(self.before, **{key: value})
                self.assertEqual(self.evaluate()["status"], "WAIT")

    def test_tick_integrity_rejects_bad_duplicate_and_out_of_order(self):
        original = copy.deepcopy(self.ring)
        for key, value in [("orders", True), ("index_id", "OTHER"), ("value", "NaN"),
                           ("source_ts_ms", self.ring["ticks"][1]["source_ts_ms"]),
                           ("sequence", self.ring["ticks"][1]["sequence"])]:
            with self.subTest(key=key):
                self.ring = copy.deepcopy(original)
                self.ring["ticks"][0][key] = value
                self.assertEqual(self.evaluate()["status"], "WAIT")

    def test_wait_zone_boundaries(self):
        for gap, expected in [(-11.001, "DOWN"), (-11, "WAIT"), (0, "WAIT"),
                              (11, "WAIT"), (11.001, "UP")]:
            self.assertEqual(parity.zone(gap), expected)
        self.data["market"].update(brti_value=81011, brti_gap=11)
        self.ring["ticks"][0]["value"] = "81011.01"
        r = self.evaluate()
        self.assertEqual(r["status"], "FAIL")
        self.assertIn("WAIT_ZONE_OR_DIRECTION", r["reasons"])

    def test_price_and_target_tolerances(self):
        self.ring["ticks"][0]["value"] = "81022"
        self.assertEqual(self.evaluate()["status"], "PASS")
        self.ring["ticks"][0]["value"] = "81022.01"
        self.assertIn("BRTI_VALUE", self.evaluate()["reasons"])
        self.ring["ticks"][0]["value"] = "81020"
        self.official["floor_strike"] = 81002
        self.assertIn("TARGET", self.evaluate()["reasons"])

    def test_quote_units_and_mismatch(self):
        for key in ("yes_bid", "yes_ask", "no_bid", "no_ask"):
            self.official[key] = round(float(self.official.pop(key + "_dollars")) * 100)
        self.assertEqual(self.evaluate()["status"], "PASS")
        self.official["yes_bid"], self.official["yes_ask"] = 70, 71
        self.assertEqual(self.evaluate()["status"], "FAIL")

    def test_invalid_data_cannot_pass(self):
        del self.data["market"]["down_ask"]
        self.assertEqual(self.evaluate()["status"], "WAIT")

    def test_wait_overrides_price_mismatch(self):
        self.data["market"]["brti_ready"] = False
        self.ring["ticks"][0]["value"] = "81999"
        self.assertEqual(self.evaluate()["status"], "WAIT")

    def test_log_fits_parent_limit(self):
        self.assertLess(len("BRTI_LIVE_PARITY | " + json.dumps(self.evaluate()) + " | NO ORDERS"), 1200)

    def test_audit_reads_live_endpoints_and_checks_owner_twice(self):
        client = types.ModuleType("btc15_brti_ws_gateway_client_v1")
        client.state = unittest.mock.Mock(side_effect=[self.before, self.after])
        with patch.dict("sys.modules", {"btc15_brti_ws_gateway_client_v1": client}), \
                patch.dict("os.environ", {"BTC15_PRODUCTION_STATE_BASE": "example.app",
                                         "BTC15_BRTI_GATEWAY_URL": "http://127.0.0.1:8080"}), \
                patch.object(parity, "get_json", side_effect=[self.data, {"market": self.official}, self.ring]) as get, \
                patch.object(parity, "auth_headers", return_value={}), \
                patch("time.time", return_value=self.now):
            self.assertEqual(parity.audit()["status"], "PASS")
            self.assertEqual(client.state.call_count, 2)
            self.assertEqual(get.call_args_list[0].args[0], "https://example.app/dashboard_state.json")
            self.assertIn("/markets/" + self.data["contract"], get.call_args_list[1].args[0])
            self.assertEqual(get.call_args_list[2].args[0], "http://127.0.0.1:8080/ticks")

    def test_transport_is_get_only(self):
        with patch("urllib.request.urlopen", return_value=io.BytesIO(b"{}")) as urlopen:
            parity.get_json("https://example.app", 1)
            self.assertEqual(urlopen.call_args.args[0].get_method(), "GET")

    def test_runtime_failure_exits_wait(self):
        with patch.object(parity, "audit", side_effect=TimeoutError), \
                patch("sys.argv", ["parity", "--once"]), patch("builtins.print") as output:
            self.assertEqual(parity.main(), 2)
            self.assertIn('"status":"WAIT"', output.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
