"""Summarize saved read-only observations; never promote a strategy or place orders.

External HTTP samples are incomplete. Qualification is reconstructed at the
server's generated timestamp, not asserted to be actual browser delivery.
Official market JSON files are used only as retrospective labels.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btc15_qualified_forward_observer_v1 import observation


def stamp(value):
    d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('naive timestamp')
    return d


def summary(values):
    a = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not a:
        return {'n': 0}
    return {'n': len(a), 'mean': statistics.mean(a), 'median': statistics.median(a),
            'min': a[0], 'p95': a[math.ceil(.95 * len(a)) - 1], 'max': a[-1]}


def wilson(correct, total):
    if not total:
        return None
    p = correct / total
    z = 1.959963984540054
    denominator = 1 + z*z/total
    center = (p + z*z/(2*total)) / denominator
    half = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / denominator
    return [center-half, center+half]


def analyze(records, start, end, official):
    counts = Counter()
    owner = defaultdict(list)
    main = []
    v81 = []
    serial = []
    for record in records:
        received = datetime.fromtimestamp(record['start_epoch'], timezone.utc)
        if not start <= received < end:
            continue
        service = record['service']
        counts[service + '_requests'] += 1
        data = record.get('state')
        if not isinstance(data, dict):
            counts[service + '_unavailable'] += 1
            continue
        if service == 'owner':
            owner[data.get('owner_epoch')].append(data)
        elif service == 'main':
            now = stamp(data['generated_utc'])
            source = stamp(data['source_timestamp_utc'])
            if not start <= source < end:
                counts['main_outside_source_window'] += 1
                continue
            qualified = observation(data, now=now)
            main.append((now, data, qualified))
        elif service == 'v81':
            v81.append(data)
        elif service == 'scalp':
            serial.append(data)
    main.sort(key=lambda x: x[0])
    owner_stats = {}
    for epoch, rows in owner.items():
        rows.sort(key=lambda r: r['server_timestamp_utc'])
        first, last = rows[0], rows[-1]
        owner_stats[epoch] = {
            'samples': len(rows),
            'qualified_samples': sum(r.get('clean_for_qualification') is True
                                     and r.get('status') == 'PRIMARY_OK'
                                     and 0 <= r.get('age_ms', math.inf) <= 5000 for r in rows),
            'source_age_seconds': summary(r.get('age_ms', math.inf)/1000 for r in rows),
            'observed_counter_deltas': {k: last.get(k, 0)-first.get(k, 0)
                                       for k in ('upstream_attempts', 'upstream_ok', 'http_429', 'upstream_errors')},
            'first_counter_values': {k: first.get(k) for k in ('upstream_attempts', 'upstream_ok', 'http_429')},
            'last_counter_values': {k: last.get(k) for k in ('upstream_attempts', 'upstream_ok', 'http_429')},
        }
    # Only official contracts opening inside the predeclared window enter the denominator.
    universe = {m['ticker']: m for m in official
                if start <= stamp(m['open_time']) < end}
    lanes = {}
    calls = {}
    for lane in ('early', 'final', 'scalp'):
        raw = Counter()
        ui = Counter()
        qualified = {}
        for now, data, obs in main:
            ticker = data.get('contract')
            if ticker not in universe:
                continue
            m = universe[ticker]
            if not stamp(m['open_time']) <= now < stamp(m['close_time']):
                continue
            state = obs['lanes'][lane]
            raw[ticker] += int(state['raw_ready'])
            ui[ticker] += int(state['publication_eligible'])
            if state['source_qualified'] and ticker not in qualified:
                signal = data[lane]
                side = signal.get('side')
                if side not in ('UP', 'DOWN'):
                    continue
                ask = data['market'].get(side.lower() + '_ask')
                if ask is None or not 0 <= ask <= 1:
                    continue
                qualified[ticker] = {
                    'contract': ticker, 'side': side, 'observed_utc': now.isoformat(),
                    'source_timestamp_utc': data['source_timestamp_utc'], 'entry_ask': ask,
                    'minutes_remaining': (stamp(m['close_time']) - now).total_seconds()/60,
                    'confidence': signal.get('confidence', signal.get('fair')),
                    'official_result': m.get('result') if m.get('status') == 'finalized' else None,
                }
        labeled = [c for c in qualified.values() if c['official_result'] in ('yes', 'no')]
        correct = sum((c['side'] == 'UP') == (c['official_result'] == 'yes') for c in labeled)
        confidences = [c for c in labeled if isinstance(c['confidence'], (int, float))
                       and 0 <= c['confidence'] <= 1]
        brier = [ (c['confidence'] - int((c['side']=='UP') == (c['official_result']=='yes')))**2
                  for c in confidences]
        calls[lane] = qualified
        lanes[lane] = {
            'official_universe_n': len(universe), 'raw_ready_contracts': sum(v>0 for v in raw.values()),
            'ui_eligible_contracts': sum(v>0 for v in ui.values()),
            'strict_qualified_contracts': len(qualified),
            'strict_coverage': len(qualified)/len(universe) if universe else None,
            'labeled_calls': len(labeled), 'correct': correct,
            'accuracy': correct/len(labeled) if labeled else None,
            'descriptive_wilson_95_not_serial_adjusted': wilson(correct, len(labeled)),
            'entry_ask': summary(c['entry_ask'] for c in qualified.values()),
            'entry_le_50c': sum(c['entry_ask'] <= .50 for c in qualified.values()),
            'entry_25_to_35c': sum(.25 <= c['entry_ask'] <= .35 for c in qualified.values()),
            'minutes_remaining': summary(c['minutes_remaining'] for c in qualified.values()),
            'brier_mean': statistics.mean(brier) if brier else None,
            'calls': list(qualified.values()),
        }
    overlaps = Counter()
    for ticker in universe:
        overlaps['+'.join(lane for lane in calls if ticker in calls[lane]) or 'NONE'] += 1
    gaps = [(b[0]-a[0]).total_seconds() for a,b in zip(main,main[1:])]
    return {
        'window': {'start': start.isoformat(), 'end': end.isoformat()},
        'qualification_basis': 'reconstructed at server generation; incomplete external samples',
        'counts': dict(counts), 'owner_by_epoch': owner_stats,
        'main': {'samples': len(main), 'usable_frame_samples': sum(o['usable_frame'] for _,_,o in main),
                 'brti_fresh_samples': sum(o['brti_fresh'] for _,_,o in main),
                 'source_age_seconds': summary(o['source_age'] for _,_,o in main),
                 'effective_brti_age_seconds': summary(o['brti_age'] for _,_,o in main),
                 'sampling_gap_seconds': summary(gaps),
                 'signal_only_all': bool(main) and all(d.get('safety',{}).get('read_only') is True
                                        and d.get('safety',{}).get('orders_enabled') is False for _,d,_ in main)},
        'lanes': lanes, 'overlap_counts': dict(overlaps),
        'v81': {'sampled_active_frames': sum(d.get('active') is True for d in v81),
                'last_signal_events': list({json.dumps(d.get('last_signal_event'),sort_keys=True)
                                            for d in v81 if d.get('last_signal_event')})},
        'serial_research': {'sampled_states': dict(Counter(d.get('state') for d in serial)),
                            'sampled_exit_frames': sum(d.get('exit_triggered') is True for d in serial)},
        'certified_performance': False,
        'limits': ['Developmental infrastructure window; not untouched holdout.',
                   'Incomplete HTTP sampling may miss brief signals and excursions.',
                   'Missing official contracts are not a valid complete denominator.',
                   'Core SCALP is distinct from V8.1 and generalized serial research.',
                   'No actual browser delivery, manual trades or net profits verified.'],
    }


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('observations', type=Path)
    p.add_argument('--start', required=True)
    p.add_argument('--end', required=True)
    p.add_argument('--markets', type=Path, nargs='*', default=[])
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    records = [json.loads(line) for line in args.observations.read_text().splitlines()]
    markets = [json.loads(path.read_text()) for path in args.markets]
    result = analyze(records, stamp(args.start), stamp(args.end), [m.get('market',m) for m in markets])
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output': str(args.output), 'samples': result['counts'],
                      'certified_performance': False}))
