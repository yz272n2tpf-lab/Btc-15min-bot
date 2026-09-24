"""V8.1 telemetry replay on its actual timestamped inputs, not REST quotes.

One entry per contract/side is used for comparable opportunity denominators;
this is not a replay of every reentry/position lifecycle or a net P&L claim.
"""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import itertools
import json
from pathlib import Path
import argparse

from joint_diagnosis import load_rows,epoch,paths,metric,stats

CORE={'btc5':20.,'btc15':25.,'brti5':15.,'brti15':5.,'accel':10.,'btc30':0.}
SURGE={'btc5':25.,'btc15':22.,'brti5':25.,'brti15':15.,'accel':18.,'btc30':0.}
BASE=dict(scale=1.,ask5=.005,ask15=.015,confirm=2,structure=True)


def rows(path,start,end):
    result=[];seen=set();reasons=Counter();bad=Counter()
    for src in load_rows(path):
        d=src['state'];t=src['receipt_epoch']
        if not start<=t<end:continue
        reasons[d.get('primary_wait_reason')]+=1
        p=d.get('input_provenance') or {};q=p.get('quote') or {};b=p.get('brti') or {}
        try:
            good=(p['schema']=='V81_TIMESTAMPED_INPUTS_V1' and p['orders'] is False and p['signal_only'] is True
                and p['ticker']==d['contract']==q['ticker'] and p['open_ts']<=t<p['close_ts']
                and p['close_ts']-p['open_ts']==900 and q['transport']=='timestamped_contiguous_ws'
                and 0<=t-q['source_ts_ms']/1000<=6 and 0<=t-b['source_ts_ms']/1000<=5
                and b['status']=='PRIMARY_OK' and b['clean_for_qualification'] is True
                and 0<=t-epoch(d['generated_utc'])<=3.5)
            btc_age=t-epoch(p['btc_source_utc'])
        except (KeyError,TypeError,ValueError):good=False;btc_age=None
        if not good:bad['unqualified_source_or_publication']+=1;continue
        if btc_age is None or not 0<=btc_age<=10:bad['btc_source_over_10s_or_future']+=1
        key=(d['contract'],q['validated_at_ms'])
        if key in seen:continue
        seen.add(key)
        for diag in d.get('diagnostics',[]):
            if not diag.get('in_30_45_band'):continue
            side=diag['side'];left=(p['close_ts']-q['validated_at_ms']/1000)/60
            result.append(dict(diag,t=t,source_t=q['validated_at_ms']/1000,ticker=d['contract'],target=p['target'],
                fair=None,bid=q[side.lower()+'_bid'],left=left,receipt_left=(p['close_ts']-t)/60,
                btc_age=btc_age))
    return result,dict(reasons),dict(bad)


def gates(r,p):
    def ge(k,x):return r.get(k) is not None and r[k]>=x
    def le(k,x):return r.get(k) is not None and r[k]<=x
    def route(floors):return all(ge(k,v*p['scale'] if v>0 else v) for k,v in floors.items())
    return dict(features=r['features_ready'],brti_features=r['brti_fresh'],
        left=r['left']>=2.,btc5=ge('btc5',10),btc15=ge('btc15',15),brti5=ge('brti5',8),
        accel=ge('accel',4),ask5=le('ask5',p['ask5']),ask15=le('ask15',p['ask15']),
        structure=(r['structure_ok'] or not p['structure']),route=route(CORE) or route(SURGE))


def candidates(data,p,drop=()):
    queues=defaultdict(list);called=set();out=[]
    for r in data:
        k=(r['ticker'],r['side']);g=gates(r,p)
        ok=all(v for key,v in g.items() if key not in drop)
        # Conservative confirmation: consecutive observed qualified ticks, no
        # reused cached frame; reset on an observed rejection or a >4s gap.
        queue=queues[k];queue[:]=[v for v in queue if r['source_t']-v<=4]
        if not ok:queue.clear();continue
        queue.append(r['source_t'])
        if len(queue)>=p['confirm'] and k not in called:
            called.add(k);out.append(r)
    return out


def grid():
    space=dict(scale=[.5,.75,1.],ask5=[.005,.015,.03],ask15=[.015,.03,.05],confirm=[1,2],structure=[True])
    return [dict(zip(space,v)) for v in itertools.product(*space.values())]


def run(data,markets,scheduled,clean,batch=True):
    gs=[gates(r,BASE) for r in data];keys=list(gs[0]) if gs else []
    result=dict(in_band_source_frames=len(data),features_ready=sum(r['features_ready'] for r in data),
       failed_gates=dict(Counter(k for g in gs for k,v in g.items() if not v)),
       sole_blocking_gate=dict(Counter(next(k for k,v in g.items() if not v) for g in gs if sum(not v for v in g.values())==1)),
       failure_patterns=dict(Counter('|'.join(k for k,v in g.items() if not v) or 'PASS' for g in gs)),
       features={k:stats(r[k] for r in data) for k in ['btc5','btc15','btc30','brti5','brti15','accel','ask5','ask15','evidence_ratio']},
       baseline=metric(candidates(data,BASE),markets,scheduled,'v81',clean,True),
       leave_one_strategy_gate_out={k:metric(candidates(data,BASE,drop=(k,)),markets,scheduled,'v81',clean) for k in keys if k not in ['features','brti_features']})
    if batch:
        signatures={}
        for p in grid():
            entries=candidates(data,p);sig=tuple((r['ticker'],r['side'],r['t']) for r in entries)
            if sig not in signatures:signatures[sig]=dict(parameters=p,equivalent_configurations=0,metrics=metric(entries,markets,scheduled,'v81',clean))
            signatures[sig]['equivalent_configurations']+=1
        result['batch']=dict(configuration_count=len(grid()),unique_call_sets=len(signatures),results=list(signatures.values()))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--markets',type=Path,required=True)
    p.add_argument('--start',required=True);p.add_argument('--end',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--batch',action='store_true');a=p.parse_args();start,end=epoch(a.start),epoch(a.end)
    if not epoch('2026-09-24T00:15:00Z')<=start<end<=epoch('2026-09-24T12:15:00Z'):raise ValueError('Only registered development partitions')
    if a.batch and end>epoch('2026-09-24T06:45:00Z'):raise ValueError('No validation tuning')
    markets={}
    for f in a.markets.glob('*.json'):
        m=json.loads(f.read_text()).get('market')
        if m and start<=epoch(m['open_time'])<end:markets[m['ticker']]=m
    data,reasons,bad=rows(a.data/'v81.jsonl.gz',start,end);clean=paths(load_rows(a.data/'inputs.jsonl.gz'))
    result=run(data,markets,int((end-start)/900),clean,a.batch)
    result.update(wait_reasons=reasons,source_rejections=bad,phase='development_only',orders=False)
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k in ('in_band_source_frames','features_ready','failed_gates','sole_blocking_gate','baseline','source_rejections')}))
