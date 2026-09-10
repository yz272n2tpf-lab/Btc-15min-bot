#!/usr/bin/env python3
"""Standalone BRTI transport probe.

Research-only. NO ORDERS. Does not touch scalp thresholds or production behavior.
Runs only where existing Kalshi/BRTI auth env vars are already present (e.g. Railway).
Measures primary request success, retry recovery, timeout/http/connection/other failures,
HTTP status codes, invalid payloads, and latency without importing the full scalp collector.
"""

import os
import time
import base64
import argparse
from collections import Counter
from statistics import mean, median

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from brti_resilience_shadow_v2 import BrtiResilienceGuard

EXT = 'https://external-api.kalshi.com'
BRTI_PATH = '/trade-api/v2/cfbenchmarks/values'


def load_auth():
    key_id = os.environ['KALSHI_KEY_ID'].strip()
    key = serialization.load_pem_private_key(
        base64.b64decode(os.environ['KALSHI_PRIVATE_KEY_B64'].strip()),
        password=None,
    )
    return key_id, key


def make_hdr(key_id, key, method, path):
    ts = str(int(time.time() * 1000))
    msg = ts + method.upper() + path
    sig = key.sign(
        msg.encode(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return {
        'KALSHI-ACCESS-KEY': key_id,
        'KALSHI-ACCESS-SIGNATURE': base64.b64encode(sig).decode(),
        'KALSHI-ACCESS-TIMESTAMP': ts,
    }


def parse_value(obj):
    vals = []
    def walk(x):
        if isinstance(x, dict):
            if 'value' in x:
                try:
                    v = float(x.get('value'))
                    if 1000 < v < 1_000_000:
                        vals.append(v)
                except (TypeError, ValueError):
                    pass
            for y in x.values():
                walk(y)
        elif isinstance(x, list):
            for y in x:
                walk(y)
    walk(obj)
    return vals[-1] if vals else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=int, default=180)
    ap.add_argument('--interval', type=float, default=1.0)
    ap.add_argument('--timeout', type=float, default=1.5)
    ap.add_argument('--retries', type=int, default=4)
    args = ap.parse_args()

    key_id, key = load_auth()
    session = requests.Session()
    guard = BrtiResilienceGuard(retries=args.retries, backoff_s=(0.05, 0.10, 0.20), diagnostic_cache_ttl_s=3.0)
    latencies = []
    invalid_payloads = 0
    values = 0
    http_status = Counter()
    retry_after = Counter()
    started = time.time()
    end_at = started + max(1, args.seconds)

    def primary_once():
        nonlocal invalid_payloads
        t0 = time.monotonic()
        r = session.get(
            EXT + BRTI_PATH,
            headers=make_hdr(key_id, key, 'GET', BRTI_PATH),
            params={'id': 'BRTI', 'maxResolution': 'PER_SECOND'},
            timeout=args.timeout,
        )
        latencies.append((time.monotonic() - t0) * 1000.0)
        http_status[str(r.status_code)] += 1
        if r.status_code >= 400:
            ra = r.headers.get('Retry-After')
            if ra:
                retry_after[str(ra)] += 1
        r.raise_for_status()
        v = parse_value(r.json())
        if v is None:
            invalid_payloads += 1
        return v

    while time.time() < end_at:
        loop_t0 = time.monotonic()
        s = guard.fetch(primary_once)
        if s.clean_for_qualification:
            values += 1
        elapsed = time.monotonic() - loop_t0
        sleep_for = args.interval - elapsed
        if sleep_for > 0:
            time.sleep(sleep_for)

    c = guard.snapshot()
    samples = max(1, c['samples'])
    ordered = sorted(latencies)
    p95 = ordered[min(len(ordered)-1, int(0.95 * (len(ordered)-1)))] if ordered else 0.0

    print('BRTI_PROBE_RESULT')
    print(f'duration_s={time.time()-started:.1f}')
    print(f'samples={c["samples"]}')
    print(f'clean={c["primary_ok"]} clean_rate={100*c["primary_ok"]/samples:.2f}%')
    print(f'retry_recovered={c["recovered_by_retry"]}')
    print(f'missing={c["primary_missing"]} errors={c["primary_error"]}')
    print(f'timeout={c.get("error_timeout",0)} http={c.get("error_http",0)} connection={c.get("error_connection",0)} other={c.get("error_other",0)}')
    print(f'http_statuses={dict(sorted(http_status.items()))}')
    print(f'retry_after={dict(sorted(retry_after.items()))}')
    print(f'invalid_payloads={invalid_payloads}')
    print(f'requests={len(latencies)}')
    if latencies:
        print(f'latency_ms_mean={mean(latencies):.1f} median={median(latencies):.1f} p95={p95:.1f} max={max(latencies):.1f}')
    print(guard.compact_stats())


if __name__ == '__main__':
    main()
