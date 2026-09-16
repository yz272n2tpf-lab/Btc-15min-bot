#!/usr/bin/env python3
"""
BTC15 FINAL V4 live frozen-review endpoint V1.

READ ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

Fetches the authoritative FINAL V4 /state payload and passes it unchanged into
the fail-closed frozen review report. This wrapper never qualifies a signal,
changes a threshold, settles a market, or promotes a model.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

import requests

import BTC15_FINAL_V4_FROZEN_REVIEW_REPORT_V1 as review

VERSION = "BTC15_FINAL_V4_REVIEW_LIVE_V1"
PORT = int(os.environ.get("PORT", "8080"))
FINAL_STATE_URL = os.environ.get(
    "BTC15_FINAL_V4_STATE_URL",
    "https://final-forward-scorecard-v1-production.up.railway.app/state",
)
TIMEOUT_SEC = 4.0


def fetch_final_state() -> dict[str, Any]:
    response = requests.get(
        FINAL_STATE_URL,
        timeout=TIMEOUT_SEC,
        headers={"Cache-Control": "no-cache", "User-Agent": VERSION},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("FINAL V4 /state payload is not a JSON object")
    return payload


def build_snapshot(payload: Mapping[str, Any]) -> dict[str, Any]:
    report = review.build_report(payload)
    return {
        "ok": bool(report["integrity"]["pass"]),
        "version": VERSION,
        "source_collector": review.EXPECTED_COLLECTOR_VERSION,
        "source_url": FINAL_STATE_URL,
        "review": report,
        "manual_review_ready": bool(report["frozen_gate"]["manual_review_ready"]),
        "auto_promote_allowed": False,
        "threshold_retune_allowed": False,
        "numeric_flip_risk_validated": False,
        "manual_execution_only": True,
        "orders": False,
    }


def collect_live() -> dict[str, Any]:
    return build_snapshot(fetch_final_state())


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15FinalV4ReviewLiveV1/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("FINAL_V4_REVIEW_HTTP | " + (fmt % args), flush=True)

    def _json(self, code: int, obj: Any) -> None:
        raw = json.dumps(obj, separators=(",", ":"), default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def _text(self, code: int, text: str) -> None:
        raw = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            snapshot = collect_live()
            if path == "/health":
                return self._json(200 if snapshot["ok"] else 503, {
                    "ok": snapshot["ok"],
                    "version": VERSION,
                    "collector_integrity": snapshot["review"]["integrity"],
                    "review_status": snapshot["review"]["status"],
                    "manual_review_ready": snapshot["manual_review_ready"],
                    "auto_promote_allowed": False,
                    "manual_execution_only": True,
                    "orders": False,
                })
            if path == "/review":
                return self._json(200 if snapshot["ok"] else 503, snapshot)
            if path == "/review.txt":
                code = 200 if snapshot["ok"] else 503
                return self._text(code, review.render_text(snapshot["review"]))
            return self._json(404, {"ok": False, "orders": False, "error": "not_found"})
        except Exception as exc:
            return self._json(503, {
                "ok": False,
                "version": VERSION,
                "error": f"{type(exc).__name__}:{exc}",
                "fail_closed": True,
                "auto_promote_allowed": False,
                "manual_execution_only": True,
                "orders": False,
            })

    def _reject(self) -> None:
        return self._json(405, {
            "ok": False,
            "error": "read_only_review_endpoint",
            "manual_execution_only": True,
            "orders": False,
        })

    do_POST = _reject
    do_PUT = _reject
    do_PATCH = _reject
    do_DELETE = _reject


def main() -> int:
    first = collect_live()
    print(
        f"{VERSION} START | status={first['review']['status']} | "
        f"integrity={first['review']['integrity']['pass']} | "
        f"eligible={first['review']['frozen_gate']['eligible_contracts']} | "
        f"settled={first['review']['frozen_gate']['settled_locks']} | "
        f"manual_review_ready={first['manual_review_ready']} | READ ONLY | NO ORDERS",
        flush=True,
    )
    print(review.render_text(first["review"]), flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
