"""Durable prospective evidence for raw gates versus publication eligibility.

This observes the local dashboard API only. It does not generate signals, label
settlement, change gates or claim a browser actually displayed a signal.
"""
import csv
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from btc15_data_paths_v1 import _btc15_data_root

DATA_ROOT = _btc15_data_root(legacy_cwd_fallback=True)
OUT = DATA_ROOT / 'btc15_qualified_forward_v1.csv'
FIELDS = ['observed_utc', 'source_timestamp_utc', 'contract', 'record_type', 'payload']


def age(raw, now):
    try:
        stamp = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            return math.inf
        return (now - stamp).total_seconds()
    except (ValueError, TypeError):
        return math.inf


def observation(state, now=None):
    now = now or datetime.now(timezone.utc)
    contract = state.get('contract')
    parity, market, safety = (state.get(k) or {} for k in ('parity', 'market', 'safety'))
    source_age = age(state.get('source_timestamp_utc'), now)
    health = state.get('health') or {}
    try:
        remaining = float((state.get('timer') or {}).get('seconds_left')) - source_age
        brti_age = float(market.get('brti_age_seconds')) + source_age
    except (TypeError, ValueError):
        remaining, brti_age = -1., math.inf
    usable = bool(isinstance(contract, str) and contract.startswith('KXBTC15M-')
                  and 0 <= source_age <= 15 and remaining > 0
                  and health.get('paired_quotes') is True
                  and safety.get('read_only') is True and safety.get('orders_enabled') is False
                  and parity.get('status') == 'PASS'
                  and parity.get('contract') == contract and parity.get('api_contract') == contract
                  and 0 <= age(parity.get('timestamp_utc'), now) <= 45)
    try:
        brti_fresh = (market.get('brti_ready') is True and 0 <= brti_age <= 5
                      and math.isfinite(float(market.get('brti_value'))))
    except (TypeError, ValueError):
        brti_fresh = False
    lanes = {}
    for lane in ('early', 'final', 'scalp'):
        raw = state.get(lane) or {}
        # Existing main HTML gates; scalp here is CORE, not the separate V8.1 overlay.
        ui_gate = usable and (brti_fresh if lane == 'final' else True)
        lanes[lane] = dict(raw_ready=raw.get('ready') is True,
                           publication_eligible=ui_gate and raw.get('ready') is True,
                           source_qualified=usable and brti_fresh and raw.get('ready') is True,
                           raw=raw)
    return dict(version=1, observed_utc=now.isoformat(),
                source_timestamp_utc=state.get('source_timestamp_utc'), contract=contract,
                source_age=source_age if math.isfinite(source_age) else None,
                brti_age=brti_age if math.isfinite(brti_age) else None,
                usable_frame=usable, brti_fresh=brti_fresh, lanes=lanes,
                timer=state.get('timer'), market=market, parity=parity,
                signal_only=True, orders=False, actual_browser_delivery_verified=False)


def append(record, path=OUT):
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with path.open('a', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        writer.writerow({k: record.get(k, '') for k in FIELDS[:-1]} | {
            'payload': json.dumps(record, separators=(',', ':'), allow_nan=False)})
        stream.flush()
        os.fsync(stream.fileno())


def main():
    url = 'http://127.0.0.1:' + os.getenv('PORT', '8080') + '/dashboard_state.json'
    while True:
        start = time.monotonic()
        try:
            response = requests.get(url, timeout=2)
            response.raise_for_status()
            record = observation(response.json())
            record['record_type'] = 'OBSERVATION'
        except Exception as exc:
            record = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                          record_type='UNAVAILABLE', error_type=type(exc).__name__,
                          signal_only=True, orders=False)
        append(record)
        time.sleep(max(.1, 5 - (time.monotonic() - start)))

if __name__ == '__main__': main()
