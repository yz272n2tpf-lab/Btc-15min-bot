"""Independent offline V3 probes: no unit fixtures or validator imports.

Replays pinned producer functions without importing/starting their services.
All HTTP source responses are in-memory; endpoint checks use real loopback HTTP.
All evidence and injected damage live in disposable synthetic directories.
"""
import base64
import copy
from contextlib import contextmanager
import hashlib
import http.client
from http.server import ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlparse

import requests
from integrity_sentinel.runtime_v1 import Handler, RecorderRuntime, SourceConfig
from integrity_sentinel.recorder_core_v1 import AppendOnlyHashChainLedger

CID = "KXBTC15M-26SEP181200-00"
OTHER = "KXBTC15M-26SEP181215-00"
HOST = "https://v3-offline.up.railway.app/"
KINDS = {"production_main": "telemetry", "scalp_combined": "telemetry",
         "brti_shared": "telemetry", "early_membership": "membership",
         "final_membership": "membership", "combined_membership": "membership",
         "nextgen_membership": "membership"}
SCHEMA = json.loads(Path(__file__).with_name("WATCHDOG_SCHEMA_V3.json").read_text())


def produced_watchdog(family, mode="healthy"):
    """Execute the frozen runtime_health function in an isolated namespace."""
    entry = SCHEMA["early" if family == "early" else "final_watchdog"]
    state = {"observer_worker_alive": mode != "dead", "observer_restarts": 2,
             "observer_iterations": 8, "observer_successes": 7,
             "observer_last_iteration_utc": "2026-09-17T00:00:00Z",
             "observer_last_success_utc": "2026-09-17T00:00:00Z",
             "observer_last_exception": "RuntimeError:probe" if mode == "error" else None,
             "active_generation": 3}
    ns = {"observer_age_seconds": lambda now: 61.0 if mode == "stale" else 1.0,
          "RUNTIME_LOCK": threading.RLock(), "RUNTIME": state, "OBSERVER_STALE_SEC": 60.0}
    exec(compile("from __future__ import annotations\n" + entry["excerpts"]["runtime_health"]["source"],
                 entry["path"], "exec"), ns)
    return ns["runtime_health"]()


def produced_payload(family, watchdog):
    """Execute actual Early V1 / Final V4 /state handler, without startup."""
    field = "call_records" if family == "early" else "lock_records"
    live = {field: [{"contract_id": CID, "side": "UP", "score": .91}], "settled_records": []}
    ns = {"urlparse": urlparse, "LOCK": threading.RLock(), "STATE": {},
          "VERSION": "pinned-source-offline-replay", "runtime_health": lambda: watchdog,
          "summarize_state": lambda: live, "summarize_live_snapshot": lambda state: live,
          "v3": SimpleNamespace(runtime_health=lambda: watchdog)}
    entry = SCHEMA[family]
    exec(compile("from __future__ import annotations\n" + entry["excerpts"]["do_GET"]["source"],
                 entry["path"], "exec"), ns)
    handler = SimpleNamespace(path="/state", _json=lambda code, body: (code, body))
    code, body = ns["do_GET"](handler)
    assert code == 200 and body["ok"] is True and body["watchdog"] == watchdog
    return body


def payload(name):
    if name in ("early_membership", "final_membership"):
        family = name.split("_")[0]
        return produced_payload(family, produced_watchdog(family))
    if name == "combined_membership":
        return {"ok": True, "scorecard": {"contract_rows": [{"contract_id": CID}]}}
    if name == "nextgen_membership":
        return {"ok": True, "audit_records": {"family": {"lane": [{"contract_id": CID}]}}}
    if name == "brti_shared":
        return {"ok": True, "age_ms": 250, "clean_for_qualification": True, "status": "OK"}
    return {"ok": True, "contract_id": CID, "source_age_sec": .1}


class MemorySource(requests.adapters.BaseAdapter):
    def __init__(self):
        self.bodies = {name: payload(name) for name in KINDS}
        self.calls, self.raw, self.errors = [], {}, {}

    def send(self, request, **kwargs):
        assert request.method == "GET" and request.url.startswith(HOST)
        assert kwargs["verify"] is True and kwargs["stream"] is True
        name = request.url[len(HOST):]
        assert name in KINDS
        self.calls.append(name)
        if name in self.errors:
            raise self.errors[name]
        reply = requests.Response()
        reply.request, reply.url, reply.status_code = request, request.url, 200
        raw = json.dumps(self.bodies[name], separators=(",", ":")).encode()
        self.raw[name] = raw
        reply.raw = io.BytesIO(raw)
        reply.headers["X-Independent-Probe"] = "V3"
        return reply

    def close(self):
        pass


@contextmanager
def fixture(control=None):
    with tempfile.TemporaryDirectory(prefix="sentinel-v3-offline-") as td, patch.dict(os.environ, {}, clear=True):
        sources = [SourceConfig(n, HOST + n, k) for n, k in KINDS.items()]
        expected = {"sources": {s.name: {"service_id": "independent-" + s.name,
            "deployment_id": "frozen-offline", "branch": "offline", "commit_sha": "b" * 40,
            "start_command": "python offline.py", "role": "observer",
            "cutoff_utc": {"not_applicable": True, "reason": "synthetic fixture"}} for s in sources}}
        actual = copy.deepcopy(expected)
        actual["captured_at_utc"] = "2026-01-01T00:00:00Z"
        if control == "missing":
            actual = None
        elif control == "mismatch":
            actual["sources"]["production_main"]["commit_sha"] = "c" * 40
        r = RecorderRuntime(td, sources, expected_manifest=expected, actual_snapshot=actual)
        r._thread = threading.current_thread()
        transport = MemorySource()
        r.session.trust_env = False
        r.session.mount("https://", transport)
        r.session.mount("http://", transport)
        try:
            yield r, transport
        finally:
            r.session.close()


def endpoints(r):
    server = ThreadingHTTPServer(("127.0.0.1", 0), type("V3Handler", (Handler,), {"runtime": r}))
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .001})
    worker.start()
    result = {}
    try:
        for path in ("/health", "/state"):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            connection.request("GET", path)
            response = connection.getresponse()
            result[path] = (response.status, json.loads(response.read()))
            connection.close()
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()
    return result


def assert_health(r, healthy):
    views = endpoints(r)
    assert views["/health"][0] == (200 if healthy else 503), views
    assert views["/health"][1]["ok"] is healthy
    assert views["/state"][0] == 200 and views["/state"][1]["ok"] is healthy
    state = views["/state"][1]
    assert state["orders"] is False and state["automatic_promotion"] is False
    assert state["certifiable_evidence"] is False and state["direct_market_api_polling"] is False
    assert state["provider_evidence"] == {"kalshi": "INSUFFICIENT", "coinbase": "INSUFFICIENT"}
    return state


def check_observation(r, transport, name, negative):
    rows = list(r.membership._iter_records())
    row = [x for x in rows if x["body"].get("record_type") == "SOURCE_OBSERVATION"
           and x["body"]["source"] == name][-1]
    obs = row["body"]
    raw = transport.raw[name]
    assert obs["payload"] == transport.bodies[name]
    assert base64.b64decode(obs["body_base64"]) == raw
    assert obs["body_sha256"] == hashlib.sha256(raw).hexdigest()
    assert obs["body_bytes"] == len(raw) and obs["body_complete"] is True
    assert obs["http_status"] == 200 and obs["parse_outcome"] == "OBJECT"
    assert obs["headers"]["X-Independent-Probe"] == "V3"
    assert all(obs[k] is not None for k in ("request_url", "response_url", "started_at_utc", "completed_at_utc", "latency_ms"))
    status = r.public_state()["source_status"][name]
    assert status["ok"] is (not negative)
    assert status["source_failures"] == obs["source_failures"]
    if negative:
        assert any("watchdog" in f for f in obs["source_failures"])
    assert any(x["body"].get("record_type") == "STRATEGY_MEMBERSHIP" and x["body"]["source"] == name for x in rows)
    assert r.membership.status().chain_valid
    return obs["source_failures"]


def watchdog_matrix():
    results = []
    for family in ("early", "final"):
        name = family + "_membership"
        good = produced_watchdog(family)
        cases = [("producer_healthy", good, False),
                 ("producer_dead", produced_watchdog(family, "dead"), True),
                 ("producer_stale", produced_watchdog(family, "stale"), True),
                 ("producer_error", produced_watchdog(family, "error"), True),
                 ("healthy_false", {**good, "healthy": False}, True),
                 ("contradictory_flags", {**good, "healthy": False, "ok": True}, True),
                 ("healthy_but_dead", {**good, "observer_worker_alive": False}, True),
                 ("healthy_but_stale", {**good, "observer_age_sec": 61}, True)]
        for label, value in (("0", 0), ("1", 1), ("string_true", "true"), ("string_false", "false"),
                             ("null", None), ("list", []), ("object", {})):
            cases.append(("malformed_healthy_" + label, {**good, "healthy": value}, True))
        for key in ("observer_age_sec", "observer_stale_sec"):
            for label, value in (("negative", -1), ("null", None), ("string", "1"),
                                 ("boolean", True), ("list", []), ("object", {}), ("overflow", 10 ** 400)):
                cases.append(("malformed_" + key + "_" + label, {**good, key: value}, True))
        for key in ("status", "state"):
            for value in ("DEAD", "STALE", "ERROR", "FAILED", "UNHEALTHY", None, [], {}):
                cases.append((key + "_" + repr(value), {**good, key: value}, True))
        cases.extend((label, value, True) for label, value in
                     (("watchdog_null", None), ("watchdog_list", []), ("watchdog_empty", {})))
        for location in ("root", "live"):
            for label, value, negative in cases:
                with fixture() as (r, transport):
                    body = produced_payload(family, value)
                    if location == "live":
                        body["live"]["watchdog"] = body.pop("watchdog")
                    transport.bodies[name] = body
                    r.run_cycle()
                    assert_health(r, not negative)
                    failures = check_observation(r, transport, name, negative)
                    results.append({"source": name, "location": location, "case": label,
                                    "result": "PASS", "health_http": 503 if negative else 200,
                                    "state_ok": not negative, "source_ok": not negative,
                                    "immutable_observation": True, "source_failures": failures})
        for bad_location in ("root", "live"):
            with fixture() as (r, t):
                t.bodies[name]["live"]["watchdog"] = copy.deepcopy(good)
                envelope = t.bodies[name] if bad_location == "root" else t.bodies[name]["live"]
                envelope["watchdog"]["healthy"] = False
                r.run_cycle()
                assert_health(r, False)
                reasons = check_observation(r, t, name, True)
                results.append({"source": name, "case": "conflicting_locations_" + bad_location,
                                "result": "PASS", "source_failures": reasons})
        with fixture() as (r, t):
            del t.bodies[name]["watchdog"]
            r.run_cycle()
            assert_health(r, False)
            reasons = check_observation(r, t, name, True)
            results.append({"source": name, "case": "missing_watchdog", "result": "PASS", "source_failures": reasons})
    return results


def lifecycle():
    results = []
    for family in ("early", "final"):
        name = family + "_membership"
        with fixture() as (r, t):
            r.run_cycle()
            assert_health(r, True)
            healthy_prefix = r.membership.path.read_bytes()
            t.bodies[name] = produced_payload(family, produced_watchdog(family, "error"))
            r.run_cycle()
            assert_health(r, False)
            check_observation(r, t, name, True)
            negative_prefix = r.membership.path.read_bytes()
            assert negative_prefix.startswith(healthy_prefix)
            r.run_cycle(include_membership=False)
            assert_health(r, False)
            t.bodies[name] = produced_payload(family, produced_watchdog(family))
            t.bodies["production_main"]["ok"] = False
            r.run_cycle()
            assert_health(r, False)
            assert r.public_state()["source_status"][name]["ok"] is True
            t.bodies["production_main"]["ok"] = True
            r.run_cycle()
            assert_health(r, True)
            check_observation(r, t, name, False)
            assert r.membership.path.read_bytes().startswith(negative_prefix)
            assert AppendOnlyHashChainLedger(r.membership.path).status().chain_valid
            results.append({"source": name, "case": "healthy_unhealthy_recovery",
                            "result": "PASS", "telemetry_only_cannot_clear": True,
                            "other_failed_gate_blocks_recovery": True,
                            "negative_history_byte_identical": True, "reopened_chain_valid": True})
    return results


def false_health_matrix():
    """The prior second-reverification 16-case matrix, with watchdog-complete controls."""
    cases = ["outage", "payload_stale", "observation_stale", "explicit_failure", "membership_failure",
             "thread_dead", "thread_stale", "write_failure", "low_disk", "disk_query_failure",
             "ledger_corruption", "anchor_corruption", "durability_marker", "missing_control",
             "mismatched_control", "contract_disagreement"]
    results = []
    for case in cases:
        control = "missing" if case == "missing_control" else "mismatch" if case == "mismatched_control" else None
        with fixture(control) as (r, t):
            r.run_cycle()
            if control is None:
                assert_health(r, True)
            if case == "outage":
                t.errors["production_main"] = requests.exceptions.ConnectionError("offline")
                r.run_cycle()
            elif case == "payload_stale":
                t.bodies["production_main"]["source_age_sec"] = 1e5
                r.run_cycle()
            elif case == "observation_stale":
                r._source_mono["early_membership"] -= 1000
            elif case in ("explicit_failure", "membership_failure"):
                t.bodies["production_main" if case == "explicit_failure" else "final_membership"]["ok"] = False
                r.run_cycle()
            elif case == "thread_dead":
                r._thread = threading.Thread()
            elif case == "thread_stale":
                r._last_success_mono -= 1000
            elif case == "write_failure":
                with patch.object(r.telemetry, "append", side_effect=OSError("synthetic failure")):
                    r.run_cycle()
            elif case == "ledger_corruption":
                r.telemetry.path.write_bytes(r.telemetry.path.read_bytes()[:-1])
            elif case == "anchor_corruption":
                r.telemetry.anchor_path.write_bytes(b'{"committed":true}')
            elif case == "durability_marker":
                r.membership.durability_path.write_bytes(b"")
            elif case == "contract_disagreement":
                t.bodies["scalp_combined"]["contract_id"] = OTHER
                r.run_cycle()
            if case in ("low_disk", "disk_query_failure"):
                kwargs = {"return_value": SimpleNamespace(total=100, used=99, free=1)} if case == "low_disk" else {"side_effect": OSError("synthetic disk fault")}
                with patch("integrity_sentinel.storage_guard_v1.shutil.disk_usage", **kwargs):
                    state = assert_health(r, False)
            else:
                state = assert_health(r, False)
            results.append({"case": case, "result": "PASS", "health_failures": state["health_failures"]})
    return results


def run():
    real_connect = socket.socket.connect
    def local_connect(sock, address):
        if not isinstance(address, tuple) or address[0] not in ("127.0.0.1", "::1"):
            raise AssertionError("external network forbidden")
        return real_connect(sock, address)
    with patch.object(socket.socket, "connect", local_connect), patch.object(
            requests.adapters.HTTPAdapter, "send", side_effect=AssertionError("real source network forbidden")):
        report = {"watchdog_matrix": watchdog_matrix(), "lifecycle": lifecycle(),
                  "prior_false_health_matrix": false_health_matrix()}
    report["counts"] = {key: len(value) for key, value in report.items()}
    report["passed"] = sum(report["counts"].values())
    report["total"] = report["passed"]
    report["result"] = "PASS"
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
