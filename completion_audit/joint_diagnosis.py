"""Chronological joint gate diagnosis. Labels score calls; never choose their time.

Research only: this module cannot emit orders or alter runtime policy. Internal
development validation is separate from the untouched registered holdout.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import numpy as np

from joint_extract import epoch

BASE = {
    'early': dict(ask=.45, fair=.75, edge=.08, min_left=2., max_left=10., gap=25.),
    'final': dict(fair=.90, min_left=0., max_left=8., gap_early=75., gap_late=50., ratio=1.),
    'scalp': dict(ask=.70, fair=.52, edge=0., min_left=3., max_left=10., gap=50.),
}


def stats(x):
    x = [float(v) for v in x if v is not None and math.isfinite(float(v))]
    return dict(n=len(x), min=min(x), mean=float(np.mean(x)), median=float(np.median(x)),
                p95=float(np.percentile(x,95)), max=max(x)) if x else dict(n=0)


def load_rows(path):
    with gzip.open(path, 'rt') as f:
        return [json.loads(line) for line in f]


def main_rows(path, start, end):
    selected = {}
    for r in load_rows(path):
        d=r['state']; t=r['receipt_epoch']
        if not start <= t < end or r['sample_kind'] != 'qualified': continue
        key=(d['contract'],d['source_timestamp_utc'])
        if key in selected: continue
        m=d['market']; p=d['early']; timer=d['timer']
        age=t-epoch(d['source_timestamp_utc'])
        selected[key]=dict(t=t, source_t=epoch(d['source_timestamp_utc']), ticker=d['contract'],
            side=p['side'], fair=p['fair'], ask=p['ask'], bid=p['bid'], edge=p['edge'],
            left=timer['minutes_left'], receipt_left=(timer['seconds_left']-age)/60,
            gap=abs(m['btc_gap']) if m['btc_gap'] is not None else None,
            signed_gap=m['btc_gap'], ratio=m['dist_over_range5'], range5=m['range5'],
            volatility=m['vol5'], reversal=m['reversal_state'], target=m['target'],
            brti_authority=m['direct_brti_authority_ready'], brti_agrees=m['direct_brti_agrees'],
            target_agrees=d['final']['conditions']['preferred_matches_target'],
            raw={k:d[k]['ready'] for k in BASE},source_age=age,
            btc15=m['btc_move_15s'],btc30=m['btc_move_30s'],btc60=m['btc_move_60s'])
    return sorted(selected.values(),key=lambda r:r['t'])


def gates(r,lane,p):
    def ge(x,v):return x is not None and math.isfinite(x) and x>=v
    def le(x,v):return x is not None and math.isfinite(x) and x<=v
    g={'side':r['side'] in ('UP','DOWN'),'fair':ge(r['fair'],p['fair']),
       'time':ge(r['left'],p['min_left']) and le(r['left'],p['max_left'])}
    if lane=='final':
        g.update(gap=ge(r['gap'],p['gap_early'] if r['left']>6 else p['gap_late']),
                 ratio=ge(r['ratio'],p['ratio']),target_agrees=r['target_agrees'],
                 brti_authority=r['brti_authority'],brti_agrees=r['brti_agrees'])
    else:
        g.update(ask=le(r['ask'],p['ask']),edge=ge(r['edge'],p['edge']),gap=ge(r['gap'],p['gap']))
    return g


def calls(rows,lane,p,drop=()):
    out={}
    for r in rows:
        g=gates(r,lane,p)
        if r['ticker'] not in out and all(v for k,v in g.items() if k not in drop):
            out[r['ticker']]=r
    return list(out.values())


def paths(inputs):
    out=defaultdict(list)
    for r in inputs:
        t=epoch(r['observed_utc'])
        if (r.get('run_id')=='clean-source-v2-1s-20260923' and r.get('signal_only') is True and r.get('orders') is False
            and r.get('quote_transport')=='timestamped_contiguous_ws' and r.get('quote_validation_utc')==r['observed_utc']
            and 0<=t-r['brti_source_ts_ms']/1000<=5):
            out[r['ticker']].append(dict(r,t=t))
    return out


def metric(entries, markets, scheduled, lane, clean=None, detail=False):
    selected=[]
    for r in entries:
        m=markets.get(r['ticker'])
        if not m or not epoch(m['open_time'])<=r['t']<epoch(m['close_time']):continue
        if r.get('target')!=m['floor_strike']:raise ValueError('Fixed target mismatch')
        c=dict(ticker=r['ticker'],side=r['side'],t=r['t'],ask=r['ask'],fair=r.get('fair'),
               minutes_left=r['receipt_left'],result=m['result'],correct=(r['side']=='UP')==(m['result']=='yes'),
               reversal=r.get('reversal'),volatility=r.get('volatility'))
        if clean is not None:
            horizon={'early':900,'final':900,'scalp':300,'v81':180}[lane]
            end=min(epoch(m['close_time']),r['t']+horizon)
            ps=[x for x in clean.get(r['ticker'],[]) if r['t']<=x['t']<end]
            values=[x[r['side'].lower()+'_bid']-r['ask'] for x in ps]
            c.update(path_samples=len(ps),mfe=max(values,default=None),mae=min(values,default=None),
                     path_max_gap=max([b['t']-a['t'] for a,b in zip(ps,ps[1:])],default=None),
                     first_quote_delay=ps[0]['t']-r['t'] if ps else None,
                     entry_ask_confirmed=ps[0][r['side'].lower()+'_ask']<=r['ask'] if ps else False)
        selected.append(c)
    n=len(selected);wins=sum(c['correct'] for c in selected);unique=len({c['ticker'] for c in selected})
    z=1.96
    interval=None
    if n:
        phat=wins/n;den=1+z*z/n;center=(phat+z*z/(2*n))/den;radius=z*math.sqrt(phat*(1-phat)/n+z*z/(4*n*n))/den
        interval=[center-radius,center+radius]
    result=dict(calls=n,contracts=unique,wins=wins,accuracy=wins/n if n else None,wilson95=interval,
        scheduled=scheduled,official=len(markets),coverage_scheduled=unique/scheduled,
        coverage_official=unique/len(markets) if markets else None,
        sides=dict(Counter(c['side'] for c in selected)),entry=stats(c['ask'] for c in selected),
        entry_le50=sum(c['ask']<=.5 for c in selected),entry_25_35=sum(.25<=c['ask']<=.35 for c in selected),
        minutes_left=stats(c['minutes_left'] for c in selected),
        brier=float(np.mean([(c['fair']-int(c['correct']))**2 for c in selected if c['fair'] is not None])) if n and any(c['fair'] is not None for c in selected) else None)
    if clean is not None:
        path=[c for c in selected if c['path_samples']]
        result.update(mfe=stats(c['mfe'] for c in path),mae=stats(c['mae'] for c in path),
            positive_movement=sum(c['mfe']>0 for c in path),hit8=sum(c['mfe']>=.08-1e-9 for c in path),
            hit10=sum(c['mfe']>=.10-1e-9 for c in path),path_samples=sum(c['path_samples'] for c in path),
            worst_path_gap=max([c['path_max_gap'] for c in path if c['path_max_gap'] is not None],default=None),
            executable_fill_proven=False)
    if detail:result['entries']=selected
    return result


def grid(lane):
    space={
        'early':dict(ask=[.45,.5],fair=[.6,.65,.7,.75],edge=[.08,.15,.2],min_left=[2.,4.],max_left=[10.,12.],gap=[11.,25.]),
        'final':dict(fair=[.8,.85,.875,.9],min_left=[0.,2.],max_left=[6.,8.,10.],gap_early=[50.,75.],gap_late=[25.,50.],ratio=[.5,.75,1.]),
        'scalp':dict(ask=[.45,.5,.6,.7],fair=[.52,.6,.7,.75],edge=[0.,.08,.15],min_left=[2.,3.],max_left=[10.],gap=[11.,25.,50.]),
    }[lane]
    return [dict(zip(space,v)) for v in itertools.product(*space.values())]


def diagnose(rows, markets, scheduled, clean):
    out={}
    for lane in BASE:
        checks=[gates(r,lane,BASE[lane]) for r in rows]
        allkeys=list(checks[0]) if checks else []
        fail=Counter(k for g in checks for k,v in g.items() if not v)
        patterns=Counter('|'.join(k for k,v in g.items() if not v) or 'PASS' for g in checks)
        single=Counter(next(k for k,v in g.items() if not v) for g in checks if sum(not v for v in g.values())==1)
        ablations={k:metric(calls(rows,lane,BASE[lane],drop=(k,)),markets,scheduled,lane) for k in allkeys if k not in ('side','brti_authority','brti_agrees')}
        mismatch=sum(all(g.values())!=r['raw'][lane] for g,r in zip(checks,rows))
        out[lane]=dict(baseline=metric(calls(rows,lane,BASE[lane]),markets,scheduled,lane,clean,True),
            unique_qualified_source_frames=len(rows),failed_gates=dict(fail),sole_blocking_gate=dict(single),
            failure_patterns=dict(patterns),leave_one_strategy_gate_out=ablations,raw_gate_mismatches=mismatch)
    coverage={k:{c['ticker'] for c in v['baseline']['entries']} for k,v in out.items()}
    out['overlap']={a+'+'+b:sorted(coverage[a]&coverage[b]) for a,b in itertools.combinations(BASE,2)}
    out['unique']={a:sorted(coverage[a]-set().union(*(coverage[b] for b in BASE if b!=a))) for a in BASE}
    out['prediction_distribution']=stats(r['fair'] for r in rows)
    out['preferred_price_distribution']=stats(r['ask'] for r in rows)
    out['cheap_preferred_frames']=sum(r['ask'] is not None and r['ask']<=.5 for r in rows)
    out['gap_fair_feature_skew_dollars']=stats(abs(r['gap']-r['ratio']*r['range5']) for r in rows if all(r[k] is not None for k in ('gap','ratio','range5')))
    return out


def batch(rows,markets,scheduled,clean):
    results={}
    for lane in BASE:
        rows_out=[]
        # Different parameters often produce the identical first-call set.
        # Group these signatures instead of treating aliases as independent wins.
        signatures={}
        for p in grid(lane):
            c=calls(rows,lane,p)
            signature=tuple((r['ticker'],r['t'],r['side']) for r in c)
            if signature not in signatures:
                signatures[signature]=dict(parameters=p,equivalent_configurations=0,
                    metrics=metric(c,markets,scheduled,lane,clean))
            signatures[signature]['equivalent_configurations']+=1
        for r in signatures.values():rows_out.append(r)
        rows_out.sort(key=lambda r:(r['metrics']['wins'],r['metrics']['accuracy'] or 0,r['metrics']['contracts']),reverse=True)
        results[lane]=dict(configuration_count=len(grid(lane)),unique_call_sets=len(rows_out),results=rows_out)
    return results


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--markets',type=Path,required=True)
    p.add_argument('--start',required=True);p.add_argument('--end',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--batch',action='store_true');a=p.parse_args()
    start,end=epoch(a.start),epoch(a.end)
    if not epoch('2026-09-24T00:15:00Z')<=start<end<=epoch('2026-09-24T12:15:00Z'):raise ValueError('Only registered development partitions allowed')
    if start<epoch('2026-09-24T07:00:00Z')<end:raise ValueError('Do not pool tuning and internal validation')
    if a.batch and end>epoch('2026-09-24T06:45:00Z'):raise ValueError('Grid may not use validation')
    markets={}
    for f in a.markets.glob('*.json'):
        m=json.loads(f.read_text()).get('market')
        if m and start<=epoch(m['open_time'])<end:markets[m['ticker']]=m
    rows=main_rows(a.data/'main.jsonl.gz',start,end);clean=paths(load_rows(a.data/'inputs.jsonl.gz'))
    scheduled=int((end-start)/900)
    result=dict(start=a.start,end=a.end,phase='development_only',scheduled=scheduled,official=len(markets),
                rows=len(rows),diagnosis=diagnose(rows,markets,scheduled,clean),orders=False)
    if a.batch:result['batch']=batch(rows,markets,scheduled,clean)
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k not in ('diagnosis','batch')}))
    print(json.dumps({k:v['baseline'] for k,v in result['diagnosis'].items() if k in BASE},default=str)[:3000])
