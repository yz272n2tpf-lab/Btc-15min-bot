"""Bounded, identity-checked development extraction; no labels or network calls."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

from common_journal import scan
from btc15_qualified_forward_observer_v1 import observation

RUN = 'clean-source-v2-1s-20260923'
START = '2026-09-24T00:15:00+00:00'
END = '2026-09-24T12:15:00+00:00'


def epoch(v):
    return datetime.fromisoformat(v.replace('Z', '+00:00')).timestamp()


def extract(path, out):
    out.mkdir(parents=True, exist_ok=True)
    start, end = epoch(START), epoch(END)
    counters = defaultdict(Counter)
    gaps, previous = defaultdict(list), {}
    ages = defaultdict(list)
    seen = defaultdict(set)
    damage, member_count, records = [], 0, Counter()
    streams = {k: gzip.open(out / (k + '.jsonl.gz'), 'xt') for k in ('main', 'v81', 'inputs')}
    first = last = None
    def write(k, r):
        streams[k].write(json.dumps(r, separators=(',', ':'), allow_nan=False) + '\n')
        records[k] += 1
    try:
        for member in scan(path, damage):
            row = member['record']; member_count += 1
            if row.get('run_id') != RUN:
                raise ValueError('Mixed collector run')
            when = row.get('recorded_utc', row.get('observed_utc'))
            if when:
                first = min(first, when) if first else when
                last = max(last, when) if last else when
            if row['record_type'] == 'SNAPSHOT_INPUT':
                if start <= epoch(row['observed_utc']) < end:
                    write('inputs', row)
                continue
            if row['record_type'] != 'OBSERVATION':
                continue
            for src in row['sources']:
                began = epoch(src['request_started_utc'])
                if not start <= began < end:
                    continue
                service = src['service']; c = counters[service]
                c['samples'] += 1
                c['http_failures'] += src.get('http_status') != 200
                if service in previous:
                    gaps[service].append(began - previous[service])
                previous[service] = began
                state = src.get('state')
                if not isinstance(state, dict):
                    c['missing_state'] += 1
                    continue
                state.pop('chart', None)
                received = epoch(src['response_received_utc'])
                if service == 'main':
                    o = observation(state, datetime.fromtimestamp(received, timezone.utc))
                    c['usable'] += o['usable_frame']; c['brti_fresh'] += o['brti_fresh']
                    c['qualified'] += bool(o['usable_frame'] and o['brti_fresh'])
                    for lane in ('early', 'final', 'scalp'):
                        c[lane + '_raw'] += state.get(lane, {}).get('ready') is True
                    key = (state.get('contract'), state.get('source_timestamp_utc'))
                    source_age = received - epoch(key[1]) if key[1] else None
                    if source_age is not None:
                        ages['main_source'].append(source_age)
                        age = state.get('market', {}).get('brti_age_seconds')
                        if age is not None:
                            ages['main_brti'].append(source_age + age)
                    # First appearance AND first qualified receipt, never create
                    # a synthetic receipt or refresh a retained source timestamp.
                    kind = 'qualified' if o['usable_frame'] and o['brti_fresh'] else 'unqualified'
                    if (key, kind) not in seen[service]:
                        seen[service].add((key, kind))
                        write('main', dict(src, qualification=o, receipt_epoch=received, sample_kind=kind))
                elif service == 'v81':
                    c['active'] += state.get('active') is True
                    c['reason:' + str(state.get('primary_wait_reason'))] += 1
                    key = (state.get('generated_utc'), state.get('contract'), state.get('primary_wait_reason'),
                           (state.get('input_provenance') or {}).get('quote', {}).get('sequence'))
                    if key not in seen[service]:
                        seen[service].add(key)
                        write('v81', dict(src, receipt_epoch=received))
                elif service == 'owner':
                    c['status:' + str(state.get('status'))] += 1
                    age_ms = state.get('age_ms')
                    if age_ms is not None:
                        ages['owner_brti'].append(age_ms / 1000)
                    c['http_429_max'] = max(c['http_429_max'], state.get('http_429', 0) or 0)
                    c['errors_max'] = max(c['errors_max'], state.get('upstream_errors', 0) or 0)
    finally:
        for stream in streams.values():
            stream.close()
    import numpy as np
    def stats(values):
        return dict(n=len(values), min=min(values), median=float(np.median(values)),
                    p95=float(np.percentile(values, 95)), max=max(values)) if values else {}
    result = dict(run_id=RUN, start=START, end=END, journal_bytes=path.stat().st_size,
                  journal_sha256=hashlib.file_digest(path.open('rb'), 'sha256').hexdigest(),
                  members_crc_checked=member_count, damage=damage, first=first, last=last,
                  samples={k:dict(v) for k,v in counters.items()}, derived_rows=dict(records),
                  request_gaps={k:stats(v) for k,v in gaps.items()},
                  gaps_over_1_5={k:sum(x > 1.5 for x in v) for k,v in gaps.items()},
                  ages={k:stats(v) for k,v in ages.items()}, continuous_availability=False, orders=False)
    with (out / 'integrity.json').open('x') as f:
        json.dump(result, f, indent=2)
    if damage:
        raise ValueError('Journal damage; derived analysis must not proceed: ' + str(damage))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('path', type=Path); p.add_argument('out', type=Path)
    a = p.parse_args(); extract(a.path, a.out)
