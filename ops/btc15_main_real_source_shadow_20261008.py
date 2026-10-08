"""Bounded BTC15 real-feed MAIN candidate SHADOW. No orders and no production writes.

This diagnostic launcher is deliberately not a production replacement. It
allows native source/quote/timing evidence from the preserved MAIN candidate in
one already-existing, specifically identified test service. Files are written
only to ephemeral test storage and logs. No order endpoint or write HTTP method.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

# Executable scripts run from ops/, so anchor imports to the reviewed repository.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROJECT = "baea4e22-d004-4434-b2c5-81a7fbc05086"
ENVIRONMENT = "61775c5d-c583-4dfc-af41-f25578856fd9"
SHADOW_SERVICE = "84bbacb1-56a4-4370-aa1c-0f8ae8ae42c1"
OPT_IN = "LIVE_READ_ONLY_NO_ORDERS"
MAX_SECONDS = 48 * 60
SAMPLE_SECONDS = 5

def validate_runtime():
    if (os.getenv("RAILWAY_PROJECT_ID") != PROJECT or
        os.getenv("RAILWAY_ENVIRONMENT_ID") != ENVIRONMENT or
        os.getenv("RAILWAY_SERVICE_ID") != SHADOW_SERVICE or
        os.getenv("BTC15_TEST_SHADOW_OPT_IN") != OPT_IN):
        raise SystemExit("BTC15_SHADOW_GUARD_FAIL: wrong service/environment or no explicit opt-in")
    if os.getenv("RAILWAY_VOLUME_ID") or os.getenv("RAILWAY_VOLUME_MOUNT_PATH"):
        raise SystemExit("BTC15_SHADOW_GUARD_FAIL: original evidence volume must be safely detached")
    if not os.getenv("RAILWAY_DEPLOYMENT_ID"):
        raise SystemExit("BTC15_SHADOW_GUARD_FAIL: deployment identity required")
    for key in ("KALSHI_KEY_ID", "KALSHI_PRIVATE_KEY_B64", "BTC15_BRTI_SHARED_URL"):
        if not os.getenv(key):
            raise SystemExit("BTC15_SHADOW_FEED_NOT_CONFIGURED: " + key)
    from btc15_v2_product.release import verify_files
    verify_files("main")

def block_http_writes():
    """Refuse outgoing POST/PUT/PATCH/DELETE including any Kalshi order request."""
    import requests
    import http.client
    original_session = requests.sessions.Session.request
    def read_only_session(self, method, url, *a, **k):
        if str(method).upper() not in ("GET", "HEAD", "OPTIONS"):
            raise RuntimeError("BTC15_SHADOW_NONREAD_HTTP_BLOCKED")
        return original_session(self, method, url, *a, **k)
    requests.sessions.Session.request = read_only_session
    for cls in (http.client.HTTPConnection, http.client.HTTPSConnection):
        original = cls.request
        def safe_request(self, method, url, body=None, headers=None, *, encode_chunked=False, _original=original):
            if str(method).upper() not in ("GET", "HEAD", "OPTIONS"):
                raise RuntimeError("BTC15_SHADOW_NONREAD_HTTP_BLOCKED")
            return _original(self, method, url, body=body, headers=headers or {}, encode_chunked=encode_chunked)
        cls.request = safe_request

def child():
    validate_runtime()
    block_http_writes()
    from btc15_v2_product.runtime import native_main
    print("BTC15_SHADOW_NATIVE_START | fresh MAIN candidate | SIGNAL_ONLY NO_ORDERS", flush=True)
    native_main()

def load_publication(root):
    path = root / "main.json"
    try:
        raw = path.read_bytes()
        if len(raw) > 524288:
            raise ValueError("OVERSIZE")
        return json.loads(raw)
    except (OSError, ValueError):
        return None

def report_line(state, window):
    result = dict(schema="BTC15_MAIN_REAL_SOURCE_SHADOW_R1",
                  at=datetime.now(timezone.utc).isoformat(), signal_only=True,
                  orders=False, evidence="REAL_FEED_SHADOW_NOT_LIVE_ACCEPTANCE",
                  **state)
    print("BTC15_SHADOW_SAMPLE | " + json.dumps(result, separators=(",",":"), allow_nan=False), flush=True)

def parent():
    validate_runtime()
    deployment = os.environ["RAILWAY_DEPLOYMENT_ID"]
    root = Path("/tmp/btc15-main-real-source-shadow") / deployment
    root.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env["BTC15_LADDER_DATA_ROOT"] = str(root)
    env["BTC15_COHORT_EVIDENCE_PATH"] = str(root / "native-cohort.jsonl")
    env["BTC15_ENABLE_INFORMATION_EXPORT"] = "1"
    env.pop("BTC15_VOLUME_DIAG", None)
    start = time.time()
    first_full_window = (int(start // 900) + 1) * 900
    expected_end = first_full_window + 2 * 900 + 10
    deadline = min(start + MAX_SECONDS, expected_end)
    summary = dict(samples=0, current=0, not_current=0, no_view=0,
                   contracts=Counter(), reasons=Counter(),
                   initial_time=start, intended_full_window_start=first_full_window,
                   intended_full_window_end=first_full_window + 1800)
    status = dict(state="STARTING", signal_only=True, orders=False, contracts=0, samples=0)
    proc = subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve()), "--native-child"],
                            env=env, stdin=subprocess.DEVNULL)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ("/health", "/status"):
                self.send_error(404);return
            good = proc.poll() is None
            value = dict(schema="BTC15_SHADOW_HEALTH_R1", running=good, **status)
            raw = json.dumps(value, separators=(",",":")).encode()
            self.send_response(200 if good else 503)
            self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(raw)))
            self.end_headers();self.wfile.write(raw)
        def log_message(self,*args):
            pass
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True, name="shadow-health")
    t.start()
    print("BTC15_SHADOW_TRIAL_BEGIN | " + json.dumps(dict(
        deployment=deployment, build=env.get("RAILWAY_GIT_COMMIT_SHA"),
        deadline_utc=datetime.fromtimestamp(deadline,timezone.utc).isoformat(),
        first_full_window_utc=datetime.fromtimestamp(first_full_window,timezone.utc).isoformat(),
        temporary_root=True, detached_old_evidence=True,
        signal_only=True, orders=False)), flush=True)
    last_contract = None
    try:
        while time.time() < deadline and proc.poll() is None:
            time.sleep(SAMPLE_SECONDS)
            now = time.time()
            v = load_publication(root)
            summary["samples"] += 1
            if not isinstance(v, dict):
                summary["no_view"] += 1
                state, reason, contract = "NO_VIEW", "NO_JOURNAL_YET", None
            else:
                contract = v.get("contract")
                if contract:summary["contracts"][contract] += 1
                expiry = v.get("expires_at")
                current = (v.get("status") != "UNAVAILABLE" and
                           isinstance(expiry,(int,float)) and
                           isinstance(v.get("published_ts"),(int,float)) and
                           v["published_ts"] <= now < expiry)
                state = "CURRENT" if current else "NOT_CURRENT"
                reason = "QUALIFIED" if current else str(v.get("reason") or "SOURCE_EXPIRED_OR_PASS")
                summary["current" if current else "not_current"] += 1
            summary["reasons"][reason] += 1
            if contract != last_contract and contract:
                print("BTC15_SHADOW_CONTRACT | " + str(contract) + " | NO ORDERS",flush=True)
                last_contract = contract
            status.update(state=state, samples=summary["samples"],
                          contracts=len(summary["contracts"]))
            report_line(dict(state=state,reason=reason,contract=contract), None)
        print("BTC15_SHADOW_TRIAL_END | " + json.dumps(dict(
            status="TIME_LIMIT" if time.time()>=deadline else "NATIVE_EXIT",
            child_code=proc.poll(), samples=summary["samples"],
            current_samples=summary["current"],
            unavailable_samples=summary["not_current"],
            no_journal_samples=summary["no_view"],
            contracts_seen=dict(summary["contracts"]), reasons=dict(summary["reasons"]),
            fully_covered_contracts="NOT_PROVEN_BY_SAMPLE_COUNT",
            signal_only=True, orders=False),separators=(",",":")),flush=True)
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:proc.wait(timeout=12)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.wait()
        server.shutdown();server.server_close()
    return 0 if summary["samples"] and summary["current"] else 2

def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight",action="store_true")
    group.add_argument("--run-shadow",action="store_true")
    group.add_argument("--native-child",action="store_true")
    args=parser.parse_args()
    if args.preflight:
        from btc15_v2_product.release import verify_files
        verify_files("main")
        print("BTC15_SHADOW_STATIC_PREFLIGHT_PASS: protected ladders intact; no orders or live reads",flush=True)
        return 0
    return child() if args.native_child else parent()

if __name__=="__main__":
    raise SystemExit(main())
