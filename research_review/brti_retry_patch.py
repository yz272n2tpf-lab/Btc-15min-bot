"""Offline, hash-pinned draft for the recovered source's BRTI retry loop.

Prints a review diff only. Does not edit, import, execute, or deploy the bot.
Applying this draft requires separate approval for upstream transport changes.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
from pathlib import Path

SOURCE_NAME = 'bot_two_output_build_v4_13_profit_protection_shadow.py'
SOURCE_SHA256 = 'cfe325434e57588a45ea429ca160198da954cd1c739418a2ba7bdfc74e5a6c2c'
POLL_FUNCTION = '''def _brti_poller():
    import random

    global _brti_last_error, _brti_last_error_print
    last_seen_cf_ts = None
    rate_limit_delay_s = BRTI_POLL_SECONDS

    while running:
        cycle = time.monotonic()
        rate_limited = False
        try:
            value, cf_ts = _fetch_direct_brti_once()

            # Keep the original publication timestamp and duplicate handling.
            if last_seen_cf_ts != cf_ts:
                with _brti_lock:
                    _brti_samples.append((cf_ts, value))
                last_seen_cf_ts = cf_ts

            _brti_last_error = None
            rate_limit_delay_s = BRTI_POLL_SECONDS

        except Exception as exc:
            _brti_last_error = f"{type(exc).__name__}: {exc}"
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 429:
                rate_limited = True
                rate_limit_delay_s = min(30.0, rate_limit_delay_s * 2.0)
            else:
                rate_limit_delay_s = BRTI_POLL_SECONDS
            if time.time() - _brti_last_error_print >= 30:
                print("DIRECT BRTI WARNING:", _brti_last_error)
                _brti_last_error_print = time.time()

        elapsed = time.monotonic() - cycle
        if rate_limited:
            # Start backoff after the response, including slow 429 responses.
            time.sleep(rate_limit_delay_s + random.uniform(0.0, 0.25))
        else:
            time.sleep(max(0.05, BRTI_POLL_SECONDS - elapsed))
'''


def draft(source: bytes) -> str:
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('Source fingerprint differs from approved recovery revision')
    text = source.decode('utf-8')
    nodes = [n for n in ast.parse(text).body
             if isinstance(n, ast.FunctionDef) and n.name == '_brti_poller']
    if len(nodes) != 1:
        raise ValueError('Expected exactly one top-level BRTI poller')
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    candidate = ''.join(lines[:node.lineno - 1]) + POLL_FUNCTION + ''.join(lines[node.end_lineno:])
    compile(candidate, SOURCE_NAME, 'exec')
    return candidate


def review_diff(source: bytes) -> str:
    return ''.join(difflib.unified_diff(
        source.decode('utf-8').splitlines(keepends=True),
        draft(source).splitlines(keepends=True),
        fromfile='a/' + SOURCE_NAME, tofile='b/' + SOURCE_NAME))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path,
                        default=Path(__file__).resolve().parents[1] / SOURCE_NAME)
    args = parser.parse_args()
    print(review_diff(args.source.read_bytes()), end='')


if __name__ == '__main__':
    main()
