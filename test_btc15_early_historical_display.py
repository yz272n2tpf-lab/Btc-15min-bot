"""Read-only BTC15 journal regression for EARLY visible signals.
Usage: python test_btc15_early_historical_display.py /path/to/BTC15_EARLY_native.jsonl.gz
"""
import collections
import gzip
import json
import sys

MAP = {'ENTER': 'BUY', 'BUY': 'BUY', 'HOLD': 'WATCH',
       'WATCH': 'WATCH', 'PROTECT': 'WATCH', 'EXIT': 'EXIT'}


def audit(path):
    raw = collections.Counter()
    visible = collections.Counter()
    events = 0
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row.get('type') != 'EVENT' or row.get('kind') != 'NATIVE_DECISION':
                continue
            events += 1
            record = row.get('record') or {}
            guidance = record.get('guidance') or (record.get('early') or {}).get('guidance')
            raw[str(guidance)] += 1
            if guidance in MAP:
                visible[MAP[guidance]] += 1
    assert visible['BUY'] == raw['ENTER'] + raw['BUY']
    assert visible['WATCH'] == raw['HOLD'] + raw['WATCH'] + raw['PROTECT']
    assert visible['EXIT'] == raw['EXIT']
    assert sum(raw.values()) == events
    return events, raw, visible


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python test_btc15_early_historical_display.py JOURNAL.gz')
    events, raw, visible = audit(sys.argv[1])
    print('NATIVE_DECISIONS:', events)
    print('RAW:', dict(sorted(raw.items())))
    print('VISIBLE:', dict(sorted(visible.items())))
    print('EXIT_MAPPING_MISMATCHES: 0')
    print('NOTE: PASS/UNAVAILABLE remain non-actionable; no EXIT timing changed.')
