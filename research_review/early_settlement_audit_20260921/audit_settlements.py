#!/usr/bin/env python3
"""Offline settlement audit. Never runs a detector, searches parameters or sends orders."""
import csv
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parent
SOURCE_COMMIT = '543e7d960f1b8aeb9f7c7de2645f46d5b1e181ab'
REPO = 'yz272n2tpf-lab/Btc-15min-bot'
CALLS_SHA = '7b26852ee6b148761003fee6fa8ac90ba2d19bee5e78774f7800f91d126e6eb1'
MEMBERSHIP_SHA = '5bfd82ad058078041f654efbd568f459dc14a79a5b10c5b8850e23e5cdb85dc4'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def read(name):
    return json.loads((ROOT / name).read_text())

def write(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')

def stats(rows):
    correct = sum(r['verdict'] == 'CORRECT' for r in rows)
    wrong = sum(r['verdict'] == 'WRONG' for r in rows)
    settled = correct + wrong
    return {'calls': len(rows), 'settled': settled, 'correct': correct,
            'wrong': wrong, 'unresolved': len(rows)-settled,
            'accuracy_percent': 100*correct/settled if settled else None}

def rate(s):
    return f"{s['correct']}/{s['settled']} = {s['accuracy_percent']:.2f}%" if s['settled'] else '0/0 = N/A'

def mmss(seconds):
    seconds = Decimal(str(seconds))
    minutes = int(seconds // 60)
    return f'{minutes}:{seconds-minutes*60:05.2f}'

def main():
    raw = (ROOT / 'inputs/early_entries.json').read_bytes()
    assert sha(raw) == CALLS_SHA, 'Frozen cohort changed'
    assert sha((ROOT / 'inputs/membership.json').read_bytes()) == MEMBERSHIP_SHA
    fingerprints = read('inputs/source_fingerprints.json')
    receipt = read('inputs/github_fingerprint_receipt.json')
    assert json.loads(receipt['content']) == fingerprints
    assert fingerprints['zip_members']['early_entries.json'] == CALLS_SHA
    assert fingerprints['zip_members']['membership.json'] == MEMBERSHIP_SHA
    calls = json.loads(raw)
    eligible = read('inputs/membership.json')['early']['eligible']
    assert len(calls) == len({c['contract'] for c in calls}) == 51
    assert len(eligible) == len(set(eligible)) == 147
    assert {c['contract'] for c in calls} <= set(eligible)
    source_rows = read('inputs/source_call_rows.json')['rows']
    assert len(source_rows) == 51
    retrieval = read('retrieval_manifest.json')
    assert not retrieval['errors'] and len(retrieval['receipts']) == 51
    receipts = {r['contract']: r for r in retrieval['receipts']}
    assert len(receipts) == 51
    with (ROOT / 'inputs/prior_truth_cache.csv').open() as f:
        cache = {r['contract']: r['result'] for r in csv.DictReader(f) if r['contract']}
    cache_source = next(x for x in read('inputs/source_manifest.json')['sources']
                        if x['filename'] == 'subminute_official_truth_cache.csv')
    assert sha((ROOT/'inputs/prior_truth_cache.csv').read_bytes()) == cache_source['sha256']
    rows, mismatches, cache_matches, close_deltas = [], [], [], []
    for index, (c, source) in enumerate(zip(calls, source_rows), 1):
        ticker = c['contract']
        assert source['contract'] == ticker and source['side'] == c['side']
        assert datetime.fromisoformat(source['timestamp_utc']).timestamp() == c['time']
        assert Decimal(source['ask']) == Decimal(str(c['ask']))
        assert Decimal(source['seconds_left']) == Decimal(str(c['seconds_left']))
        raw_market = (ROOT / 'official' / (ticker+'.json')).read_bytes()
        rec = receipts[ticker]
        assert sha(raw_market) == rec['sha256'] and len(raw_market) == rec['bytes']
        assert rec['method'] == 'GET' and rec['http_status'] == 200
        assert rec['url'] == 'https://api.elections.kalshi.com/trade-api/v2/markets/'+ticker
        m = json.loads(raw_market)['market']
        assert m['ticker'] == ticker and m['market_type'] == 'binary'
        assert m['status'] == 'finalized' and m['result'] in ('yes', 'no')
        assert m['title'] == 'BTC price up in next 15 mins?'
        assert m['strike_type'] == 'greater_or_equal' and m['settlement_ts']
        assert Decimal(m['settlement_value_dollars']) == (1 if m['result']=='yes' else 0)
        official_side = {'yes': 'UP', 'no': 'DOWN'}[m['result']]
        verdict = 'CORRECT' if c['side'] == official_side else 'WRONG'
        open_time = datetime.fromisoformat(m['open_time'].replace('Z','+00:00')).timestamp()
        close_time = datetime.fromisoformat(m['close_time'].replace('Z','+00:00')).timestamp()
        assert close_time-open_time == 900 and open_time <= c['time'] < close_time
        close_delta = abs(close_time-c['time']-c['seconds_left'])
        close_deltas.append(close_delta)
        assert close_delta < .011, 'Recorded remaining time disagrees with official contract close'
        if ticker in cache:
            cache_matches.append(ticker)
            if cache[ticker] != m['result']:
                mismatches.append(ticker)
        ask_c = Decimal(source['ask'])*100
        assert ask_c <= 50
        seconds = Decimal(source['seconds_left'])
        rows.append({'call_number': index, 'contract_id': ticker,
                     'early_timestamp_utc': source['timestamp_utc'].replace('+00:00','Z'),
                     'early_side': c['side'], 'entry_ask_dollars': float(Decimal(source['ask'])),
                     'entry_ask_cents': float(ask_c), 'seconds_remaining': float(seconds),
                     'minutes_remaining': float(seconds/60), 'time_remaining_mm_ss': mmss(seconds),
                     'official_kalshi_result': m['result'], 'official_settlement_side': official_side,
                     'verdict': verdict, 'official_status': m['status'],
                     'official_settlement_timestamp_utc': m['settlement_ts'],
                     'official_close_time_utc': m['close_time'],
                     'official_source_url': rec['url'], 'official_response_sha256': rec['sha256'],
                     'retrieved_at_utc': rec['retrieved_at_utc'], 'source_csv_line': source['source_csv_line']})
    assert len(rows) == 51 and len(cache_matches) == 23 and not mismatches
    groups = {
        'UP': [r for r in rows if r['early_side']=='UP'],
        'DOWN': [r for r in rows if r['early_side']=='DOWN'],
        'below_25c': [r for r in rows if Decimal(str(r['entry_ask_cents'])) < 25],
        '25_to_35c': [r for r in rows if 25 <= Decimal(str(r['entry_ask_cents'])) <= 35],
        '36_to_40c': [r for r in rows if 36 <= Decimal(str(r['entry_ask_cents'])) <= 40],
        '41_to_50c': [r for r in rows if 41 <= Decimal(str(r['entry_ask_cents'])) <= 50],
        'at_least_8_minutes': [r for r in rows if r['seconds_remaining'] >= 480],
        '6_to_under_8_minutes': [r for r in rows if 360 <= r['seconds_remaining'] < 480],
    }
    assert sum(len(groups[g]) for g in ['below_25c','25_to_35c','36_to_40c','41_to_50c']) == 51
    assert len(groups['at_least_8_minutes'])+len(groups['6_to_under_8_minutes']) == 51
    summary = {'candidate': 'BREAKOUT_RETEST_RECLAIM_V1', 'source_commit': SOURCE_COMMIT,
               'overall': stats(rows), 'groups': {k:stats(v) for k,v in groups.items()},
               'entry_ask_cents': {'average': mean(r['entry_ask_cents'] for r in rows),
                                   'median': median(r['entry_ask_cents'] for r in rows),
                                   'minimum': min(r['entry_ask_cents'] for r in rows),
                                   'maximum': max(r['entry_ask_cents'] for r in rows)},
               'minutes_remaining': {'average': mean(r['minutes_remaining'] for r in rows),
                                     'median': median(r['minutes_remaining'] for r in rows)},
               'seconds_remaining': {'average': mean(r['seconds_remaining'] for r in rows),
                                     'median': median(r['seconds_remaining'] for r in rows)},
               'coverage': {'called_contracts':51,'original_eligible_contracts':147,
                            'percent':100*51/147},
               'verification': {'unchanged_calls_sha256':CALLS_SHA,
                                'official_finalized_responses':51,'prior_cache_matches':23,
                                'newly_resolved_calls':28,'prior_cache_conflicts':mismatches,
                                'original_snapshot_matches':51,
                                'maximum_remaining_time_difference_seconds':max(close_deltas),
                                'clean_validation_window_accessed':False,
                                'detector_run_or_tuned':False,'orders_created':False}}
    write('per_call.json',rows)
    write('summary.json',summary)
    # CSV is a machine-readable audit export, not a new trading workbook.
    with (ROOT/'per_call.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    s=summary; overall=s['overall'];lines=[
        '# BTC15 EARLY final settlement accuracy audit', '',
        '**EARLY FINAL-ACCURACY AUDIT COMPLETE**',
        f"**{rate(overall)} final-settlement directional accuracy.**", '',
        f"Exact saved candidate: `BREAKOUT_RETEST_RECLAIM_V1`. Source research commit: `{SOURCE_COMMIT}`.",
        'Every one of the original 51 calls is retained in its original order. No rule, threshold or call was changed.', '',
        '| Primary metric | Result |', '|---|---:|',
        '| Officially settled / original calls | 51 / 51 |',
        f"| Correct | {overall['correct']} |",f"| Wrong | {overall['wrong']} |",'| Unresolved | 0 |',
        f"| Final directional accuracy | {rate(overall)} |",
        f"| UP directional accuracy | {rate(s['groups']['UP'])} |",
        f"| DOWN directional accuracy | {rate(s['groups']['DOWN'])} |",
        f"| Mean / median entry ASK, all 51 | {s['entry_ask_cents']['average']:.8f}c / {s['entry_ask_cents']['median']:g}c |",
        '| Entry ASK range / at or below 50c | 2.1–47c / 51 of 51 |',
        f"| Mean / median minutes remaining, all 51 | {s['minutes_remaining']['average']:.8f} / {s['minutes_remaining']['median']:.8f} |",
        f"| Mean / median seconds remaining, all 51 | {s['seconds_remaining']['average']:.8f} / {s['seconds_remaining']['median']:.8f} |",
        '| Original eligible-contract coverage | 51/147 = 34.69% |', '',
        '## Descriptive groups', '',
        '| Group | Calls | Correct / settled = accuracy | Wrong | Unresolved |', '|---|---:|---:|---:|---:|']
    labels={'below_25c':'Below 25c (remaining calls)','25_to_35c':'25–35c','36_to_40c':'36–40c','41_to_50c':'41–50c',
            'at_least_8_minutes':'At least 8 minutes remaining','6_to_under_8_minutes':'6 to under 8 minutes remaining'}
    for key,label in labels.items():
        g=s['groups'][key];lines.append(f"| {label} | {g['calls']} | {rate(g)} | {g['wrong']} | {g['unresolved']} |")
    lines += ['', 'Price bounds are literal inclusive cent bounds, using unrounded recorded ASK. No calls fall in the gaps between these requested bands. The below-25c row accounts for the other 20 calls. Time bands use original recorded seconds. Groups are descriptive only; no subset was selected for a new rule.', '',
        '## Truth, provenance and scope', '',
        'Truth comes from 51 fresh HTTP GET responses from the official Kalshi market endpoint, one for each exact ticker. Each response is finalized, has a settlement timestamp and an explicit yes/no result. YES maps to UP and NO maps to DOWN for these BTC-up binary contracts. This uses the official contract outcome, including its greater-or-equal rule; no settlement was inferred from BTC prices, bids or a model.',
        'All 23 matching old-cache results agree with the fresh official responses. The remaining 28 now have official results. All 51 timestamps, asks and recorded seconds match their historical source snapshot rows. Each official open-to-close interval is 900 seconds; recorded time remaining differs from official close minus call timestamp by less than 0.011 seconds due to source rounding.',
        'The original 147 eligible-contract denominator is taken unchanged from the committed membership evidence. The original nine incomplete-window contracts are not newly excluded by this audit. The detector was not rerun. Neither excursion statistics nor settlement performance were used to select calls.',
        'This is a historical development-cohort audit, not untouched forward validation. The untouched clean post-fix window was not accessed. Production, FINAL, SCALP, BRTI, Kalshi plumbing and thresholds were not modified. SIGNAL ONLY / NO ORDERS.', '',
        '## Reproduce', '',
        'Run `python3 audit_settlements.py` in this directory to reproduce the table and summary offline from frozen inputs and captured official responses. It fails closed on cohort, fingerprint, identity, settlement or timing mismatches. `python3 fetch_official_settlements.py` is an optional fresh official GET-only retrieval for the same 51 tickers; it is not needed to reproduce this captured audit.',
        'The inputs directory retains the exact committed calls and original membership file, the source fingerprints read from GitHub at the stated commit, the prior cache and the 51 matched historical source rows. `retrieval_manifest.json` stores request URLs, fetch times, HTTP metadata and raw-response SHA-256 values. `artifact_fingerprints.json` fingerprints every saved audit artifact except itself.', '',
        '## Every original call', '',
        '| # | Contract ID | EARLY timestamp (UTC) | Side | ASK (c) | Remaining (m:ss) | Official result / side | Verdict |',
        '|---:|---|---|---|---:|---:|---|---|']
    for r in rows:
        lines.append(f"| {r['call_number']} | {r['contract_id']} | {r['early_timestamp_utc']} | {r['early_side']} | {r['entry_ask_cents']:g} | {r['time_remaining_mm_ss']} | [{r['official_kalshi_result']} / {r['official_settlement_side']}]({r['official_source_url']}) | {r['verdict']} |")
    lines += ['', '**EARLY FINAL-ACCURACY AUDIT COMPLETE**', f"**{rate(overall)}.**", '']
    (ROOT/'AUDIT.md').write_text('\n'.join(lines))
    files={str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}
           for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name!='artifact_fingerprints.json'
           and '__pycache__' not in p.parts}
    write('artifact_fingerprints.json',files)
    print(json.dumps(summary,indent=2))

if __name__ == '__main__':
    main()
