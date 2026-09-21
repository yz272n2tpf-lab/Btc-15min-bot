#!/usr/bin/env python3
"""Synthetic observer plumbing tests; never use live forward performance."""
import ast
import copy
import inspect
import io
import json
import os
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import BTC15_EARLY_FORWARD_SCORECARD_V2 as m

START = datetime(2026, 9, 21, 4, 0, tzinfo=timezone.utc)


def frame(start, elapsed, ready=False, side="UP", ask=.31, fair=.80, edge=.49):
    source = start + timedelta(seconds=elapsed)
    close = start + timedelta(minutes=15)
    return {"contract": m.ticker_for_close(close), "source_timestamp_utc": m.iso(source),
            "health": {"source_fresh": True},
            "timer": {"seconds_left": 900 - elapsed, "close_utc": m.iso(close)},
            "early": {"ready": ready, "source": "FROZEN_TIER1", "status": "OPPORTUNITY" if ready else "WATCHING",
                      "side": side, "ask": ask, "fair": fair, "edge": edge},
            # Deliberately contradictory irrelevant authorities.
            "market": {"btc_price": 1, "target": 999999},
            "final": {"ready": True, "side": "DOWN", "confidence": .99}}


def evidence(ticker, result="yes", status="finalized"):
    return m.official_evidence({"market": {"ticker": ticker, "result": result, "status": status,
        "settlement_ts": m.iso(START), "is_provisional": False}}, ticker, m.MARKET_BASES[0] + ticker, START)


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.o = m.Observer(START - timedelta(seconds=20), self.events.append)

    def feed(self, elapsed, **kwargs):
        raw = frame(START, elapsed, **kwargs)
        self.o.observe(raw, START + timedelta(seconds=elapsed + 1))
        return raw["contract"]

    def arm(self):
        previous = START - timedelta(minutes=15)
        self.o.observe(frame(previous, 890, ready=True), START - timedelta(seconds=9))
        self.feed(5)

    def advance(self, end, **kwargs):
        current = int((self.o.last_source - START).total_seconds())
        for elapsed in range(current + 5, int(end), 5):
            self.feed(elapsed)
        return self.feed(end, **kwargs)

    def test_startup_contract_never_counts_even_if_ready(self):
        self.feed(300, ready=True)
        self.feed(305, ready=True)
        self.assertFalse(self.o.plumbing()["live_scoring_armed"])
        self.assertFalse(self.o.calls)
        self.assertEqual(self.o.summary()["eligible_contracts"], 0)

    def test_full_rollover_arms_records_exact_start_and_observation_time(self):
        self.arm()
        p = self.o.plumbing()
        self.assertEqual(p["forward_start_utc"], "2026-09-21T04:00:00Z")
        self.assertEqual(p["armed_observed_at_utc"], "2026-09-21T04:00:06Z")
        self.assertEqual(p["first_eligible_contract"], m.ticker_for_close(START + timedelta(minutes=15)))
        self.assertNotEqual(p["first_eligible_contract"], p["startup_contract_excluded"])

    def test_late_rollover_cannot_arm_or_backfill(self):
        previous = START - timedelta(minutes=15)
        self.o.observe(frame(previous, 890), START - timedelta(seconds=9))
        self.feed(200)
        self.assertIsNone(self.o.forward_start)
        self.assertEqual(self.o.summary()["eligible_contracts"], 0)
        self.advance(890)
        next_start = START + timedelta(minutes=15)
        self.o.observe(frame(next_start, 5), next_start + timedelta(seconds=6))
        self.assertEqual(self.o.forward_start, m.iso(next_start))

    def test_stale_excluded_startup_does_not_disqualify_fresh_new_opening(self):
        self.o = m.Observer(START - timedelta(seconds=70), self.events.append)
        previous = START - timedelta(minutes=15)
        self.o.observe(frame(previous, 840), START - timedelta(seconds=59))
        # The excluded preceding contract goes stale; the new one arrives fresh
        # at its opening, as in the live deployment plumbing check.
        self.feed(25)
        self.assertEqual(self.o.forward_start, m.iso(START))
        self.assertEqual(self.o.summary()["eligible_contracts"], 1)
        self.assertFalse(self.o.calls)

    def test_skipped_contract_is_not_treated_as_full_rollover(self):
        self.o = m.Observer(START - timedelta(minutes=20), self.events.append)
        previous = START - timedelta(minutes=30)
        self.o.observe(frame(previous, 890), START - timedelta(minutes=15, seconds=9))
        self.feed(5)
        self.assertIsNone(self.o.forward_start)
        self.assertEqual(self.o.summary()["eligible_contracts"], 0)

    def test_new_process_ignores_bootstrap_and_all_previous_sample(self):
        self.arm()
        ticker = self.advance(300, ready=True)
        self.o.accept_settlement(ticker, evidence(ticker))
        with patch.dict(os.environ, {"EARLY_SCORECARD_BOOTSTRAP": json.dumps(self.o.summary())}):
            fresh = m.Observer(START + timedelta(seconds=310), self.events.append)
        self.assertNotEqual(fresh.run_id, self.o.run_id)
        self.assertFalse(fresh.calls or fresh.settlements or fresh.contracts or fresh.checkpoints)
        fresh.observe(frame(START, 320, ready=True), START + timedelta(seconds=321))
        self.assertEqual(fresh.startup, ticker)
        self.assertIsNone(fresh.forward_start)

    def test_7_to_10_minute_boundaries_inclusive(self):
        for left, expected in [(600, True), (420, True), (600.01, False), (419.99, False)]:
            with self.subTest(left=left):
                self.setUp()
                self.arm()
                ticker = self.advance(900 - left, ready=True)
                self.assertEqual(ticker in self.o.calls, expected)
                self.assertEqual(self.o.first_calls[ticker]["in_7to10m_slice"], expected)

    def test_first_call_immutable_across_side_price_and_ready_changes(self):
        self.arm()
        ticker = self.advance(300, ready=True, side="UP", ask=.31)
        first = copy.deepcopy(self.o.calls[ticker])
        self.feed(305, ready=False)
        self.feed(310, ready=True, side="DOWN", ask=.27)
        self.assertEqual(self.o.calls[ticker], first)

    def test_out_of_slice_first_call_cannot_be_replaced_by_in_slice_call(self):
        self.arm()
        ticker = self.advance(295, ready=True)
        self.feed(300, ready=True, side="DOWN")
        self.assertNotIn(ticker, self.o.calls)
        self.assertEqual(self.o.first_calls[ticker]["side"], "UP")

    def test_first_call_below_7m_stays_out_of_study(self):
        self.arm()
        ticker = self.advance(481, ready=True)
        self.feed(486, ready=True)
        self.assertNotIn(ticker, self.o.calls)

    def test_ready_is_authority_no_rule_recalculation(self):
        self.arm()
        self.advance(300, ready=False, fair=.99, ask=.25, edge=.74)
        self.assertFalse(self.o.calls)
        ticker = self.feed(305, ready=True, fair=.40, ask=.51, edge=-.11)
        # Contradictory synthetic producer values prove no hidden threshold filter.
        self.assertEqual(self.o.calls[ticker]["ask"], .51)

    def test_mapping_uses_early_not_market_or_final_values(self):
        self.arm()
        ticker = self.advance(310, ready=True, ask=.32, fair=.83, edge=.51)
        rec = self.o.calls[ticker]
        self.assertEqual((rec["side"], rec["ask"], rec["fair"], rec["edge"]), ("UP", .32, .83, .51))
        self.assertEqual(rec["seconds_left"], 590)

    def test_duplicate_and_old_source_cannot_change_call_or_current_contract(self):
        self.arm()
        ticker = self.advance(300, ready=True)
        old = copy.deepcopy(self.o.calls)
        self.feed(295, ready=True, side="DOWN")
        self.feed(300, ready=True, side="DOWN")
        self.assertEqual(old, self.o.calls)
        self.assertEqual(self.o.current, ticker)

    def test_stale_source_invalid_metrics_and_missing_schema_fail_closed(self):
        for mutation in (lambda r: r.pop("early"),
                         lambda r: r["early"].update(ask=float("nan")),
                         lambda r: r["early"].update(edge=None),
                         lambda r: r.update(source_timestamp_utc=m.iso(START)),
                         lambda r: r.update(contract="KXBTC15M-WRONG-15"),
                         lambda r: r["early"].update(source="UNPROTECTED")):
            self.setUp()
            self.arm()
            self.advance(295)
            raw = frame(START, 300, ready=True)
            mutation(raw)
            with self.assertRaises((ValueError, KeyError)):
                self.o.observe(raw, START + timedelta(seconds=301))
            self.feed(305, ready=True)
            self.assertFalse(self.o.calls)

    def test_observation_gap_before_call_excluded_without_backfill(self):
        self.arm()
        self.advance(295)
        ticker = self.feed(335, ready=True)
        self.assertNotIn(ticker, self.o.calls)
        self.assertFalse(self.o.contracts[ticker]["eligible"])

    def test_gap_after_call_does_not_remove_call_or_coverage(self):
        self.arm()
        ticker = self.advance(300, ready=True)
        self.feed(450)
        self.assertIn(ticker, self.o.calls)
        self.assertTrue(self.o.contracts[ticker]["eligible"])

    def test_no_call_complete_slice_stays_in_denominator_after_later_gap(self):
        self.arm()
        ticker = self.advance(485)
        self.feed(650)
        self.assertTrue(self.o.contracts[ticker]["eligible"])
        self.assertEqual(self.o.summary()["eligible_contract_coverage"], 0)

    def test_settlement_is_primary_and_descriptive_metrics_separate(self):
        self.arm()
        ticker = self.advance(300, ready=True)
        self.o.accept_settlement(ticker, evidence(ticker, "no"))
        s = self.o.summary()
        self.assertEqual(s["settlement_same_side_rate"], 0)
        self.assertEqual(s["ask_25_35c_rate"], 1)
        self.assertEqual(s["ask_le_50c_rate"], 1)
        self.assertEqual(s["avg_minutes_left"], 10)
        self.assertEqual((s["up_calls"], s["down_calls"]), (1, 0))
        self.assertEqual(s["primary_success_definition"], "EARLY_SIDE_EQUALS_OFFICIAL_FINAL_SETTLEMENT_SIDE")

    def test_settlement_not_inferred_from_final_btc_or_price(self):
        self.arm()
        self.advance(300, ready=True)
        self.o.settle_due(START + timedelta(hours=1), lambda *_: (None, "pending"))
        self.assertEqual(self.o.summary()["settled_qualifying_calls"], 0)
        self.assertEqual(len(self.o.pending), 1)

    def test_official_exact_ticker_final_status_and_yes_no_required(self):
        ticker = m.ticker_for_close(START)
        url = m.MARKET_BASES[0] + ticker
        for changes in [{"ticker": "wrong"}, {"status": "active"}, {"status": "closed"},
                        {"result": ""}, {"result": "UP"}, {"result": 1}, {"is_provisional": True}]:
            market = {"ticker": ticker, "status": "finalized", "result": "yes", **changes}
            self.assertIsNone(m.official_evidence({"market": market}, ticker, url, START))
        self.assertEqual(evidence(ticker, "no")["official_side"], "DOWN")
        self.assertEqual(evidence(ticker, "yes")["official_side"], "UP")

    def test_settlement_historical_fallback_and_immutable_score(self):
        ticker = m.ticker_for_close(START + timedelta(minutes=15))
        payload = {"market": {"ticker": ticker, "status": "finalized", "result": "yes"}}
        with patch.object(m, "fetch_json", side_effect=[ValueError("not found"), payload]) as fetch:
            found, error = m.fetch_official_settlement(ticker, START)
        self.assertIsNone(error)
        self.assertEqual(fetch.call_args_list[1].args[0], m.MARKET_BASES[1] + ticker)
        self.arm()
        self.advance(300, ready=True)
        self.assertTrue(self.o.accept_settlement(ticker, found))
        self.assertFalse(self.o.accept_settlement(ticker, evidence(ticker, "no")))
        self.assertEqual(self.o.summary()["settlement_same_side_rate"], 1)

    def test_settlement_fetch_errors_remain_pending(self):
        with patch.object(m, "fetch_json", side_effect=TimeoutError("timeout")):
            found, error = m.fetch_official_settlement(m.ticker_for_close(START), START)
        self.assertIsNone(found)
        self.assertIn("TimeoutError", error)

    def test_startup_settlement_probe_never_enters_sample(self):
        self.arm()
        self.o.settle_due(START + timedelta(seconds=60), lambda ticker, _: (evidence(ticker), None))
        self.assertTrue(self.o.probe_done)
        self.assertFalse(self.o.calls or self.o.settlements or self.o.checkpoints)
        self.assertTrue(self.o.plumbing()["settlement_probe"]["verified"])

    def test_plumbing_endpoint_contains_no_strategy_performance(self):
        self.arm()
        p = self.o.plumbing()
        self.assertTrue(p["signal_only"])
        self.assertFalse(p["orders"])
        self.assertFalse({"calls", "qualifying_calls", "settlement_same_side_rate", "checkpoints", "avg_ask"} & p.keys())


class GateTests(unittest.TestCase):
    def run_gate(self, n, correct):
        o = m.Observer(START, lambda _: None)
        for i in range(n):
            ticker = m.ticker_for_close(START + timedelta(minutes=15 * i))
            o.calls[ticker] = {"contract": ticker, "side": "UP"}
            o.accept_settlement(ticker, evidence(ticker, "yes" if i < correct else "no"))
        return o

    def test_exact_ten_call_gate(self):
        for correct, decision in [(8, "FAIL_7TO10M_CLAIM"), (9, "CONTINUE_UNCHANGED_TO_15"), (10, "CONTINUE_UNCHANGED_TO_15")]:
            self.assertEqual(self.run_gate(10, correct).checkpoints["10"]["decision"], decision)

    def test_exact_fifteen_call_gate(self):
        for correct, decision in [(13, "FAIL_TARGET"), (14, "PROVISIONAL_SUPPORT_93_TO_95_TARGET"), (15, "PROVISIONAL_SUPPORT_93_TO_95_TARGET")]:
            o = self.run_gate(15, correct)
            self.assertEqual(o.checkpoints["15"]["decision"], decision)
            self.assertAlmostEqual(o.checkpoints["15"]["same_side_rate"], correct / 15)

    def test_settlement_response_order_cannot_select_checkpoint_cohort(self):
        o = m.Observer(START, lambda _: None)
        tickers = [m.ticker_for_close(START + timedelta(minutes=15*i)) for i in range(11)]
        for ticker in tickers:
            o.calls[ticker] = {"contract": ticker, "side": "UP"}
        for ticker in tickers[1:]:
            o.accept_settlement(ticker, evidence(ticker))
        self.assertNotIn("10", o.checkpoints)
        o.accept_settlement(tickers[0], evidence(tickers[0], "no"))
        self.assertEqual(o.checkpoints["10"]["correct"], 9)


class SafetyTests(unittest.TestCase):
    def test_transport_only_gets_allowlisted_source_and_official_markets(self):
        ticker = m.ticker_for_close(START)
        urls = [m.MAIN_STATE_URL, *(base+ticker for base in m.MARKET_BASES)]
        for url in urls:
            response = io.StringIO('{"ok":true}')
            response.geturl = lambda: url
            with patch.object(m, "urlopen", return_value=response) as network:
                m.fetch_json(url)
            request = network.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertIsNone(request.data)
        for url in ["https://external-api.kalshi.com/trade-api/v2/portfolio/orders", "https://example.com", m.MARKET_BASES[0]+"../portfolio/orders"]:
            with patch.object(m, "urlopen") as network:
                with self.assertRaises(ValueError):
                    m.fetch_json(url)
                network.assert_not_called()

    def test_no_production_module_or_order_client_imported(self):
        tree = ast.parse(inspect.getsource(m))
        imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("bot" == alias.name or "kalshi" in alias.name for n in imports for alias in n.names))
        self.assertNotIn("BTC15_EARLY_FORWARD_SCORECARD_V1", inspect.getsource(m))

    def test_http_writes_rejected_without_state_change(self):
        o = m.Observer(START, lambda _: None)
        with patch.object(m, "OBSERVER", o):
            server = ThreadingHTTPServer(("127.0.0.1", 0), m.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for method in ["POST", "PUT", "PATCH", "DELETE"]:
                    req = Request(f"http://127.0.0.1:{server.server_port}/state", method=method)
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(req)
                    self.assertEqual(caught.exception.code, 405)
                    self.assertFalse(json.load(caught.exception)["orders"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
        self.assertFalse(o.contracts or o.calls or o.settlements)


if __name__ == "__main__":
    unittest.main()
