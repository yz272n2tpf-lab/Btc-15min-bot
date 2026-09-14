#!/usr/bin/env python3
import unittest

from btc15_brti_resilient_fetch_v1 import (
    BrtiUnavailable,
    fetch_brti_resilient,
    parse_latest_brti,
)

NOW = 2_000.0


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = {} if payload is None else payload

    def json(self):
        return self._payload


def payload(value=78000.0, age_sec=1.0):
    return {
        "data": {
            "payload": [
                {"value": value - 1, "time": int((NOW - age_sec - 1) * 1000)},
                {"value": value, "time": int((NOW - age_sec) * 1000)},
            ]
        }
    }


class BrtiResilientFetchTests(unittest.TestCase):
    def test_parser_uses_latest_usable_item(self):
        value, source_ms, age = parse_latest_brti(payload(78123.45, 1.25), now_ts=NOW)
        self.assertAlmostEqual(value, 78123.45)
        self.assertEqual(source_ms, int((NOW - 1.25) * 1000))
        self.assertAlmostEqual(age, 1.25)

    def test_primary_success_returns_fresh_observation(self):
        calls = []
        def get(*args, **kwargs):
            calls.append(1)
            return FakeResponse(200, payload(age_sec=1.0))
        obs = fetch_brti_resilient(
            get=get,
            headers=lambda m, p: {"X": "safe"},
            backoff_sec=(0,),
            sleep=lambda _: None,
            now=lambda: NOW,
        )
        self.assertEqual(obs.attempts, 1)
        self.assertFalse(obs.recovered_after_retry)
        self.assertTrue(obs.fresh)
        self.assertEqual(len(calls), 1)

    def test_429_then_success_recovers_without_changing_source(self):
        responses = [FakeResponse(429), FakeResponse(200, payload(78200.0, 1.0))]
        sleeps = []
        def get(*args, **kwargs):
            return responses.pop(0)
        obs = fetch_brti_resilient(
            get=get,
            headers=lambda m, p: {},
            backoff_sec=(0, .5),
            sleep=sleeps.append,
            now=lambda: NOW,
        )
        self.assertAlmostEqual(obs.value, 78200.0)
        self.assertEqual(obs.attempts, 2)
        self.assertTrue(obs.recovered_after_retry)
        self.assertEqual(sleeps, [.5])

    def test_stale_success_is_not_accepted(self):
        responses = [
            FakeResponse(200, payload(78000.0, 10.0)),
            FakeResponse(200, payload(78001.0, 1.0)),
        ]
        obs = fetch_brti_resilient(
            get=lambda *a, **k: responses.pop(0),
            headers=lambda m, p: {},
            backoff_sec=(0, .5),
            sleep=lambda _: None,
            now=lambda: NOW,
            max_age_sec=5.0,
        )
        self.assertAlmostEqual(obs.value, 78001.0)
        self.assertEqual(obs.attempts, 2)

    def test_all_429_fails_closed(self):
        with self.assertRaises(BrtiUnavailable):
            fetch_brti_resilient(
                get=lambda *a, **k: FakeResponse(429),
                headers=lambda m, p: {},
                backoff_sec=(0, .1, .2),
                sleep=lambda _: None,
                now=lambda: NOW,
            )

    def test_malformed_payload_fails_closed(self):
        with self.assertRaises(BrtiUnavailable):
            fetch_brti_resilient(
                get=lambda *a, **k: FakeResponse(200, {"data": {"payload": []}}),
                headers=lambda m, p: {},
                backoff_sec=(0,),
                sleep=lambda _: None,
                now=lambda: NOW,
            )

    def test_never_substitutes_external_price(self):
        # The helper has no Coinbase/fallback price input by design. If the BRTI
        # endpoint fails, it must raise instead of returning any other price.
        with self.assertRaises(BrtiUnavailable):
            fetch_brti_resilient(
                get=lambda *a, **k: FakeResponse(503),
                headers=lambda m, p: {},
                backoff_sec=(0,),
                sleep=lambda _: None,
                now=lambda: NOW,
            )


if __name__ == "__main__":
    unittest.main()
