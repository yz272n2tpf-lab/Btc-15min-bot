#!/usr/bin/env python3
"""Isolated, read-only P5 host. No producer imports, cache, retries or polling.

Local hosting: python3 cockpit_candidate/server.py --port 8765
Open /?mode=fixture for offline fixtures; /?mode=live uses the original owners.
Live mode contacts the fixed MAIN host and the unchanged direct SCALP endpoint.
Do not use live mode without separately authorized delivery acceptance.

For a future isolated HTTPS reverse proxy, explicitly allow its Host using
--public-host cockpit.example. This changes inbound hosting only, never MAIN.
TLS termination, public hosting and physical-device acceptance belong to P6.
"""

import argparse
import http.client
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parent
MAIN_HOST = "btc-15min-bot-production.up.railway.app"
MAIN_PATHS = frozenset({
    "/ladders", "/ladders/quotes", "/ladders/indicators",
    "/information", "/dashboard_state.json",
})
NONCE = "X-BTC15-Information-Nonce"
_SOURCE_HEALTH_LOCK = threading.Lock()
_SOURCE_HEALTH_LAST = {}
# A blocking network-I/O bound, not a publication lease or browser deadline.
# Original clients still abort at 700 ms (information), 3 s (ladders), 8 s
# (market). This host does not renew or interpret any of those source clocks.
UPSTREAM_IO_TIMEOUT = 8.0
ASSETS = MappingProxyType({
    "/index.html": "text/html; charset=utf-8",
    "/styles.css": "text/css; charset=utf-8",
    "/adapter.js": "text/javascript; charset=utf-8",
    "/cockpit.js": "text/javascript; charset=utf-8",
    "/live.js": "text/javascript; charset=utf-8",
    "/owners/ladder_owner.js": "text/javascript; charset=utf-8",
    "/owners/market_view_owner.js": "text/javascript; charset=utf-8",
    "/owners/information_owner.js": "text/javascript; charset=utf-8",
    "/fixtures.js": "text/javascript; charset=utf-8",
    "/preview.js": "text/javascript; charset=utf-8",
    "/BTC15_Cockpit_Preview.html": "text/html; charset=utf-8",
})
# Forward representation and original timing headers. Never forward redirects,
# cookies, authentication challenges, CORS or hop-by-hop connection headers.
RESPONSE_HEADERS = frozenset({
    "content-type", "content-encoding", "content-language", "date", "age",
    "expires", "last-modified", "retry-after", NONCE.lower(),
})


class CandidateServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, public_host=None):
        if public_host is not None and not re.fullmatch(
            r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?(?::[0-9]{1,5})?",
            public_host,
        ):
            raise ValueError("public-host must be a hostname with optional port")
        super().__init__(address, CandidateHandler)
        port = self.server_address[1]
        self.allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if public_host:
            self.allowed_hosts.add(public_host.lower())
        self.shadow_loopback = False


class CandidateHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        # Avoid recording nonces, payloads, browser credentials or query text.
        pass

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            # The existing browser may abort before a response is ready.
            pass

    def handle_expect_100(self):
        self.fail(417, "EXPECTATION_NOT_SUPPORTED")
        return False

    def parse_request(self):
        if not super().parse_request():
            return False
        if self.command != "GET":
            self.fail(405, "GET_ONLY", (("Allow", "GET"),))
            return False
        # Examine the raw request target too: BaseHTTPRequestHandler normalizes
        # a leading // before do_GET. Never let normalization widen the allowlist.
        words = self.requestline.split()
        if len(words) != 3 or words[1] != self.path:
            self.fail(400, "NONCANONICAL_REQUEST")
            return False
        hosts = self.headers.get_all("Host", [])
        host_allowed = len(hosts) == 1 and hosts[0].lower() in self.server.allowed_hosts
        if len(hosts) == 1 and hosts[0].partition(":")[0].lower() == "healthcheck.railway.app":
            # Public, spoofable Host; permit only this source-free static request.
            # Do not add it to allowed_hosts or bypass the remaining validation.
            host_allowed = hosts[0] == "healthcheck.railway.app" and (self.path == "/index.html" or
                (self.server.shadow_loopback and self.path == '/health'))
        if not host_allowed:
            self.fail(400, "HOST_NOT_ALLOWED")
            return False
        for name in ("Authorization", "Proxy-Authorization", "Cookie"):
            if name in self.headers:
                self.fail(400, "CREDENTIALS_NOT_SUPPORTED")
                return False
        if ("Transfer-Encoding" in self.headers or "Expect" in self.headers
                or "Upgrade" in self.headers
                or self.headers.get_all("Content-Length", []) not in ([], ["0"])):
            self.fail(400, "REQUEST_BODY_NOT_SUPPORTED")
            return False
        origin = self.headers.get_all("Origin", [])
        if (len(origin) > 1 or (origin and origin[0] not in {
                "http://" + hosts[0], "https://" + hosts[0]})
                or self.headers.get("Sec-Fetch-Site") == "cross-site"):
            self.fail(403, "SAME_ORIGIN_ONLY")
            return False
        return True

    def reply(self, status, body, headers=()):
        self.close_connection = True
        # send_response() would fabricate a new Date. Preserve upstream Date
        # only when supplied; Content-Length is wire framing, not source data.
        self.send_response_only(status)
        for key, value in headers:
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def fail(self, status, code, headers=()):
        # Deliberately no schema/status/served_ts/expires_at/nonce or old body.
        self.reply(status, ('{"error":"' + code + '"}\n').encode("ascii"),
                   (("Content-Type", "application/json"), *headers))

    def send_error(self, code, message=None, explain=None):
        self.fail(code, "INVALID_HTTP_REQUEST")

    def do_GET(self):
        # Same-origin, bounded client display diagnostics. No user data,
        # credential or actionable source enters this diagnostic.
        report = re.fullmatch(r"/client-diagnostic\?code=([A-Z0-9_]{1,64})", self.path)
        if report:
            code = report.group(1)
            now = time.monotonic()
            with _SOURCE_HEALTH_LOCK:
                tag = "client_" + code
                if now - _SOURCE_HEALTH_LAST.get(tag, 0) >= 12:
                    _SOURCE_HEALTH_LAST[tag] = now
                    print("BTC15 LIVE COCKPIT CLIENT | " + code, flush=True)
            self.reply(204, b"")
            return
        route = self.path
        if route in ("/", "/?mode=fixture", "/?mode=live",
                     "/index.html?mode=fixture", "/index.html?mode=live"):
            route = "/index.html"
        nonces = self.headers.get_all(NONCE, [])
        if (len(nonces) > 1 or (nonces and (
                route != "/information" or not re.fullmatch("[0-9a-f]{32}", nonces[0])))):
            self.fail(400, "INVALID_INFORMATION_NONCE")
            return
        if route in MAIN_PATHS:
            self.relay(route, nonces[0] if nonces else None)
        elif route in ASSETS:
            asset = ROOT / route[1:]
            # Serve exactly this candidate asset, never a directory or symlink.
            if asset.resolve() != asset or not asset.is_file():
                self.fail(404, "ASSET_UNAVAILABLE")
                return
            try:
                body = asset.read_bytes()
            except OSError:
                self.fail(503, "ASSET_UNAVAILABLE")
                return
            self.reply(200, body, (("Content-Type", ASSETS[route]),))
        else:
            self.fail(404, "ROUTE_NOT_ALLOWED")

    def relay(self, route, nonce):
        headers = {"Accept": "application/json", "Accept-Encoding": "identity",
                   "Cache-Control": "no-store", "Pragma": "no-cache"}
        if nonce is not None:
            headers[NONCE] = nonce
        # Direct TLS with certificate verification; no environment proxy,
        # credentials, redirects, configurable upstream or retry mechanism.
        connection = (http.client.HTTPConnection('127.0.0.1', 8765, timeout=UPSTREAM_IO_TIMEOUT)
                      if self.server.shadow_loopback else
                      http.client.HTTPSConnection(MAIN_HOST, timeout=UPSTREAM_IO_TIMEOUT))
        try:
            connection.request("GET", route, headers=headers)
            response = connection.getresponse()
            status = response.status
            body = response.read()
            if not 200 <= status <= 599:
                raise http.client.HTTPException("Invalid final upstream status")
            forwarded = [(key, value) for key, value in response.getheaders()
                         if key.lower() in RESPONSE_HEADERS
                         and (key.lower() != NONCE.lower() or route == "/information")]
            # Do not turn malformed header framing into downstream headers.
            if any("\r" in value or "\n" in value for _, value in forwarded):
                raise http.client.HTTPException("Invalid upstream header")
        except TimeoutError:
            self.fail(504, "UPSTREAM_TIMEOUT")
            return
        except (OSError, http.client.HTTPException):
            self.fail(502, "UPSTREAM_TRANSPORT_FAILURE")
            return
        finally:
            connection.close()
        # Inspect responses on the actual live product path. HTTP 200 alone is
        # not proof of qualified data. This reports only public status/identity;
        # it neither retains payloads nor changes timestamps or action authority.
        if route in MAIN_PATHS:
            try:
                decoded = json.loads(body)
                summary = {
                    "route": route, "http": status, "bytes": len(body),
                    "schema": decoded.get("schema"),
                    "status": decoded.get("status"),
                    "reason": decoded.get("reason"),
                    "contract": (decoded.get("official_identity") or {}).get("contract")
                        or decoded.get("contract"),
                }
                if route == "/ladders":
                    summary["final"] = (decoded.get("final") or {}).get("state")
                    summary["early"] = (decoded.get("early") or {}).get("guidance")
                    summary["published_ts"] = decoded.get("published_ts")
                    summary["expires_at"] = decoded.get("expires_at")
                    summary["source_health"] = (decoded.get("delivery") or {}).get("quote")
                elif route == "/ladders/quotes":
                    summary["quote_source_ts"] = decoded.get("exchange_ts")
                elif route == "/dashboard_state.json":
                    summary["source_ts"] = decoded.get("source_timestamp_utc")
                    summary["generated_utc"] = decoded.get("generated_utc")
                    summary["paired_quotes"] = (decoded.get("health") or {}).get("paired_quotes")
                    summary["brti_ready"] = (decoded.get("market") or {}).get("brti_ready")
                elif route == "/information":
                    summary["checked_ts"] = decoded.get("checked_ts")
                now = time.monotonic()
                with _SOURCE_HEALTH_LOCK:
                    prior = _SOURCE_HEALTH_LAST.get(route, 0)
                    if now - prior >= 12:
                        _SOURCE_HEALTH_LAST[route] = now
                        print("BTC15 LIVE COCKPIT SOURCE | " + json.dumps(summary, separators=(",", ":")), flush=True)
            except (ValueError, TypeError, AttributeError):
                with _SOURCE_HEALTH_LOCK:
                    now = time.monotonic()
                    if now - _SOURCE_HEALTH_LAST.get(route, 0) >= 12:
                        _SOURCE_HEALTH_LAST[route] = now
                        print("BTC15 LIVE COCKPIT SOURCE | " + json.dumps({
                            "route": route, "http": status, "bytes": len(body),
                            "status": "INVALID_OR_NONJSON_SOURCE"
                        }), flush=True)
        self.reply(status, body, forwarded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--public-host", help="Explicit inbound Host allowed by a future HTTPS proxy")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    try:
        host = CandidateServer((args.bind, args.port), args.public_host)
    except ValueError as error:
        parser.error(str(error))
    print(f"BTC15 isolated candidate: http://127.0.0.1:{args.port}/?mode=fixture", flush=True)
    print("SIGNAL-ONLY / NO ORDERS. Live mode requires separate delivery authorization.", flush=True)
    try:
        host.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        host.server_close()


if __name__ == "__main__":
    main()
