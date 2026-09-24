"""Position-side FINAL protection experiments over the existing frozen replay.

SIGNAL ONLY. No production imports, network, account state or orders. The
already-opened challenge is exploratory; no policy is promoted from this run.
Warning flags and confidence are independent of FINAL entry qualification.
"""
import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from joint_diagnosis import BASE, calls, epoch, load_rows, stats, gates
from structural_batch import DATA, ROOT, enrich, markets, verify_inputs
from structural_path_alignment import native_paths

RULES = {
    'position_identity': 'Original side, ticker, fixed target and entry time never follow the preferred side',
    'confirmation': 'Unchanged production FINAL gates; no cheap-entry constraint on FINAL',
    'deterioration': 'Held-side probability below existing EARLY 0.75 confidence',
    'model_flip': 'Held-side probability <0.5; diagnostic alternative only',
    'authoritative_flip': 'Model flip plus qualified BRTI >=11 dollars against original side',
    'late_guards': 'First causal observation at/below 5m and 3m; signed BTC distance <=75 from frozen specs',
    'profit_warning': 'Existing shadow +10c arm, +6c minimum bid profit, -4c trail; requires deterioration or BRTI disagreement',
    'safety': 'As-of main <=5s, its true BRTI source <=5s, native quotes <=6s, native publication <=3.5s; same ticker/target/window',
    'evaluation': 'Baseline EARLY positions separate from cheap control stress positions; neither rows nor both sides are independent contracts',
    'execution': 'Warnings are not orders, actual fills or certified executable returns',
}


def held_probability(preferred_side, preferred_probability, held_side):
    if held_side not in ('UP', 'DOWN') or preferred_side not in ('UP', 'DOWN'):
        raise ValueError('Direction required')
    if preferred_probability is None or not 0 <= preferred_probability <= 1:
        raise ValueError('Probability required')
    return preferred_probability if held_side == preferred_side else 1-preferred_probability


def position_flags(entry, row, bid, peak_bid):
    if row['ticker'] != entry['ticker'] or row['target'] != entry['target']:
        raise ValueError('Position identity mismatch')
    sign = 1 if entry['side'] == 'UP' else -1
    p = held_probability(row['side'], row['fair'], entry['side'])
    against = row['brti_authority'] and sign*row['brti_gap'] <= -11
    final_ready = all(gates(row, 'final', BASE['final']).values())
    deterioration = p < BASE['early']['fair']
    profit = bid-entry['ask']
    profit_warning = (peak_bid-entry['ask'] >= .10-1e-9 and profit >= .06-1e-9
                      and (deterioration or against)
                      and (profit <= max(.06, peak_bid-entry['ask']-.04)+1e-9 or against))
    return dict(held_probability=p, probability_deterioration=deterioration,
                model_flip=p < .5, authoritative_flip=p < .5 and against,
                profit_warning=profit_warning,
                final_confirmation=final_ready and row['side'] == entry['side'],
                final_opposition=final_ready and row['side'] != entry['side'],
                caution_5m=row['receipt_left'] <= 5 and sign*row['signed_gap'] <= 75,
                guard_3m=row['receipt_left'] <= 3 and sign*row['signed_gap'] <= 75,
                signed_distance=sign*row['signed_gap'])


def qualify_asof(row, quote_time, target):
    return bool(row is not None and row['target'] == target
                and row.get('fair') is not None and 0 <= row['fair'] <= 1
                and 0 <= quote_time-row['t'] <= 5
                and 0 <= quote_time-row['brti_source_t'] <= 5)


def evaluate(entry, main, tape, official):
    if entry['target'] != official['floor_strike']:
        raise ValueError('Official target mismatch')
    close = epoch(official['close_time'])
    if not epoch(official['open_time']) <= entry['t'] < close:
        raise ValueError('Entry outside official window')
    mt = [r['t'] for r in main]
    ps = [q for q in tape if entry['t'] <= q['t'] < close]
    events = {}; counts = Counter(); samples = []; peak = None; previous = entry['t']
    original_correct = (entry['side'] == 'UP') == (official['result'] == 'yes')
    for q in ps:
        if q['target'] != entry['target']:
            raise ValueError('Quote target mismatch')
        bid = q[entry['side'].lower()+'_bid']
        counts['quote_samples'] += 1
        if q['t']-previous > 6: counts['quote_gaps_over6s'] += 1
        previous = q['t']; peak = bid if peak is None else max(peak, bid)
        i = bisect_right(mt, q['t'])-1
        row = main[i] if i >= 0 else None
        if not qualify_asof(row, q['t'], entry['target']):
            counts['probability_unavailable'] += 1; continue
        row = dict(row, receipt_left=(close-q['t'])/60)
        flags = position_flags(entry, row, bid, peak)
        counts['qualified_position_samples'] += 1
        sample = dict(t=q['t'], bid=bid, peak_bid=peak, **flags)
        samples.append(sample)
        for key, value in flags.items():
            if isinstance(value, bool) and value and key not in events:
                events[key] = dict(t=q['t'], seconds_after_entry=q['t']-entry['t'],
                    seconds_to_close=close-q['t'], bid=bid, held_probability=flags['held_probability'],
                    gain=bid-entry['ask'], versus_settlement=bid-float(original_correct))
    gains = [q[entry['side'].lower()+'_bid']-entry['ask'] for q in ps]
    # Warning lead is measured to the first LATER observed loss of entry value.
    # It is an observed crossing, not a claimed continuous path/fill.
    for event in events.values():
        lost = next((q for q in ps if q['t'] > event['t'] and
                     q[entry['side'].lower()+'_bid'] <= entry['ask']), None)
        event['seconds_before_later_observed_breakeven_loss'] = lost['t']-event['t'] if lost else None
    final_opposed_samples = sum(s['final_opposition'] for s in samples)
    return dict(ticker=entry['ticker'], side=entry['side'], t=entry['t'], ask=entry['ask'],
        correct=original_correct, minutes_left=(close-entry['t'])/60, counts=dict(counts),
        events=events, held_probability=stats(s['held_probability'] for s in samples),
        held_probability_brier=sum((s['held_probability']-float(original_correct))**2 for s in samples)/len(samples) if samples else None,
        observed_mfe=max(gains, default=None), observed_mae=min(gains, default=None),
        first_quote_delay=ps[0]['t']-entry['t'] if ps else None,
        entry_ask_confirmed=bool(ps and ps[0]['t']-entry['t'] <= 3 and ps[0][entry['side'].lower()+'_ask'] <= entry['ask']+1e-9),
        final_opposition_samples=final_opposed_samples,
        actual_fill_verified=False, continuous_path_verified=False)


def summarize(entries, main, native, official, scheduled, scalp):
    by=defaultdict(list)
    for r in main: by[r['ticker']].append(r)
    positions=[evaluate(e, by[e['ticker']], native.get(e['ticker'], []), official[e['ticker']]) for e in entries]
    kinds=sorted({k for p in positions for k in p['events']})
    warnings={}
    for key in kinds:
        selected=[p for p in positions if key in p['events']]
        warnings[key]=dict(positions=len(selected), contracts=len({p['ticker'] for p in selected}),
            eventual_winners=sum(p['correct'] for p in selected), eventual_losers=sum(not p['correct'] for p in selected),
            median_seconds_to_close=stats(p['events'][key]['seconds_to_close'] for p in selected),
            observed_bid_gain=stats(p['events'][key]['gain'] for p in selected),
            bid_minus_settlement=stats(p['events'][key]['versus_settlement'] for p in selected),
            lead_to_later_observed_breakeven_loss=stats(p['events'][key]['seconds_before_later_observed_breakeven_loss'] for p in selected))
    conflicts=Counter()
    for e in entries:
        for s in scalp:
            if s['ticker']==e['ticker'] and s['t'] >= e['t']:
                conflicts['same_direction' if s['side']==e['side'] else 'opposite_direction']+=1
    return dict(positions=len(positions), contracts=len({p['ticker'] for p in positions}),
        official=len(official), scheduled=scheduled, wins=sum(p['correct'] for p in positions),
        entry=stats(p['ask'] for p in positions), minutes_left=stats(p['minutes_left'] for p in positions),
        warnings=warnings, later_core_scalp=dict(conflicts), details=positions)


def run(output):
    verify_inputs(); main=enrich(); clocks={}
    for record in load_rows(DATA/'main.jsonl.gz'):
        d=record['state']; m=d.get('market',{}); stamp=d.get('source_timestamp_utc')
        if stamp and m.get('brti_age_seconds') is not None:
            clocks[d['contract'], epoch(stamp)]=epoch(stamp)-m['brti_age_seconds']
    for row in main: row['brti_source_t']=clocks[row['ticker'],row['source_t']]
    native,_=native_paths(load_rows(DATA/'v81.jsonl.gz'))
    previous=json.loads((ROOT/'STRUCTURAL_LEAD_LAG_STRICT_20260924.json').read_text())
    result=dict(rules=RULES, signal_only=True, orders=False, production_promotion=False,
        status='exploratory previously opened challenge, corrected-runtime reserved validation untouched',
        no_new_threshold_search=True)
    for part,start,end,n in [('tuning','2026-09-24T00:15Z','2026-09-24T06:45Z',26),
                             ('validation','2026-09-24T07:00Z','2026-09-24T12:15Z',21)]:
        truth=markets(part); rows=[r for r in main if epoch(start)<=r['t']<epoch(end)]
        actual=calls(rows,'early',BASE['early']); scalp=calls(rows,'scalp',BASE['scalp'])
        control=[dict(e,target=truth[e['ticker']]['floor_strike'])
                 for e in previous[part]['policies']['cheap_first_control']['entries']]
        result[part]={name:summarize(entries, rows, native, truth, n, scalp)
            for name,entries in [('actual_early',actual),('cheap_control_stress_only',control)]}
    result['source_code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with output.open('x') as f: json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({part:{name:{k:v for k,v in m.items() if k!='details'} for name,m in result[part].items()}
                      for part in ('tuning','validation')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,required=True); a=p.parse_args(); run(a.output)
