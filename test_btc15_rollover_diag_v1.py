#!/usr/bin/env python3
import contextlib
import io
import json
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path

import btc15_rollover_diag_v1 as d

UTC = timezone.utc
MAIN = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
QUOTE = Path("btc15_kalshi_quote_provenance_v1.py")
HELPER = Path("btc15_rollover_diag_v1.py")


class RolloverDiagTests(unittest.TestCase):
    def setUp(self):
        d.reset_for_tests()

    def test_quarter_open(self):
        x = datetime(2026, 9, 21, 14, 37, 12, tzinfo=UTC)
        self.assertEqual(d.quarter_open(x), datetime(2026, 9, 21, 14, 30, tzinfo=UTC))

    def test_boundary_after_open(self):
        x = datetime(2026, 9, 21, 14, 30, 29, tzinfo=UTC)
        self.assertEqual(d.rollover_boundary(x), datetime(2026, 9, 21, 14, 30, tzinfo=UTC))

    def test_boundary_before_open(self):
        x = datetime(2026, 9, 21, 14, 44, 58, tzinfo=UTC)
        self.assertEqual(d.rollover_boundary(x), datetime(2026, 9, 21, 14, 45, tzinfo=UTC))

    def test_boundary_outside_window(self):
        x = datetime(2026, 9, 21, 14, 32, 0, tzinfo=UTC)
        self.assertIsNone(d.rollover_boundary(x))

    def test_offset_ms(self):
        op = datetime(2026, 9, 21, 14, 30, 0, tzinfo=UTC)
        x = datetime(2026, 9, 21, 14, 30, 12, 345000, tzinfo=UTC)
        self.assertEqual(d.offset_ms(x, op), 12345.0)

    def test_safe_headers_allowlist(self):
        got = d.safe_headers({
            "Age": "15", "Cache-Control": "public,max-age=15", "ETag": "abc",
            "Authorization": "secret", "KALSHI-ACCESS-SIGNATURE": "secret2",
        })
        self.assertEqual(got["age"], "15")
        self.assertIn("cache-control", got)
        self.assertIn("etag", got)
        self.assertNotIn("authorization", got)
        self.assertNotIn("kalshi-access-signature", got)

    def test_emit_marks_signal_only_and_no_orders(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rec = d.emit("test", "EVENT", at=datetime(2026, 9, 21, 14, 30, 1, tzinfo=UTC))
        self.assertTrue(rec["signal_only"])
        self.assertFalse(rec["orders"])
        payload = json.loads(buf.getvalue().split(" | ", 1)[1])
        self.assertTrue(payload["signal_only"])
        self.assertFalse(payload["orders"])

    def test_emit_has_open_offset(self):
        op = datetime(2026, 9, 21, 14, 30, 0, tzinfo=UTC)
        rec = d.emit("test", "EVENT", at=datetime(2026, 9, 21, 14, 30, 2, tzinfo=UTC),
                     expected_open=op)
        self.assertEqual(rec["ms_from_open"], 2000.0)

    def test_emit_deduplicates_identical_transition(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            first = d.emit("test", "WAIT", details={"state": "x"}, dedupe_key="k")
            second = d.emit("test", "WAIT", details={"state": "x"}, dedupe_key="k")
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(buf.getvalue().count(d.PREFIX), 1)

    def test_emit_allows_changed_transition(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            d.emit("test", "STATE", details={"state": "x"}, dedupe_key="k")
            d.emit("test", "STATE", details={"state": "y"}, dedupe_key="k")
        self.assertEqual(buf.getvalue().count(d.PREFIX), 2)

    def test_main_poll_cadence_unchanged(self):
        text = MAIN.read_text()
        self.assertIn("POLL_SECONDS = 5", text)
        self.assertIn('print("NO ACTIVE KXBTC15M CONTRACT — retrying...")\n            time.sleep(POLL_SECONDS)', text)
        self.assertIn('print("KALSHI QUOTE WAIT | timestamped contiguous evidence unavailable | NO ORDERS", flush=True)\n                time.sleep(POLL_SECONDS)', text)

    def test_runtime_market_discovery_is_instrumented(self):
        text = MAIN.read_text()
        runtime = text.rsplit("def kalshi_get(path, params=None):", 1)[1]
        runtime = runtime.split("def parse_dt(value):", 1)[0]
        self.assertIn('"main.market_discovery", "MARKET_LIST_RESPONSE"', runtime)
        self.assertIn('"safe_cache_headers": rollover_diag.safe_headers(r.headers)', runtime)
        self.assertIn('"expected_open_present": bool(_diag_open)', runtime)
        self.assertIn("return data", runtime)

    def test_rollover_discovery_cache_bypass_is_bounded(self):
        text = MAIN.read_text()
        block = text.split("def get_active_market():", 1)[1].split("def extract_target(", 1)[0]
        self.assertIn('if _rollover_boundary is not None and now >= _rollover_boundary:', block)
        self.assertIn('_discovery_params["_btc15_rollover_probe"]', block)
        self.assertIn('"status":"open"', block)
        self.assertIn('"series_ticker":"KXBTC15M"', block)
        self.assertIn('"limit":1000', block)

    def test_active_market_selection_predicate_unchanged(self):
        text = MAIN.read_text()
        self.assertIn("and op <= now < cl", text)
        self.assertIn('_discovery_params = {"status":"open","series_ticker":"KXBTC15M","limit":1000}', text)
        self.assertIn('return _selected', text)

    def test_protected_early_thresholds_unchanged(self):
        text = MAIN.read_text()
        required = [
            "float(_opportunity_ask) <= 0.45",
            "float(_opportunity_model_prob) >= 0.75",
            "float(_opportunity_edge) >= 0.08",
            "2.0 <= float(_entry_time_left) <= 10.0",
            "float(_entry_abs_gap) >= 25.0",
        ]
        for token in required:
            self.assertIn(token, text)

    def test_quote_provider_new_ticker_still_returns_none(self):
        text = QUOTE.read_text()
        block = re.search(r"if ticker != self\.ticker:(.*?)if self\.book is None:", text, re.S)
        self.assertIsNotNone(block)
        self.assertIn("return None", block.group(1))

    def test_instrumentation_contains_no_order_action(self):
        helper = HELPER.read_text().lower()
        self.assertNotIn("/orders", helper)
        self.assertNotIn("create_order", helper)
        self.assertNotIn("place_order", helper)
        self.assertIn('"orders": False', HELPER.read_text())


if __name__ == "__main__":
    unittest.main()
