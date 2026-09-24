"""Fixed, dimensionally scaled lead/lag hypotheses; uses existing replay only."""
from bisect import bisect_right
from collections import defaultdict,Counter
import hashlib
import json
import math
from pathlib import Path
import argparse
from scipy.special import ndtr

from structural_batch import DATA,ROOT,enrich,markets,verify_inputs,score_entries
from joint_diagnosis import load_rows,paths,epoch,stats
from joint_v81 import rows as vrows

MODES=('cheap_first_control','price_response_residual','basis_dislocation')


def prepare(vs,main):
    grouped=defaultdict(list)
    for r in main:grouped[r['ticker']].append(r)
    times={k:[x['t'] for x in rs] for k,rs in grouped.items()}
    out=[];missing=Counter()
    for r in vs:
        if not r['features_ready'] or not r['brti_fresh'] or r.get('btc_age') is None or not 0<=r['btc_age']<=10:
            missing['source_or_features']+=1;continue
        if not 2<=r['receipt_left']<=10:continue
        rs=grouped.get(r['ticker'],[]);i=bisect_right(times.get(r['ticker'],[]),r['t'])-1
        if i<0 or r['t']-rs[i]['t']>5:missing['main_asof_unavailable']+=1;continue
        m=rs[i]
        if m['target']!=r['target']:raise ValueError('Cross-source target mismatch')
        sign=1 if r['side']=='UP' else -1
        sigma=m['sigma'];left=r['receipt_left'];gap=sign*m['signed_gap']
        prob=float(ndtr(gap/(sigma*math.sqrt(left))))
        previous=float(ndtr((gap-r['btc15'])/(sigma*math.sqrt(left+.25))))
        delta=prob-previous
        out.append(dict(r,expected_delta15=delta,response_residual=delta-r['ask15'],
            model_dislocation=prob-r['ask'],signed_basis=sign*(m['signed_gap']-m['brti_gap']),
            spread=r['ask']-r['bid'],main_asof_t=m['t'],sigma=sigma))
    return out,dict(missing)


def signals(rows,mode):
    queues=defaultdict(list);seen=set();out=[]
    for r in rows:
        k=(r['ticker'],r['side']);t=r['source_t']
        if mode=='cheap_first_control':ok=True
        else:
            direction=r['btc5']>0 and r['btc15']>0 and r['brti5']>0 and r['structure_ok']
            if mode=='price_response_residual':ok=direction and r['response_residual']>=.08+r['spread']
            elif mode=='basis_dislocation':ok=direction and r['signed_basis']>0 and r['model_dislocation']>=.08+r['spread']
            else:raise ValueError(mode)
        if not ok:queues[k].clear();continue
        queues[k]=[x for x in queues[k] if t-x<=4];queues[k].append(t)
        if len(queues[k])>=2 and k not in seen:seen.add(k);out.append(r)
    return out


def run(output):
    verify_inputs();main=enrich();clean=paths(load_rows(DATA/'inputs.jsonl.gz'))
    result=dict(models=list(MODES),fit_parameters=False,threshold_search=False,
        purpose='Do economic units and lag direction help beyond absolute-dollar simultaneous impulse gates?',
        fixed_rule='30-45c, 2-10m; expected residual >= existing8c target + observed spread; positive BTC/BRTI, structure, two observations in4s',
        promotion_allowed=False,challenge_already_opened=True,orders=False,signal_only=True)
    for name,start,end,n in [('tuning','2026-09-24T00:15Z','2026-09-24T06:45Z',26),('validation','2026-09-24T07:00Z','2026-09-24T12:15Z',21)]:
        truth=markets(name);vs,_,bad=vrows(DATA/'v81.jsonl.gz',epoch(start),epoch(end));rs,missing=prepare(vs,main)
        result[name]=dict(source_rejections=bad,asof_rejections=missing,eligible_frames=len(rs),
            residual=stats(r['response_residual'] for r in rs),dislocation=stats(r['model_dislocation'] for r in rs),
            policies={mode:score_entries(signals(rs,mode),truth,n,'v81',clean) for mode in MODES})
    result['code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    for part in ('tuning','validation'):
        print(part,json.dumps({name:{k:m[k] for k in ('calls','contracts','wins','sides','entry','minutes_left','first_passage','mfe','mae')} for name,m in result[part]['policies'].items()}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
