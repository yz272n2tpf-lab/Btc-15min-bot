"""Offline diagnostics tests: no credentials, network, or order execution."""
import copy
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import btc15_production_state_probe_v1 as probe


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.now = 1789842000.0
        self.data = {
            "contract": "KXBTC15M-26SEP191430-30",
            "source_timestamp_utc": iso(self.now - 1),
            "generated_utc": iso(self.now - 0.5), "source_age_sec": 0.5,
            "timer": {"close_utc": iso(self.now + 600), "seconds_left": 601,
                      "remaining_at_generation_sec": 600.5,
                      "close_basis": "source_timestamp_plus_logged_remaining"},
            "market": {"brti_age_seconds": 0.5},
            "safety": {"read_only": True, "orders_enabled": False}}

    def result(self, data=None, now=None):
        return probe.inspect_state(self.data if data is None else data,
                                   self.now if now is None else now)

    def test_actual_schema_and_separate_clock_bases(self):
        r = self.result()
        self.assertEqual(r["seconds_left_at_source"], 601)
        self.assertEqual(r["seconds_left_now"], 600)
        self.assertEqual(r["brti_age_sec"], 1.5)
        self.assertEqual(r["state_gate"], "PASS")
        self.assertEqual(r["official_kalshi_alignment"], "NOT_CHECKED")
        self.assertFalse(r["cutover_approved"])

    def test_brti_five_second_boundary(self):
        for age, expected in [(4.999, "PASS"), (5.0, "PASS"), (5.001, "WAIT"), (300, "WAIT")]:
            with self.subTest(age=age):
                self.data["market"]["brti_age_seconds"] = age - 1
                self.assertEqual(self.result()["state_gate"], expected)

    def test_fresh_render_does_not_refresh_old_source(self):
        self.data["source_timestamp_utc"] = iso(self.now - 30)
        self.data["source_age_sec"] = 29.5
        self.data["timer"]["seconds_left"] = 630
        r = self.result()
        self.assertEqual(r["state_gate"], "WAIT")
        self.assertEqual(r["brti_age_sec"], 30.5)

    def test_transit_age_is_included(self):
        self.assertEqual(self.result(now=self.now + 4)["state_gate"], "WAIT")

    def test_source_five_second_boundary(self):
        self.data["market"]["brti_age_seconds"] = 0
        self.assertEqual(self.result(now=self.now + 4)["state_gate"], "PASS")
        self.assertEqual(self.result(now=self.now + 4.001)["state_gate"], "WAIT")

    def test_bad_timing_and_safety_fail_closed(self):
        mutations = [
            ("timer", "seconds_left", 800),
            ("timer", "remaining_at_generation_sec", 800),
            ("timer", "close_utc", iso(self.now)),
            ("safety", "orders_enabled", True),
            ("safety", "read_only", "true"),
            ("market", "brti_age_seconds", -1)]
        for group, key, value in mutations:
            with self.subTest(group=group, key=key):
                data = copy.deepcopy(self.data)
                data[group][key] = value
                self.assertEqual(self.result(data)["state_gate"], "WAIT")

    def test_future_and_inconsistent_age_fail_closed(self):
        self.assertEqual(self.result(now=self.now - 2)["state_gate"], "WAIT")
        self.data["source_age_sec"] = 0
        self.assertEqual(self.result()["state_gate"], "WAIT")

    def test_missing_and_nonfinite_fields_rejected(self):
        for value in [None, float("nan"), float("inf"), True]:
            with self.subTest(value=value):
                self.data["timer"]["seconds_left"] = value
                with self.assertRaises((ValueError, TypeError)):
                    self.result()
        del self.data["source_timestamp_utc"]
        with self.assertRaises(KeyError):
            self.result()

    def test_url_normalization(self):
        expected = "https://example.up.railway.app/dashboard_state.json"
        for base in ["example.up.railway.app", "https://example.up.railway.app/\n"]:
            self.assertEqual(probe.state_url(base), expected)
        for base in ["https://exam\nple.app", "http://example.app", "https://a:b@example.app"]:
            with self.assertRaises(ValueError):
                probe.state_url(base)

    def test_network_failure_is_wait(self):
        with patch.dict("os.environ", {"BTC15_PRODUCTION_STATE_BASE": "example.app"}), \
                patch("urllib.request.urlopen", side_effect=TimeoutError), \
                patch("builtins.print") as output:
            self.assertEqual(probe.main(), 2)
            self.assertIn('"state_gate":"WAIT"', output.call_args.args[0])

    def test_parent_log_limit(self):
        import json
        self.assertLess(len(json.dumps(self.result())) + 50, 1500)

    def test_official_market_alignment(self):
        m = {"ticker": self.data["contract"], "open_time": iso(self.now - 300),
             "close_time": iso(self.now + 600)}
        r = probe.inspect_alignment(self.data, m, self.now)
        self.assertEqual(r["official_kalshi_alignment"], "PASS")
        for key, value in [("ticker", "KXBTC15M-OTHER"),
                           ("open_time", iso(self.now - 600)),
                           ("close_time", iso(self.now + 599))]:
            with self.subTest(key=key):
                wrong = dict(m, **{key: value})
                r = probe.inspect_alignment(self.data, wrong, self.now)
                self.assertEqual(r["official_kalshi_alignment"], "WAIT")
        r = probe.inspect_alignment(self.data, m, self.now + 600)
        self.assertEqual(r["official_kalshi_alignment"], "WAIT")

    def test_metadata_failure_prevents_overall_pass(self):
        import io
        import json
        with patch.dict("os.environ", {"BTC15_PRODUCTION_STATE_BASE": "example.app"}), \
                patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(self.data).encode())), \
                patch.object(probe, "datetime", wraps=datetime) as clock, \
                patch.object(probe, "official_market", side_effect=TimeoutError), \
                patch("builtins.print") as output:
            clock.now.return_value = datetime.fromtimestamp(self.now, timezone.utc)
            self.assertEqual(probe.main(), 2)
            self.assertIn('"official_kalshi_alignment":"WAIT"', output.call_args.args[0])
            self.assertIn('"probe_gate":"WAIT"', output.call_args.args[0])

    def test_full_success_and_log_budget(self):
        import io
        import json
        m = {"ticker": self.data["contract"], "open_time": iso(self.now - 300),
             "close_time": iso(self.now + 600)}
        with patch.dict("os.environ", {"BTC15_PRODUCTION_STATE_BASE": "example.app"}), \
                patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(self.data).encode())), \
                patch.object(probe, "datetime", wraps=datetime) as clock, \
                patch.object(probe, "official_market", return_value=m), \
                patch("builtins.print") as output:
            clock.now.return_value = datetime.fromtimestamp(self.now, timezone.utc)
            self.assertEqual(probe.main(), 0)
            self.assertIn('"probe_gate":"PASS"', output.call_args.args[0])
            self.assertLess(len(output.call_args.args[0]), 1500)


if __name__ == "__main__":
    unittest.main()
