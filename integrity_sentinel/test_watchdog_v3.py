"""V3 unit/regression cases; all source responses and ledgers are synthetic."""
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import requests
from integrity_sentinel.runtime_v1 import Handler, RecorderRuntime, SourceConfig

CID = "KXBTC15M-26SEP171200-00"
HEALTHY = {"healthy": True, "observer_worker_alive": True,
           "observer_age_sec": 1.0, "observer_stale_sec": 60.0,
           "observer_last_exception": None}


class Transport(requests.adapters.BaseAdapter):
    def __init__(self, bodies):
        self.bodies, self.raw, self.calls = bodies, {}, []

    def send(self, request, **kwargs):
        assert request.method == "GET"
        name = request.url.rsplit("/", 1)[-1]
        assert name in self.bodies
        self.calls.append(name)
        response = requests.Response()
        response.request, response.url, response.status_code = request, request.url, 200
        self.raw[name] = json.dumps(self.bodies[name], separators=(",", ":")).encode()
        response.raw = io.BytesIO(self.raw[name])
        response.headers["X-Watchdog-Fixture"] = "v3-unit"
        return response

    def close(self):
        pass


class WatchdogV3Tests(unittest.TestCase):
    def setUp(self):
        for guard in (patch.dict(os.environ, {}, clear=True),
                      patch.object(requests.adapters.HTTPAdapter, "send",
                                   side_effect=AssertionError("external network forbidden"))):
            guard.start()
            self.addCleanup(guard.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        sources = [SourceConfig(name, "https://watchdog-test.up.railway.app/" + name, kind)
                   for name, kind in (("production_main", "telemetry"),
                       ("early_membership", "membership"), ("final_membership", "membership"))]
        expected = {"sources": {s.name: {"service_id": "unit-" + s.name,
            "deployment_id": "unit", "branch": "unit", "commit_sha": "a" * 40,
            "start_command": "python synthetic.py", "role": "observer",
            "cutoff_utc": {"not_applicable": True, "reason": "unit fixture"}} for s in sources}}
        actual = copy.deepcopy(expected)
        actual["captured_at_utc"] = "2026-01-01T00:00:00Z"
        self.r = RecorderRuntime(self.temp.name, sources, expected_manifest=expected, actual_snapshot=actual)
        self.r._thread = threading.current_thread()
        self.bodies = {"production_main": {"ok": True, "contract_id": CID}}
        for name, container in (("early_membership", "call_records"), ("final_membership", "lock_records")):
            self.bodies[name] = {"ok": True, "healthy": True, "watchdog": copy.deepcopy(HEALTHY),
                                 "live": {"ok": True, container: [{"contract_id": CID, "side": "UP"}]}}
        self.transport = Transport(self.bodies)
        self.r.session.trust_env = False
        self.r.session.mount("https://", self.transport)
        self.r.session.mount("http://", self.transport)
        self.addCleanup(self.r.session.close)

    def endpoint(self, path):
        h = object.__new__(Handler)
        h.runtime, h.path = self.r, path
        h._json = lambda code, body: (code, body)
        return h.do_GET()

    def set_watchdog(self, name, location, watchdog):
        self.bodies[name].pop("watchdog", None)
        self.bodies[name]["live"].pop("watchdog", None)
        obj = self.bodies[name] if location == "root" else self.bodies[name]["live"]
        obj["watchdog"] = copy.deepcopy(watchdog)

    def assert_observation(self, name):
        rows = list(self.r.membership._iter_records())
        obs = [r["body"] for r in rows if r["body"].get("record_type") == "SOURCE_OBSERVATION"
               and r["body"]["source"] == name][-1]
        raw = self.transport.raw[name]
        self.assertEqual(obs["payload"], self.bodies[name])
        self.assertEqual(base64.b64decode(obs["body_base64"]), raw)
        self.assertEqual(obs["body_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(obs["body_bytes"], len(raw))
        self.assertIs(obs["body_complete"], True)
        self.assertEqual(obs["http_status"], 200)
        self.assertEqual(obs["headers"]["X-Watchdog-Fixture"], "v3-unit")
        self.assertTrue(self.r.membership.status().chain_valid)
        self.assertTrue(any(row["body"].get("record_type") == "STRATEGY_MEMBERSHIP"
                            and row["body"]["source"] == name for row in rows))
        return obs

    def assert_failed(self, name):
        self.assertEqual(self.endpoint("/health")[0], 503)
        state = self.endpoint("/state")[1]
        self.assertIs(state["ok"], False)
        status = state["source_status"][name]
        self.assertIs(status["ok"], False)
        self.assertTrue(any("watchdog" in reason for reason in status["source_failures"]))
        obs = self.assert_observation(name)
        self.assertEqual(obs["source_failures"], status["source_failures"])
        self.assertIs(state["orders"], False)
        self.assertIs(state["certifiable_evidence"], False)
        self.assertEqual(state["provider_evidence"], {"kalshi": "INSUFFICIENT", "coinbase": "INSUFFICIENT"})


NEGATIVE_CASES = {
    "healthy_false": {"healthy": False},
    "worker_dead": {"observer_worker_alive": False},
    "worker_stale": {"observer_age_sec": 61},
    "worker_error": {"observer_last_exception": "RuntimeError:fixture failure"},
    "contradictory_flags": {"healthy": False, "ok": True, "fresh": True},
    "failed": {"failed": True}, "dead_flag": {"dead": True}, "stale_flag": {"stale": True},
}
for key in ("status", "state"):
    for value in ("dead", "stale", "error", "failed", "unhealthy", "stopped"):
        NEGATIVE_CASES[key + "_" + value] = {key: value}
    for label, value in (("null", None), ("list", []), ("object", {}), ("integer", 1)):
        NEGATIVE_CASES[key + "_" + label] = {key: value}
for label, value in (("zero", 0), ("one", 1), ("true_string", "true"),
                     ("false_string", "false"), ("null", None), ("list", []), ("object", {})):
    NEGATIVE_CASES["healthy_" + label] = {"healthy": value}
for key in ("observer_age_sec", "observer_stale_sec"):
    for label, value in (("negative", -1), ("string", "1"), ("null", None),
                         ("boolean", True), ("list", []), ("object", {}), ("overflow", 10 ** 400)):
        NEGATIVE_CASES[key + "_" + label] = {key: value}
NEGATIVE_CASES["zero_threshold"] = {"observer_stale_sec": 0}
NEGATIVE_CASES["malformed_worker_alive"] = {"observer_worker_alive": 1}
NEGATIVE_CASES["malformed_exception"] = {"observer_last_exception": {}}


def negative_test(name, location, changes):
    def test(self):
        self.set_watchdog(name, location, {**HEALTHY, **changes})
        self.r.run_cycle()
        self.assert_failed(name)
    return test


def lifecycle_test(name, location):
    def test(self):
        self.set_watchdog(name, location, HEALTHY)
        self.r.run_cycle()
        self.assertEqual(self.endpoint("/health")[0], 200)
        first = self.r.membership.path.read_bytes()
        self.set_watchdog(name, location, {**HEALTHY, "healthy": False})
        self.r.run_cycle()
        self.assert_failed(name)
        negative = self.r.membership.path.read_bytes()
        self.assertTrue(negative.startswith(first))
        # Telemetry-only success must never erase the failed membership status.
        self.r.run_cycle(include_membership=False)
        self.assert_failed(name)
        self.set_watchdog(name, location, HEALTHY)
        self.r.run_cycle()
        self.assertEqual(self.endpoint("/health")[0], 200)
        self.assertIs(self.endpoint("/state")[1]["ok"], True)
        self.assertTrue(self.r.membership.path.read_bytes().startswith(negative))
        self.assert_observation(name)
    return test


def malformed_object_test(name, location):
    def test(self):
        for value in (None, False, 0, 1, "healthy", [], {}, {"ok": True}):
            with self.subTest(value=value):
                self.set_watchdog(name, location, value)
                self.r.run_cycle()
                self.assert_failed(name)
    return test


def locations_test(name):
    def test(self):
        for bad_location in ("root", "live"):
            self.bodies[name]["watchdog"] = copy.deepcopy(HEALTHY)
            self.bodies[name]["live"]["watchdog"] = copy.deepcopy(HEALTHY)
            target = self.bodies[name] if bad_location == "root" else self.bodies[name]["live"]
            target["watchdog"]["healthy"] = False
            self.r.run_cycle()
            self.assert_failed(name)
    return test


def missing_test(name):
    def test(self):
        del self.bodies[name]["watchdog"]
        self.r.run_cycle()
        self.assert_failed(name)
        self.assertIn("watchdog:missing", self.r.state["source_status"][name]["source_failures"])
    return test


def recovery_gate_test(name):
    def test(self):
        self.bodies[name]["watchdog"]["healthy"] = False
        self.r.run_cycle()
        self.assert_failed(name)
        negative = self.r.membership.path.read_bytes()
        self.bodies[name]["watchdog"] = copy.deepcopy(HEALTHY)
        self.bodies["production_main"]["ok"] = False
        self.r.run_cycle()
        self.assertIs(self.r.state["source_status"][name]["ok"], True)
        self.assertEqual(self.endpoint("/health")[0], 503)
        self.assertIs(self.endpoint("/state")[1]["ok"], False)
        self.assertTrue(self.r.membership.path.read_bytes().startswith(negative))
    return test


for name in ("early_membership", "final_membership"):
    for location in ("root", "live"):
        for label, changes in NEGATIVE_CASES.items():
            setattr(WatchdogV3Tests, "test_" + name + "_" + location + "_" + label,
                    negative_test(name, location, changes))
        setattr(WatchdogV3Tests, "test_" + name + "_" + location + "_lifecycle", lifecycle_test(name, location))
        setattr(WatchdogV3Tests, "test_" + name + "_" + location + "_malformed_object", malformed_object_test(name, location))
    setattr(WatchdogV3Tests, "test_" + name + "_both_locations", locations_test(name))
    setattr(WatchdogV3Tests, "test_" + name + "_missing", missing_test(name))
    setattr(WatchdogV3Tests, "test_" + name + "_recovery_other_gate", recovery_gate_test(name))


if __name__ == "__main__":
    unittest.main()
