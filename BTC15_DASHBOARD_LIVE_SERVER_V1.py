"""
BTC15_DASHBOARD_LIVE_SERVER_V1.py

Read-only HTTP dashboard server for the BTC 15-minute Kalshi bot.

This server:
    - Uses only the Python standard library (http.server.ThreadingHTTPServer).
    - Serves the static dashboard HTML at "/".
    - Serves the current bot state as JSON at "/dashboard_state.json".
    - Serves a simple health check at "/health".
    - Contains NO order/trading logic. It is strictly read-only.

Usage:
    python BTC15_DASHBOARD_LIVE_SERVER_V1.py
    python BTC15_DASHBOARD_LIVE_SERVER_V1.py --self-test
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HTML_FILENAME = "BTC_Kalshi_App_Live_v13.html"
HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), HTML_FILENAME)

DEFAULT_PORT = 8080

try:
    from BTC15_DASHBOARD_STATE_V2 import build_state
except Exception as import_error:
    build_state = None
    _BUILD_STATE_IMPORT_ERROR = import_error
else:
    _BUILD_STATE_IMPORT_ERROR = None


def _get_state_dict():
    """
    Calls build_state() and returns a JSON-serializable dict.
    Raises a RuntimeError with a clear message if build_state is unavailable
    or does not behave as expected.
    """
    if build_state is None:
        raise RuntimeError(
            "BTC15_DASHBOARD_STATE_V2.build_state is not available: %r"
            % (_BUILD_STATE_IMPORT_ERROR,)
        )

    state = build_state()

    if isinstance(state, dict):
        return state

    if hasattr(state, "to_dict"):
        return state.to_dict()

    if hasattr(state, "__dict__"):
        return dict(state.__dict__)

    raise RuntimeError(
        "build_state() returned an object that cannot be converted to JSON: %r"
        % (type(state),)
    )


def _get_state_object():
    """
    Calls build_state() and returns the raw object (used by self-test to
    inspect nested attributes like .safety.read_only).
    """
    if build_state is None:
        raise RuntimeError(
            "BTC15_DASHBOARD_STATE_V2.build_state is not available: %r"
            % (_BUILD_STATE_IMPORT_ERROR,)
        )
    return build_state()


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server_version = "BTC15DashboardHTTP/1.0"

    def log_message(self, format_str, *args):
        message = "%s - - [%s] %s" % (
            self.address_string(),
            self.log_date_time_string(),
            format_str % args,
        )
        sys.stdout.write(message + "\n")
        sys.stdout.flush()

    def _log_request(self, status_code):
        print(
            "HTTP %s %s -> %s"
            % (self.command, self.path, status_code)
        )

    def _send_json(self, payload, status_code=200, no_cache=False):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if no_cache:
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(body)
        self._log_request(status_code)

    def _send_html_file(self):
        if not os.path.isfile(HTML_PATH):
            self._send_json(
                {"error": "dashboard html file not found", "path": HTML_PATH},
                status_code=404,
            )
            return

        try:
            with open(HTML_PATH, "rb") as html_file:
                body = html_file.read()
        except Exception as read_error:
            self._send_json(
                {"error": "failed to read dashboard html file", "detail": str(read_error)},
                status_code=500,
            )
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self._log_request(200)

    def _send_dashboard_state(self):
        try:
            state_dict = _get_state_dict()
        except Exception as state_error:
            self._send_json(
                {"error": "failed to build dashboard state", "detail": str(state_error)},
                status_code=500,
                no_cache=True,
            )
            return

        self._send_json(state_dict, status_code=200, no_cache=True)

    def _send_health(self):
        self._send_json({"ok": True, "read_only": True}, status_code=200)

    def do_GET(self):
        if self.path == "/" or self.path == "":
            self._send_html_file()
        elif self.path == "/dashboard_state.json":
            self._send_dashboard_state()
        elif self.path == "/health":
            self._send_health()
        else:
            self._send_json({"error": "not found", "path": self.path}, status_code=404)


def run_server():
    port = DEFAULT_PORT
    port_env = os.environ.get("PORT")
    if port_env:
        try:
            port = int(port_env)
        except ValueError:
            print(
                "WARNING: invalid PORT environment variable %r, falling back to %s"
                % (port_env, DEFAULT_PORT)
            )
            port = DEFAULT_PORT

    address = ("0.0.0.0", port)
    server = ThreadingHTTPServer(address, DashboardRequestHandler)
    print("BTC15 dashboard server listening on 0.0.0.0:%s (read-only)" % port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down BTC15 dashboard server")
    finally:
        server.server_close()


def run_self_test():
    print("SELF-TEST: starting")

    if not os.path.isfile(HTML_PATH):
        raise AssertionError(
            "SELF-TEST FAILED: dashboard html file not found at %s" % HTML_PATH
        )
    print("SELF-TEST: html file found at %s" % HTML_PATH)

    state = _get_state_object()
    print("SELF-TEST: build_state() executed successfully")

    if isinstance(state, dict):
        safety = state.get("safety")
        if safety is None:
            raise AssertionError("SELF-TEST FAILED: state has no 'safety' key")
        if isinstance(safety, dict):
            read_only = safety.get("read_only")
            orders_enabled = safety.get("orders_enabled")
        else:
            read_only = getattr(safety, "read_only", None)
            orders_enabled = getattr(safety, "orders_enabled", None)
    else:
        safety = getattr(state, "safety", None)
        if safety is None:
            raise AssertionError("SELF-TEST FAILED: state has no 'safety' attribute")
        read_only = getattr(safety, "read_only", None)
        orders_enabled = getattr(safety, "orders_enabled", None)

    if read_only is not True:
        raise AssertionError(
            "SELF-TEST FAILED: build_state.safety.read_only must be True, got %r"
            % (read_only,)
        )
    print("SELF-TEST: safety.read_only == True")

    if orders_enabled is not False:
        raise AssertionError(
            "SELF-TEST FAILED: build_state.safety.orders_enabled must be False, got %r"
            % (orders_enabled,)
        )
    print("SELF-TEST: safety.orders_enabled == False")

    print("SELF-TEST: PASS")


def main():
    if "--self-test" in sys.argv:
        run_self_test()
        return

    run_server()


if __name__ == "__main__":
    main()
