"""Diagnostic regressions only. No strategy outcomes and no production changes.

V3 repair is BLOCKED: the inspected production stream misses the opening grace.
The timestamps below are runtime collection evidence, not a replayed clean sample.
"""
import copy
import hashlib
import pathlib
import unittest
from datetime import timedelta
from unittest.mock import patch

import BTC15_EARLY_FORWARD_SCORECARD_V2 as m
from test_BTC15_EARLY_FORWARD_SCORECARD_V2 import START, frame, evidence


class SourceBlockerTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.o = m.Observer(START - timedelta(seconds=70), self.events.append)
        self.previous = START - timedelta(minutes=15)
        self.o.observe(frame(self.previous, 850), START - timedelta(seconds=49))

    def feed(self, elapsed, delay=1, **kwargs):
        raw = frame(START, elapsed, **kwargs)
        self.o.observe(raw, START + timedelta(seconds=elapsed + delay))
        return raw["contract"]

    def arm_and_advance(self, end=300, ready=False):
        self.feed(5)
        for elapsed in range(10, end, 5):
            self.feed(elapsed)
        return self.feed(end, ready=ready)

    def test_continuous_opening_and_duplicate_arm_exactly_once(self):
        for elapsed in (5, 5, 10, 15):
            ticker = self.feed(elapsed)
        self.assertTrue(self.o.contracts[ticker]["eligible"])
        self.assertEqual(sum(e["event"] == "FORWARD_ARMED" for e in self.events), 1)
        self.assertEqual(sum(e["event"] == "CONTRACT_OBSERVED" for e in self.events), 2)

    def test_actual_stale_error_in_prior_contract_does_not_poison_new_opening(self):
        stale = frame(self.previous, 850)
        with self.assertRaisesRegex(ValueError, "stale/future"):
            self.o.observe(stale, START - timedelta(seconds=1))
        ticker = self.feed(5)
        self.assertTrue(self.o.contracts[ticker]["eligible"])
        self.assertIsNone(self.o.last_error)

    def test_truly_stale_new_contract_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "stale/future"):
            self.feed(5, delay=31)
        self.assertIsNone(self.o.first_eligible)
        self.assertEqual(len(self.o.contracts), 1)

    def test_material_future_dating_rejected(self):
        with self.assertRaisesRegex(ValueError, "stale/future"):
            self.feed(5, delay=-2.001)
        self.assertIsNone(self.o.first_eligible)

    def test_bounded_clock_skew_and_polling_jitter_pass_without_new_tolerances(self):
        # Producer reports healthy in these fixtures; no override of its health flag.
        for elapsed, delay in ((5, -1.5), (10, 4.8), (15, .2), (20, 3.7)):
            ticker = self.feed(elapsed, delay=delay)
        self.assertTrue(self.o.contracts[ticker]["eligible"])
        self.assertEqual(self.o.poll_successes, 5)
        self.assertEqual((m.MAX_SOURCE_AGE_SEC, m.ROLLOVER_GRACE_SEC), (30, 30))

    def test_duplicates_do_not_count_as_observations_or_duplicate_calls(self):
        ticker = self.arm_and_advance(300, ready=True)
        first = copy.deepcopy(self.o.first_calls)
        successes = self.o.poll_successes
        self.feed(300, delay=4, ready=True, side="DOWN")
        self.assertEqual(self.o.poll_successes, successes)
        self.assertEqual(self.o.first_calls, first)
        self.assertEqual(sum(e["event"] == "FIRST_PROTECTED_EARLY" for e in self.events), 1)
        self.assertEqual(list(self.o.calls), [ticker])

    def test_skipped_contract_not_reconstructed_from_fresh_later_opening(self):
        later = START + timedelta(minutes=15)
        raw = frame(later, 5)
        self.o.observe(raw, later + timedelta(seconds=6))
        self.assertFalse(self.o.contracts[raw["contract"]]["eligible"])
        self.assertNotIn(m.ticker_for_close(later), self.o.contracts)

    def test_three_observed_late_sources_remain_excluded_even_with_zero_http_delay(self):
        # Exact source offsets from 2026-09-21 11:15, 11:30, 11:45 UTC.
        # Removing ALL observer network latency cannot recover an absent opening.
        for elapsed in (53.295141, 48.936398, 34.514139):
            with self.subTest(source_elapsed_seconds=elapsed):
                self.setUp()
                ticker = self.feed(elapsed, delay=0)
                self.assertFalse(self.o.contracts[ticker]["eligible"])
                self.assertEqual(self.o.contracts[ticker]["exclusion_reason"],
                                 "rollover_not_fully_observed")
                self.assertIsNone(self.o.first_eligible)

    def test_restart_excludes_startup_and_cannot_import_earlier_call(self):
        ticker = self.arm_and_advance(300, ready=True)
        restarted = m.Observer(START + timedelta(seconds=301), self.events.append)
        restarted.observe(frame(START, 305, ready=True), START + timedelta(seconds=306))
        self.assertEqual(restarted.startup, ticker)
        self.assertFalse(restarted.calls or restarted.first_calls or restarted.settlements)
        self.assertNotEqual(restarted.run_id, self.o.run_id)

    def test_settlement_for_another_contract_cannot_attach_to_call(self):
        ticker = self.arm_and_advance(300, ready=True)
        wrong = m.ticker_for_close(START + timedelta(minutes=30))
        with self.assertRaisesRegex(ValueError, "invalid official settlement"):
            self.o.accept_settlement(ticker, evidence(wrong))
        self.assertFalse(self.o.settlements)
        self.assertTrue(self.o.accept_settlement(ticker, evidence(ticker)))
        self.assertFalse(self.o.accept_settlement(ticker, evidence(ticker)))

    def test_producer_unfresh_flag_is_not_overridden_by_local_age(self):
        raw = frame(START, 5)
        raw["health"]["source_fresh"] = False
        with self.assertRaisesRegex(ValueError, "production source not fresh"):
            self.o.observe(raw, START + timedelta(seconds=6))
        self.assertIsNone(self.o.first_eligible)

    def test_poll_clock_is_sampled_after_fetch_returns(self):
        raw = frame(START, 5)
        request_start = START - timedelta(seconds=2)
        received = START + timedelta(seconds=6)
        clock = [request_start]

        def fetch(_url):
            clock[0] = received
            return raw

        class EndOnePoll(Exception):
            pass

        with patch.object(m, "fetch_json", side_effect=fetch), \
             patch.object(m, "utcnow", side_effect=lambda: clock[0]), \
             patch.object(m.time, "sleep", side_effect=EndOnePoll):
            with self.assertRaises(EndOnePoll):
                m.poll_loop(self.o)
        self.assertEqual(self.o.last_observed, received)
        self.assertEqual(self.o.first_eligible, raw["contract"])

    def test_observer_and_protected_adapters_are_byte_identical_to_deployed_baseline(self):
        expected = {
            "BTC15_EARLY_FORWARD_SCORECARD_V2.py": "76e4fce4cab1093e27b7cc09f23463d3f1c209e6bd5bb88528e8379b83777dac",
            "btc15_main_protected_state_adapter_v1.py": "47b0e41926d2c70837dbc846efff0ebf567d08fc5d9c0e1ea0fdac0b80d70ab6",
            "btc15_protected_module_adapter_v1.py": "bc98d1cf70f73d5dec9800496db333a8f871df25b8bc0f3b138d6d1a161028a8",
            "btc15_signal_integration_v1.py": "d3cc02b2ff09799bca791f9a4717edd9969d08a4bdce9e18c73bc016bec34fb2",
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256(pathlib.Path(m.__file__).with_name(name).read_bytes()).hexdigest(), digest)

    def test_safety_envelope_retains_signal_only_no_orders(self):
        self.arm_and_advance(300, ready=True)
        for event in self.events:
            self.assertTrue(event["signal_only"])
            self.assertTrue(event["manual_execution_only"])
            self.assertFalse(event["orders"])
            self.assertFalse(event["production_behavior_changed"])
            self.assertFalse(event["protected_early_thresholds_changed"])


if __name__ == "__main__":
    unittest.main()
