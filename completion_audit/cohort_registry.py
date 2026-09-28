"""Frozen UTC common-universe accounting; missing slots stay in denominators."""
from datetime import datetime, timedelta, timezone
import hashlib
import json


def utc(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timezone required')
    return parsed.astimezone(timezone.utc)


def validate(manifest):
    registered = utc(manifest['registered_utc'])
    previous = None
    roles = set()
    for window in manifest['windows']:
        start, end = utc(window['start_utc']), utc(window['end_utc'])
        if start <= registered or start >= end:
            raise ValueError('Register future, positive windows only')
        if any(x.minute % 15 or x.second or x.microsecond for x in (start, end)):
            raise ValueError('Window is not aligned to official quarter-hour slots')
        if previous is not None and start < previous:
            raise ValueError('Overlapping roles')
        if window['role'] in roles:
            raise ValueError('Repeated role')
        if int((end-start).total_seconds()/900) != window['scheduled_slots']:
            raise ValueError('Denominator mismatch')
        previous = end
        roles.add(window['role'])
    if manifest['orders'] is not False or manifest['signal_only'] is not True:
        raise ValueError('Signal-only contract required')
    return manifest


def slots(window):
    start, end = utc(window['start_utc']), utc(window['end_utc'])
    while start < end:
        yield start
        start += timedelta(minutes=15)


def registry(window, official, observed_contracts=()):
    """Official results are metadata/labels, never an input for signal selection."""
    by_open = {}
    for item in official:
        ticker = item['ticker']
        if not ticker.startswith('KXBTC15M-'):
            raise ValueError('Wrong market family')
        start, close = utc(item['open_time']), utc(item['close_time'])
        if close - start != timedelta(minutes=15):
            raise ValueError('Unexpected official contract duration')
        if start in by_open and by_open[start]['ticker'] != ticker:
            raise ValueError('Multiple tickers for one scheduled slot')
        by_open[start] = item
    observed = set(observed_contracts)
    result = []
    for start in slots(window):
        item = by_open.get(start)
        ticker = item['ticker'] if item else None
        result.append(dict(open_utc=start.isoformat(), close_utc=(start+timedelta(minutes=15)).isoformat(),
                           ticker=ticker, official_identified=item is not None,
                           observed=ticker in observed if ticker else False,
                           role=window['role'], retained_in_scheduled_denominator=True))
    return result


def identity(manifest):
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
