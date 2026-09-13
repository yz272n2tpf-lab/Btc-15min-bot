#!/usr/bin/env python3
"""Shared BRTI transport feed V1.

Purpose
-------
Reduce external Kalshi BRTI request pressure by making exactly one process own
upstream polling and broadcasting the resulting *fresh primary sample* to local
consumers. This is infrastructure only: it does not generate trading signals or
orders and does not weaken qualification rules.

Safety invariants
-----------------
* One upstream request attempt per scheduled poll. No burst retry loop.
* 429s trigger exponential backoff instead of more requests.
* A failed latest upstream attempt makes the feed unqualified immediately.
* A successful broadcast sample qualifies only inside a short freshness TTL.
* Last-good data is retained for diagnostics only after any failed attempt.
* HTTP client reads never trigger an upstream request.
* SIGNAL ONLY. NO ORDERS.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional
import base64
import json
import math
import os
import random
import threading
import time

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

EXT = "https://external-api.kalshi.com"
BRTI_PATH = "/trade-api/v2/cfbenchmarks/values"


def _utc_iso(ts: Optional[float] = None) -> str:
    if ts is None:
        ts = time.time()
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()


def _num(v: Any) -> Optional[float]:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def brti_value(obj: Any) -> Optional[float]:
    vals = []

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            if "value" in x:
                v = _num(x.get("value"))
                if v is not None and 1000 < v < 1_000_000:
                    vals.append(v)
            for y in x.values():
                walk(y)
        elif isinstance(x, list):
            for y in x:
                walk(y)

    walk(obj)
    return vals[-1] if vals else None


def classify_exception(exc: Exception) -> str:
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    text = str(exc).lower()
    name = exc.__class__.__name__.lower()
    if status_code == 429 or "429" in text or "too many requests" in text:
        return "http_429"
    if "timeout" in name or "timeout" in text or "timed out" in text:
        return "timeout"
    if status_code is not None or "http" in name or "status code" in text:
        return "http"
    if "connection" in name or "connect" in text or "dns" in text or "name resolution" in text:
        return "connection"
    return "other"


@dataclass
class FeedSnapshot:
    value: Optional[float]
    status: str
    clean_for_qualification: bool
    age_ms: Optional[float]
    sequence: int
    success_timestamp_utc: Optional[str]
    last_attempt_timestamp_utc: Optional[str]
    last_error_type: Optional[str]
    last_error_text: Optional[str]
    consecutive_errors: int
    next_poll_in_ms: float
    poll_interval_ms: float
    max_qualification_age_ms: float
    upstream_attempts: int
    upstream_ok: int
    upstream_errors: int
    http_429: int
    timeout_errors: int
    http_errors: int
    connection_errors: int
    other_errors: int
    server_timestamp_utc: str
    mode: str = "SHARED_BRTI_PRIMARY_BROADCAST"
    signal_only: bool = True
    orders: bool = False


class SharedBrtiPoller:
    """Single owner of upstream BRTI polling.

    Call ``start`` once. Any number of HTTP consumers may call ``snapshot``;
    those reads never cause upstream traffic.
    """

    def __init__(
        self,
        fetch_once: Callable[[], Optional[float]],
        poll_interval_s: float = 1.0,
        max_qualification_age_s: float = 1.35,
        max_429_backoff_s: float = 30.0,
        jitter_s: float = 0.08,
    ) -> None:
        self.fetch_once = fetch_once
        self.poll_interval_s = max(0.25, float(poll_interval_s))
        self.max_qualification_age_s = max(self.poll_interval_s, float(max_qualification_age_s))
        self.max_429_backoff_s = max(self.poll_interval_s, float(max_429_backoff_s))
        self.jitter_s = max(0.0, float(jitter_s))

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self.value: Optional[float] = None
        self.status = "BOOTING"
        self.sequence = 0
        self.last_success_mono: Optional[float] = None
        self.last_success_wall: Optional[float] = None
        self.last_attempt_wall: Optional[float] = None
        self.last_error_type: Optional[str] = None
        self.last_error_text: Optional[str] = None
        self.consecutive_errors = 0
        self.next_due_mono = 0.0

        self.counters: Dict[str, int] = {
            "upstream_attempts": 0,
            "upstream_ok": 0,
            "upstream_errors": 0,
            "http_429": 0,
            "timeout_errors": 0,
            "http_errors": 0,
            "connection_errors": 0,
            "other_errors": 0,
        }

    @staticmethod
    def _valid(v: Any) -> bool:
        x = _num(v)
        return x is not None and x > 0.0

    def _schedule_after_error(self, error_type: str, now_mono: float) -> None:
        if error_type == "http_429":
            exp = min(max(1, self.consecutive_errors), 8)
            delay = min(self.max_429_backoff_s, self.poll_interval_s * (2 ** exp))
        else:
            delay = self.poll_interval_s
        if self.jitter_s:
            delay += random.uniform(0.0, self.jitter_s)
        self.next_due_mono = now_mono + delay

    def poll_once(self, force: bool = False) -> bool:
        now_mono = time.monotonic()
        if not force and now_mono < self.next_due_mono:
            return False

        wall = time.time()
        with self._lock:
            self.last_attempt_wall = wall
            self.counters["upstream_attempts"] += 1

        try:
            value = self.fetch_once()
            if not self._valid(value):
                raise ValueError("BRTI primary returned missing/invalid value")
            value = float(value)
        except Exception as exc:
            et = classify_exception(exc)
            with self._lock:
                self.status = "PRIMARY_ERROR"
                self.last_error_type = et
                self.last_error_text = str(exc)[:180]
                self.consecutive_errors += 1
                self.counters["upstream_errors"] += 1
                if et == "http_429":
                    self.counters["http_429"] += 1
                elif et == "timeout":
                    self.counters["timeout_errors"] += 1
                elif et == "http":
                    self.counters["http_errors"] += 1
                elif et == "connection":
                    self.counters["connection_errors"] += 1
                else:
                    self.counters["other_errors"] += 1
                self._schedule_after_error(et, now_mono)
            return True

        with self._lock:
            self.value = value
            self.status = "PRIMARY_OK"
            self.sequence += 1
            self.last_success_mono = now_mono
            self.last_success_wall = wall
            self.last_error_type = None
            self.last_error_text = None
            self.consecutive_errors = 0
            self.counters["upstream_ok"] += 1
            self.next_due_mono = now_mono + self.poll_interval_s
        return True

    def snapshot(self) -> Dict[str, Any]:
        now_mono = time.monotonic()
        now_wall = time.time()
        with self._lock:
            age_ms = None if self.last_success_mono is None else max(0.0, (now_mono - self.last_success_mono) * 1000.0)
            clean = (
                self.status == "PRIMARY_OK"
                and self.value is not None
                and age_ms is not None
                and age_ms <= self.max_qualification_age_s * 1000.0
            )
            snap = FeedSnapshot(
                value=self.value,
                status=self.status,
                clean_for_qualification=bool(clean),
                age_ms=age_ms,
                sequence=self.sequence,
                success_timestamp_utc=None if self.last_success_wall is None else _utc_iso(self.last_success_wall),
                last_attempt_timestamp_utc=None if self.last_attempt_wall is None else _utc_iso(self.last_attempt_wall),
                last_error_type=self.last_error_type,
                last_error_text=self.last_error_text,
                consecutive_errors=self.consecutive_errors,
                next_poll_in_ms=max(0.0, (self.next_due_mono - now_mono) * 1000.0),
                poll_interval_ms=self.poll_interval_s * 1000.0,
                max_qualification_age_ms=self.max_qualification_age_s * 1000.0,
                upstream_attempts=self.counters["upstream_attempts"],
                upstream_ok=self.counters["upstream_ok"],
                upstream_errors=self.counters["upstream_errors"],
                http_429=self.counters["http_429"],
                timeout_errors=self.counters["timeout_errors"],
                http_errors=self.counters["http_errors"],
                connection_errors=self.counters["connection_errors"],
                other_errors=self.counters["other_errors"],
                server_timestamp_utc=_utc_iso(now_wall),
            )
        return asdict(snap)

    def _run(self) -> None:
        while not self._stop.is_set():
            attempted = self.poll_once(force=False)
            wait = 0.03 if attempted else min(0.08, max(0.01, self.next_due_mono - time.monotonic()))
            self._stop.wait(wait)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.next_due_mono = 0.0
        self._thread = threading.Thread(target=self._run, name="brti-shared-poller", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)


class KalshiBrtiFetcher:
    def __init__(self, key_id: str, private_key_b64: str, timeout_s: float = 1.5) -> None:
        self.key_id = str(key_id).strip()
        self.key = serialization.load_pem_private_key(
            base64.b64decode(str(private_key_b64).strip()), password=None
        )
        self.timeout_s = float(timeout_s)
        self.http = requests.Session()

    def _hdr(self) -> Dict[str, str]:
        ts = str(int(time.time() * 1000))
        msg = ts + "GET" + BRTI_PATH
        sig = self.key.sign(
            msg.encode(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
            "KALSHI-ACCESS-TIMESTAMP": ts,
        }

    def fetch_once(self) -> Optional[float]:
        r = self.http.get(
            EXT + BRTI_PATH,
            headers=self._hdr(),
            params={"id": "BRTI", "maxResolution": "PER_SECOND"},
            timeout=self.timeout_s,
        )
        r.raise_for_status()
        return brti_value(r.json())


class FeedHandler(BaseHTTPRequestHandler):
    poller: SharedBrtiPoller

    def _write(self, status_code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/state":
            self._write(200, self.poller.snapshot())
            return
        if path == "/health":
            s = self.poller.snapshot()
            self._write(200, {"alive": True, "status": s["status"], "sequence": s["sequence"], "orders": False})
            return
        if path == "/ready":
            s = self.poller.snapshot()
            self._write(200 if s["clean_for_qualification"] else 503, s)
            return
        self._write(404, {"error": "not_found"})

    def log_message(self, fmt: str, *args: Any) -> None:
        return


class BrtiThreadingHTTPServer(ThreadingHTTPServer):
    request_queue_size = 128
    daemon_threads = True


def make_server(poller: SharedBrtiPoller, host: str, port: int) -> ThreadingHTTPServer:
    handler = type("BoundFeedHandler", (FeedHandler,), {"poller": poller})
    return BrtiThreadingHTTPServer((host, int(port)), handler)


def main() -> None:
    key_id = os.environ.get("KALSHI_KEY_ID", "").strip()
    private_key_b64 = os.environ.get("KALSHI_PRIVATE_KEY_B64", "").strip()
    if not key_id or not private_key_b64:
        raise SystemExit("BRTI_SHARED_FEED CONFIG ERROR | missing Kalshi credentials")

    poll_interval = float(os.environ.get("BRTI_SHARED_POLL_INTERVAL_S", "1.0"))
    max_age = float(os.environ.get("BRTI_SHARED_MAX_QUAL_AGE_S", "1.35"))
    max_429 = float(os.environ.get("BRTI_SHARED_MAX_429_BACKOFF_S", "30"))
    host = os.environ.get("BRTI_SHARED_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("BRTI_SHARED_PORT", "8080")))

    fetcher = KalshiBrtiFetcher(key_id, private_key_b64)
    poller = SharedBrtiPoller(
        fetcher.fetch_once,
        poll_interval_s=poll_interval,
        max_qualification_age_s=max_age,
        max_429_backoff_s=max_429,
    )
    poller.start()
    server = make_server(poller, host, port)

    def _log_loop() -> None:
        while True:
            time.sleep(60.0)
            st = poller.snapshot()
            ok = st["upstream_ok"]
            attempts = max(1, st["upstream_attempts"])
            print(
                "BRTI_SHARED HEARTBEAT | status=%s | clean=%s | age_ms=%s | seq=%s | "
                "upstream_ok=%s/%s (%.1f%%) | 429=%s | errors=%s | NO ORDERS"
                % (
                    st["status"], st["clean_for_qualification"],
                    "N/A" if st["age_ms"] is None else f"{st['age_ms']:.0f}",
                    st["sequence"], ok, st["upstream_attempts"], 100.0 * ok / attempts,
                    st["http_429"], st["upstream_errors"],
                ),
                flush=True,
            )

    threading.Thread(target=_log_loop, name="brti-shared-heartbeat", daemon=True).start()

    print(
        "BRTI SHARED FEED V1 START | SINGLE UPSTREAM POLLER | 429 BACKOFF | "
        "FRESH PRIMARY BROADCAST ONLY | SIGNAL ONLY | NO ORDERS",
        flush=True,
    )
    print(
        f"BRTI_SHARED CONFIG | poll={poll_interval:.2f}s | max_qual_age={max_age:.2f}s | "
        f"max429={max_429:.1f}s | port={port}",
        flush=True,
    )

    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
        poller.stop()


if __name__ == "__main__":
    main()
