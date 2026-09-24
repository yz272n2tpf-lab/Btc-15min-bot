"""Named architecture experiments over the existing verified telemetry replay.

Research only. No network, orders, runtime writes, threshold grid, or holdout IO.
The old internal validation has already been opened: it is a challenge set,
never relabelled as untouched evidence. Models train only on the tuning window.
"""
import argparse
from collections import Counter, defaultdict
from bisect import bisect_left
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.special import ndtr, expit, logit
from sklearn.linear_model import LogisticRegression

from joint_diagnosis import BASE, calls, epoch, load_rows, main_rows, metric, paths, stats
from joint_v81 import rows as vrows, candidates, gates as vgates, BASE as VBASE

ROOT = Path(__file__).parent
DATA = ROOT / 'joint_input_20260924'
MODELS = ('existing', 'diffusion', 'distance', 'distance_motion', 'market', 'market_residual')
V81_MODES = ('baseline', 'sequence', 'velocity', 'sequence_velocity')
PLAN = dict(
    training='00:15-06:45 UTC September 24; 26 contracts',
    folds='first 8 -> next 6, first 14 -> next 6, first 20 -> next 6; no future labels',
    challenge='07:00-12:15, previously opened development data, 13 official/21 scheduled',
    promotion='Requires later untouched validation; this challenge cannot authorize promotion',
    outcome_families=list(MODELS), v81_families=list(V81_MODES),
    fit='C=1 fixed L2, symmetric signed features, 5 clock anchors/contract, equal contract weight',
    outcome_policy='EARLY existing .75/.08/45c/2-10m; FINAL .90/2-8m plus BRTI authority; distance encoded in horizon model replaces absolute gap/range double gates',
    scalp_policy='separate first-passage head, existing +8c target/-10c stop/180s, 30-45c entry, two confirmations within4s, P(target-first)>=.70 fixed',
    sequence='arm existing route, permit entry within15s on continuing BTC/BRTI direction plus original quote-lag and structure gates; reset on source gaps/failed direction/expiry',
    velocity='replace acceleration-only trigger by equal 15s velocity over5s; keep existing route scale and all safety, price, persistence gates',
    selected_model='lowest contract-weighted chronological OOF Brier; baseline included, no challenge reselection',
    safety='same source qualification; explicitly exclude BTC source age outside[0,10] in V81 replay',
    orders=False, signal_only=True)


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def markets(part):
    result = {}
    for f in sorted((ROOT/'joint_labels_20260924'/part).glob('*.json')):
        m = json.loads(f.read_text()).get('market')
        if m:
            result[m['ticker']] = m
    return result


def verify_inputs():
    manifest = json.loads((DATA/'manifest.json').read_text())
    for name in ('main.jsonl.gz', 'v81.jsonl.gz', 'inputs.jsonl.gz'):
        if hashlib.sha256((DATA/name).read_bytes()).hexdigest() != manifest[name]['sha256']:
            raise ValueError('Input identity changed: '+name)


def enrich():
    raw = {(x['state']['contract'], epoch(x['state']['source_timestamp_utc'])): x['state']
           for x in load_rows(DATA/'main.jsonl.gz') if x['sample_kind']=='qualified'}
    rows = main_rows(DATA/'main.jsonl.gz', epoch('2026-09-24T00:15Z'), epoch('2026-09-24T12:15Z'))
    out=[]
    for r in rows:
        m=raw[r['ticker'],r['source_t']]['market']
        if any(m.get(k) is None for k in ('brti_gap','btc_price','vol5','range5','up_bid','up_ask','down_bid','down_ask')):
            continue
        sigma=max(m['btc_price']*m['vol5'],m['range5']/(1.59577*math.sqrt(5)),1.)
        horizon=sigma*math.sqrt(max(r['receipt_left'],1/60))
        q=min(.999,max(.001,(m['up_bid']+m['up_ask'])/2))
        movements=[r[k] for k in ('btc15','btc30','btc60')]
        if any(v is None for v in movements): continue
        out.append(dict(r, **{k:m[k] for k in ('up_bid','up_ask','down_bid','down_ask','brti_gap','btc_price')},
            sigma=sigma, z=m['brti_gap']/horizon, basis=(m['btc_gap']-m['brti_gap'])/sigma,
            m15=movements[0]/sigma,m30=movements[1]/sigma,m60=movements[2]/sigma,
            q=q, logit_q=float(logit(q)),p_existing=r['fair'] if r['side']=='UP' else 1-r['fair'] if r['fair'] is not None else None))
    return out


FEATURES={'distance':('z',), 'distance_motion':('z','basis','m15','m30','m60'),
          'market_residual':('logit_q','z','basis','m15','m30','m60')}


def anchors(rows):
    picked={}
    for r in rows:
        for a in (10,8,6,4,2):
            k=(r['ticker'],a)
            if k not in picked and a-.5<=r['receipt_left']<=a: picked[k]=r
    return list(picked.values())


def fit(rows, truth, name):
    if name not in FEATURES:return dict(name=name)
    rows=anchors(rows); features=FEATURES[name]
    x=np.array([[r[k] for k in features] for r in rows]); y=np.array([int(truth[r['ticker']]['result']=='yes') for r in rows])
    counts=Counter(r['ticker'] for r in rows); w=np.array([1/counts[r['ticker']] for r in rows])
    # Direction symmetry is an architectural constraint, not extra independent labels.
    scale=np.maximum(np.sqrt(np.average(x*x,axis=0,weights=w)),1e-6)
    sx=np.vstack((x/scale,-x/scale)); sy=np.r_[y,1-y]; sw=np.r_[w/2,w/2]
    model=LogisticRegression(C=1.,fit_intercept=False,max_iter=2000)
    model.fit(sx,sy,sample_weight=sw)
    return dict(name=name,features=features,scale=scale.tolist(),coef=model.coef_[0].tolist(),
                training_contracts=len(counts),training_anchors=len(rows))


def probability(r,model):
    name=model['name']
    if name=='existing':return r['p_existing']
    if name=='market':return r['q']
    if name=='diffusion':return float(ndtr(r['z']))
    return float(expit(sum(r[k]/s*c for k,s,c in zip(model['features'],model['scale'],model['coef']))))


def signed(r,p,side):
    prefix=side.lower(); confidence=p if side=='UP' else 1-p
    return dict(r,side=side,fair=confidence,ask=r[prefix+'_ask'],bid=r[prefix+'_bid'],edge=confidence-r[prefix+'_ask'])


def outcome_calls(rows, model, lane):
    out={}
    for r in rows:
        if r['ticker'] in out: continue
        p=probability(r,model)
        if p is None:continue
        possibilities=[]
        for side in ('UP','DOWN'):
            c=signed(r,p,side);direction=1 if side=='UP' else -1
            if lane=='early':
                ok=(2<=c['receipt_left']<=10 and c['fair']>=.75 and c['ask']<=.45 and c['edge']>=.08)
            elif lane=='final':
                ok=(2<=c['receipt_left']<=8 and c['fair']>=.90 and r['brti_authority']
                    and direction*r['brti_gap']>=11 and direction*r['signed_gap']>0)
            else:raise ValueError(lane)
            if ok:possibilities.append(c)
        if possibilities:out[r['ticker']]=max(possibilities,key=lambda c:c['edge'])
    return list(out.values())


def forecast_scores(rows, model, truth):
    scores=defaultdict(list); bins=defaultdict(list)
    for r in anchors(rows):
        p=probability(r,model)
        if p is None:continue
        y=int(truth[r['ticker']]['result']=='yes');p=min(1-1e-8,max(1e-8,p))
        scores[r['ticker']].append(((p-y)**2,-y*math.log(p)-(1-y)*math.log(1-p),int((p>=.5)==y)))
        bins[str(min(9,int(max(p,1-p)*10)))].append((max(p,1-p),int((p>=.5)==y)))
    averages=np.array([np.mean(v,axis=0) for v in scores.values()])
    return dict(contracts=len(scores),anchors=sum(map(len,scores.values())),
        brier=float(np.mean(averages[:,0])) if len(averages) else None,
        logloss=float(np.mean(averages[:,1])) if len(averages) else None,
        accuracy=float(np.mean(averages[:,2])) if len(averages) else None,
        contract_brier={k:float(np.mean([x[0] for x in v])) for k,v in scores.items()},
        calibration={k:dict(n=len(v),confidence=float(np.mean([x[0] for x in v])),accuracy=float(np.mean([x[1] for x in v]))) for k,v in bins.items()})


def v81_calls(rows, mode):
    armed={};queues=defaultdict(list);last={};called=set();out=[];events=Counter()
    for r in rows:
        k=(r['ticker'],r['side']);t=r['source_t']; f=dict(r)
        if mode in ('velocity','sequence_velocity'):
            f['btc5']=min(r.get('btc5') or 0,(r.get('btc15') or 0)/3)
            # Route must have sustained speed at least equal to its original acceleration floor.
            f['accel']=f['btc5']
        g=vgates(f,VBASE)
        if t-last.get(k,t)>4:armed.pop(k,None);queues[k].clear()
        last[k]=t
        safe=r.get('btc_age') is not None and 0<=r['btc_age']<=10 and g['features'] and g['brti_features'] and g['left']
        if not safe:armed.pop(k,None);queues[k].clear();events['safety_reset']+=1;continue
        impulse=all(v for n,v in g.items() if n not in ('ask5','ask15'))
        if mode in ('sequence','sequence_velocity'):
            if impulse:armed[k]=t;events['arm_frames']+=1
            a=armed.get(k)
            if a is None or t-a>15 or (r.get('btc5') or 0)<=0 or (r.get('brti5') or 0)<=0 or not g['structure']:
                armed.pop(k,None);queues[k].clear();continue
            ok=g['ask5'] and g['ask15']
        else:ok=all(g.values())
        if not ok:queues[k].clear();continue
        queues[k]=[x for x in queues[k] if t-x<=4];queues[k].append(t)
        if len(queues[k])>=2 and k not in called:called.add(k);out.append(r)
    return out,dict(events)


def passage(r,clean,horizon=180):
    tape=clean.get(r['ticker'],[]);t=r['t']; end=t+horizon
    ps=[x for x in tape if t<=x['t']<end]; p=r['side'].lower(); previous=t
    if not ps:return dict(result='missing',priced=False)
    if ps[0]['t']-t>3 or ps[0][p+'_ask']>r['ask']+1e-9:
        return dict(result='entry_not_confirmed',priced=False)
    for x in ps:
        if x['target']!=r['target']:return dict(result='target_mismatch',priced=False)
        if x['t']-previous>6:return dict(result='gap_censored',priced=False)
        previous=x['t'];gain=x[p+'_bid']-r['ask']
        if gain>=.08-1e-9:return dict(result='target',priced=True,gain=gain,delay=x['t']-t)
        if gain<=-.10+1e-9:return dict(result='stop',priced=True,gain=gain,delay=x['t']-t)
    # Never invent an execution at an unobserved time-limit quote.
    return dict(result='horizon_unpriced',priced=False)


SCALP_FEATURES=('btc5','btc15','btc30','brti5','brti15','accel','ask5','ask15','ask','receipt_left')


def scalp_fit(rows,clean):
    picked={}
    for r in rows:
        if r.get('btc_age') is None or not 0<=r['btc_age']<=10 or not r['features_ready'] or not r['brti_fresh']:
            continue
        if not 2<=r['receipt_left']<=10 or any(r.get(k) is None for k in SCALP_FEATURES):continue
        picked.setdefault((r['ticker'],r['side'],int(r['t']//60)),r)
    usable=[];censor=Counter()
    for r in picked.values():
        p=passage(r,clean);censor[p['result']]+=1
        if p['result'] in ('target','stop'):usable.append((r,int(p['result']=='target')))
    if len({y for _,y in usable})<2:return dict(available=False,selection_counts=censor)
    x=np.array([[r[k] for k in SCALP_FEATURES] for r,_ in usable]);y=np.array([y for _,y in usable])
    counts=Counter(r['ticker'] for r,_ in usable);w=np.array([1/counts[r['ticker']] for r,_ in usable])
    center=np.average(x,axis=0,weights=w);scale=np.maximum(np.sqrt(np.average((x-center)**2,axis=0,weights=w)),1e-6)
    model=LogisticRegression(C=1.,max_iter=2000)
    model.fit((x-center)/scale,y,sample_weight=w)
    return dict(available=True,features=SCALP_FEATURES,center=center.tolist(),scale=scale.tolist(),
        coef=model.coef_[0].tolist(),intercept=float(model.intercept_[0]),selection_counts=censor,
        contracts=len(counts),sampled_events=len(usable),selection_censor_bias_unresolved=True)


def scalp_calls(rows,model):
    if not model['available']:return []
    called=set();queues=defaultdict(list);out=[]
    for r in rows:
        k=(r['ticker'],r['side']);t=r['source_t']
        ok=(r.get('btc_age') is not None and 0<=r['btc_age']<=10 and r['features_ready'] and r['brti_fresh']
            and 2<=r['receipt_left']<=10 and all(r.get(f) is not None for f in model['features']))
        if not ok:queues[k].clear();continue
        p=float(expit(model['intercept']+sum((r[f]-c)/s*w for f,c,s,w in zip(model['features'],model['center'],model['scale'],model['coef']))))
        if p<.70:queues[k].clear();continue
        queues[k]=[x for x in queues[k] if t-x<=4];queues[k].append(t)
        if len(queues[k])>=2 and k not in called:
            out.append(dict(r,passage_probability=p));called.add(k)
    return out


def score_entries(entries,truth,scheduled,lane,clean):
    result=metric(entries,truth,scheduled,lane,clean,True)
    outcomes=[passage(r,clean) for r in entries]
    counts=Counter(x['result'] for x in outcomes)
    result['first_passage']=dict(counts=counts,marks=stats(x['gain'] for x in outcomes if x['priced']),
        win_rate_decisive=counts['target']/(counts['target']+counts['stop']) if counts['target']+counts['stop'] else None,
        complete_fills_proven=False,maximum_allowed_observation_gap_seconds=6)
    return result


def paired_uncertainty(candidate,baseline):
    common=sorted(set(candidate['contract_brier'])&set(baseline['contract_brier']))
    if not common:return {}
    d=np.array([candidate['contract_brier'][k]-baseline['contract_brier'][k] for k in common])
    rng=np.random.default_rng(150924);draw=rng.choice(d,(5000,len(d)),replace=True).mean(axis=1)
    return dict(contracts=len(d),candidate_minus_baseline_mean=float(d.mean()),bootstrap95=np.quantile(draw,[.025,.975]).tolist(),
                descriptive_only=True)


def frontier_from_existing():
    previous=json.loads((ROOT/'JOINT_TUNING_20260924.json').read_text())
    result={}
    for lane,b in previous['batch'].items():
        caps={}
        for cap in (.35,.45,.50,.70,1.):
            eligible=[x['metrics'] for x in b['results'] if x['metrics']['calls'] and x['metrics']['entry']['max']<=cap]
            qualified=[m for m in eligible if m['accuracy']>=.93 and m['calls']>=5]
            best=max(eligible,key=lambda m:(m['accuracy'],m['calls']),default=None)
            caps[str(cap)]=dict(unique_policies=len(eligible),best_accuracy=None if best is None else best['accuracy'],
                best_accuracy_calls=None if best is None else best['calls'],
                largest_ge93_at_least5_calls=max((m['calls'] for m in qualified),default=0))
        result[lane]=caps
    return result


def run(phase,output,tuning_path=None):
    verify_inputs();allrows=enrich();clean=paths(load_rows(DATA/'inputs.jsonl.gz'))
    start,end=epoch('2026-09-24T00:15Z'),epoch('2026-09-24T06:45Z')
    train=markets('tuning'); rows=[r for r in allrows if start<=r['t']<end and r['ticker'] in train]
    result=dict(plan=PLAN,plan_sha256=digest(PLAN),phase=phase,orders=False,signal_only=True)
    if phase=='tune':
        tickers=sorted(train,key=lambda k:train[k]['open_time']);oof={k:[] for k in MODELS}; result['folds']=[]
        for n in (8,14,20):
            tr={k:train[k] for k in tickers[:n]};te={k:train[k] for k in tickers[n:n+6]}
            fitrows=[r for r in rows if r['ticker'] in tr];testrows=[r for r in rows if r['ticker'] in te]
            fold=dict(fit_contracts=len(tr),test_contracts=len(te),models={})
            for name in MODELS:
                model=fit(fitrows,tr,name);score=forecast_scores(testrows,model,te);fold['models'][name]=score
                oof[name].append(score)
            result['folds'].append(fold)
        averages={k:float(np.mean([v for s in sc for v in s['contract_brier'].values()])) for k,sc in oof.items()}
        result['oof_brier']=averages;result['selected_outcome_family']=min(averages,key=averages.get)
        result['models']={name:fit(rows,train,name) for name in MODELS}
        result['outcome']={}
        for name,model in result['models'].items():
            result['outcome'][name]=dict(scores=forecast_scores(rows,model,train),lanes={lane:score_entries(outcome_calls(rows,model,lane),train,26,lane,clean) for lane in ('early','final')})
        vr,_,bad=vrows(DATA/'v81.jsonl.gz',start,end)
        result['v81']={name:dict(metrics=score_entries(v81_calls(vr,name)[0],train,26,'v81',clean),state_counts=v81_calls(vr,name)[1]) for name in V81_MODES}
        result['scalp_model']=scalp_fit(vr,clean)
        result['scalp_head']=score_entries(scalp_calls(vr,result['scalp_model']),train,26,'v81',clean)
        result['source_rejections']=bad;result['existing_threshold_frontier']=frontier_from_existing()
    else:
        lock=json.loads(tuning_path.read_text())
        if lock['plan_sha256']!=digest(PLAN):raise ValueError('Architecture plan changed')
        result['tuning_sha256']=hashlib.sha256(tuning_path.read_bytes()).hexdigest()
        result['selected_outcome_family']=lock['selected_outcome_family'];truth=markets('validation')
        start,end=epoch('2026-09-24T07:00Z'),epoch('2026-09-24T12:15Z')
        testrows=[r for r in allrows if start<=r['t']<end and r['ticker'] in truth]
        result['outcome']={}
        for name,model in lock['models'].items():
            result['outcome'][name]=dict(scores=forecast_scores(testrows,model,truth),lanes={lane:score_entries(outcome_calls(testrows,model,lane),truth,21,lane,clean) for lane in ('early','final')})
        for name in MODELS:
            result['outcome'][name]['paired_vs_existing']=paired_uncertainty(result['outcome'][name]['scores'],result['outcome']['existing']['scores'])
        vr,_,bad=vrows(DATA/'v81.jsonl.gz',start,end)
        result['v81']={name:dict(metrics=score_entries(v81_calls(vr,name)[0],truth,21,'v81',clean),state_counts=v81_calls(vr,name)[1]) for name in V81_MODES}
        result['scalp_head']=score_entries(scalp_calls(vr,lock['scalp_model']),truth,21,'v81',clean)
        result['source_rejections']=bad
        result['promotion_allowed']=False
    result['source_code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(phase=phase,selected=result['selected_outcome_family'],oof=result.get('oof_brier'),
        models={n:dict(brier=v['scores']['brier'],lanes={l:{k:m[k] for k in ('calls','wins','entry','minutes_left','first_passage')} for l,m in v['lanes'].items()}) for n,v in result['outcome'].items()},
        v81={n:{k:m['metrics'][k] for k in ('calls','wins','entry','first_passage')} for n,m in result['v81'].items()}),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=('tune','challenge'),required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--tuning',type=Path)
    a=p.parse_args();run(a.phase,a.output,a.tuning)
