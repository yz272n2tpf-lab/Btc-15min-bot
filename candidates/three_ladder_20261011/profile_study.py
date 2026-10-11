"""Frozen observational EARLY forecast feasibility. Never a trusted/live profile.

Fit past BID-at-horizon observations; never use future maxima or create native
receipts. One training/calibration origin per contract prevents row replication
from increasing the independent sample. Holdout selection precedes path scoring.
"""
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
import bisect, hashlib, json, math
import numpy as np
from btc15_v2_product.opportunities import fee_scenario

HORIZONS=(240,300,360,420)
FEATURES=('bid','spread','fair','btc_gap_bps','brti_gap_bps','momentum60_bps','remaining_fraction')

def ts(x): return datetime.fromisoformat(x.replace('Z','+00:00')).timestamp()
def sha(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def normalize(r, common=False):
    try:
        m=r['market'] if common else r
        e=r['final'] if common else r['early']
        b=m if common else r['brti']
        t=ts(r['source_timestamp_utc'] if common else r['timestamp_utc'])
        side=e['side'] if common else e['preferred_side']
        p=e['confidence'] if common else e['preferred_fair']
        left=r['timer']['seconds_left'] if common else r['seconds_left']
        ready=all(r['health'].get(k)is True for k in ('source_fresh','brti_fresh','paired_quotes','market_open')) if common else b.get('direct_brti_ready') is True
        if not common:
            source=ts(b['brti_timestamp_utc']);ready &= 0<=t-source<=5
        o=dict(contract=r['contract'],time=t,target=m['target'],btc=m['btc_price'] if common else e['btc_price'],
            brti=m['brti_value'] if common else b['direct_brti'],side=side,p=p,left=left,healthy=ready,
            **{k:m[k] for k in ('up_bid','up_ask','down_bid','down_ask')})
        if side not in ('UP','DOWN') or not all(type(v) in (int,float) and math.isfinite(v) for k,v in o.items() if k not in ('contract','side','healthy')):return None
        if not 0<left<=900 or o['target']<=0:return None
        if abs(o['up_ask']+o['down_bid']-1)>1e-8 or abs(o['down_ask']+o['up_bid']-1)>1e-8:o['healthy']=False
        return o
    except (KeyError,TypeError,ValueError):return None

def paths(rows):
    seen={};conflicts=set()
    for r in rows:
        if not r:continue
        key=(r['contract'],r['time'])
        # The same source publication observed again is one observation.
        # Re-observing the identical source publication after it expires must
        # not invalidate the earlier observation, nor revive an earlier stale
        # one. Preserve FIRST observed health; conflict on market bytes only.
        if key in seen and any(seen[key][k]!=v for k,v in r.items() if k!='healthy'):conflicts.add(key)
        seen.setdefault(key,r)
    out=defaultdict(list)
    for k,r in sorted(seen.items(),key=lambda kv:kv[1]['time']):
        if k not in conflicts:out[r['contract']].append(r)
    return dict(out),len(conflicts)

def features(seq,i,h):
    r=seq[i];side=r['side'];sign=1 if side=='UP' else -1
    bid,ask=r[side.lower()+'_bid'],r[side.lower()+'_ask']
    if not r['healthy'] or not 0<bid<=ask<1 or r['left']<=h:return None
    # Only already observed prices; an outage cannot supply a momentum estimate.
    past=[x for x in seq[:i+1] if r['time']-65<=x['time']<=r['time']-60]
    if not past:return None
    old=past[-1];prefix=[x for x in seq[:i+1] if x['time']>=old['time']]
    if any(not x['healthy'] or x['target']!=r['target'] for x in prefix):return None
    if any(b['time']-a['time']>10 for a,b in zip(prefix,prefix[1:])):return None
    gap=sign*(r['btc']-r['target']);bgap=sign*(r['brti']-r['target']);momentum=sign*(r['btc']-old['btc'])
    if min(gap,bgap,momentum)<=0:return None
    scale=10000/r['target']
    return np.array([bid,ask-bid,r['p'],gap*scale,bgap*scale,momentum*scale,r['left']/900])

def future(seq,i,h):
    r=seq[i];side=r['side'].lower();end=r['time']+h
    j=bisect.bisect_left([x['time'] for x in seq],end)
    if j>=len(seq) or seq[j]['time']>end+10 or r['left']<=seq[j]['time']-r['time']:return None
    tail=seq[i:j+1]
    if any(not x['healthy'] or x['target']!=r['target'] for x in tail):return None
    if any(b['time']-a['time']>10 for a,b in zip(tail,tail[1:])):return None
    x=seq[j];bid=x[side+'_bid'];ask=x[side+'_ask']
    if not 0<=bid<=ask<=1:return None
    return dict(bid=bid,at=x['time'],net=bid-r[side+'_ask']-fee_scenario(r[side+'_ask'],1)-fee_scenario(bid,1)-(r[side+'_ask']-r[side+'_bid']))

def first_origins(data,h):
    out=[]
    for contract,seq in data.items():
        for i,r in enumerate(seq):
            x=features(seq,i,h)
            if x is not None:
                # First qualifying current observation; NEVER choose by future label.
                out.append((contract,r,x,future(seq,i,h)));break
    return out

def fit(data):
    contracts=sorted(data,key=lambda c:data[c][0]['time']);split=int(len(contracts)*.6)
    train=contracts[:split];cal=contracts[split:];models={}
    for h in HORIZONS:
        a=first_origins({c:data[c] for c in train},h);b=first_origins({c:data[c] for c in cal},h)
        usable=[r for r in a if r[3] is not None]
        if len(usable)<len(FEATURES)+2:
            models[str(h)]={'blocked':'INSUFFICIENT_TRAINING_CONTRACTS','train_eligible':len(a),'train_labeled':len(usable)};continue
        X=np.array([r[2] for r in usable]);y=np.array([r[3]['bid'] for r in usable]);mean=X.mean(0);scale=X.std(0);scale[scale==0]=1
        A=np.column_stack([np.ones(len(X)),(X-mean)/scale]);pen=np.eye(A.shape[1]);pen[0,0]=0
        beta=np.linalg.solve(A.T@A+pen,A.T@y)
        model=dict(mean=mean.tolist(),scale=scale.tolist(),beta=beta.tolist(),train_eligible=len(a),train_labeled=len(usable),cal_eligible=len(b))
        residual=[r[3]['bid']-predict(model,r[2])[0] for r in b if r[3] is not None]
        model.update(cal_labeled=len(residual),lower_residual=float(np.quantile(residual,.05,method='lower')) if residual else -1,
                     train_contracts=[r[0] for r in usable],calibration_contracts=[r[0] for r in b if r[3] is not None])
        models[str(h)]=model
    return dict(policy='EARLY_BID_HORIZON_RESEARCH_V1',features=FEATURES,models=models,
        development_contracts=train,calibration_contracts=cal,enabled=False,validated=False,
        evidence_class='OBSERVATIONAL_COMPONENT_FEASIBILITY',signal_only=True,orders=False,
        uncertainty='Empirical lower calibration residual; NOT validated conditional confidence or guaranteed per-trade gain',
        missing=['original native quote/feature receipt binding','verified decision-time series fee schedule','measured manual execution budget','independent uncertainty and regime validation'])

def predict(model,x):
    mean=float(np.clip(np.r_[1,(x-np.array(model['mean']))/np.array(model['scale'])]@model['beta'],0,1))
    return mean,max(0,min(1,mean+model.get('lower_residual',0)))

def evaluate(profile,data):
    result={}
    for h in HORIZONS:
        m=profile['models'][str(h)];chosen=[];eligible=0;missed=[];errors=[]
        if 'blocked' in m:result[str(h)]=m;continue
        for contract,seq in data.items():
            selected=None;first=None
            for i,r in enumerate(seq):
                x=features(seq,i,h)
                if x is None:continue
                eligible+=1;mean,lower=predict(m,x);side=r['side'].lower();ask=r[side+'_ask'];spread=ask-r[side+'_bid']
                net=lower-ask-fee_scenario(ask,1)-fee_scenario(.5,1)-spread
                if first is None:first=(i,r,mean,lower,net)
                if net>0 and selected is None:selected=(i,r,mean,lower,net)
            # Only now inspect future observations. Missing paths are censored,
            # never silently erased from the selected entry denominator.
            if first:
                i,r,mean,lower,net=first;f=future(seq,i,h)
                if f:errors.append(dict(contract=contract,error=mean-f['bid'],lower_exceeded=f['bid']>=lower))
                if selected is None and f and f['net']>0:missed.append(contract)
            if selected:
                i,r,mean,lower,net=selected;f=future(seq,i,h)
                chosen.append(dict(contract=contract,side=r['side'],time=r['time'],ask=r[r['side'].lower()+'_ask'],left=r['left'],
                    predicted_bid=mean,empirical_lower_bid=lower,conservative_net_scenario=net,future=f,realized_profit=None))
        labeled=[r for r in chosen if r['future']]
        result[str(h)]=dict(observation_screen_count=eligible,selected_contracts=len(chosen),scored_contracts=len(labeled),censored=len(chosen)-len(labeled),
            positive_net_scenarios=sum(r['future']['net']>1e-9 for r in labeled),
            mean_net_cents=float(np.mean([r['future']['net']*100 for r in labeled])) if labeled else None,
            mean_ask_cents=float(np.mean([r['ask']*100 for r in chosen])) if chosen else None,
            first_opportunity_forecast_n=len(errors),mae=float(np.mean([abs(r['error']) for r in errors])) if errors else None,
            empirical_lower_coverage=sum(r['lower_exceeded'] for r in errors)/len(errors) if errors else None,
            missed_positive_first_opportunities=missed,entries=chosen,full_native_candidate_replay=False,
            warning_exit_reentry_performance='UNVALIDATED: original native chronology and a trusted opportunity profile remain absent')
    return result

def load_cohort(workspace):
    inv=json.loads((workspace/'repo/audit/existing_evidence_20261011/corpus_inventory.json').read_text())
    item=next(r for r in inv['files'] if r['name'].endswith('btc15_cohort_native_v1_20260928.jsonl'))
    p=workspace/'evidence-corpus'/item['sha256'];assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
    return paths(normalize(json.loads(l)) for l in p.open()),item['sha256']

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('workspace',type=Path);p.add_argument('mode',choices=['fit','holdout']);args=p.parse_args()
    out=args.workspace/'repo/audit/three_ladder_readiness_20261011'
    if args.mode=='fit':
        (data,conflicts),source=load_cohort(args.workspace);profile=fit(data);profile.update(source_sha256=source,conflicting_keys=conflicts)
        (out/'research_profile_DISABLED.json').write_text(json.dumps(profile,indent=2));print(json.dumps({h:{k:v for k,v in m.items() if k.endswith(('eligible','labeled')) or k=='blocked'} for h,m in profile['models'].items()}))
    else:
        profile=json.loads((out/'research_profile_DISABLED.json').read_text());rows=[]
        for line in (args.workspace/'readiness-evidence/holdout/records.jsonl').open():
            event=json.loads(line)
            for source in event.get('sources',[]):
                if source.get('service')=='main' and isinstance(source.get('state'),dict):
                    r=normalize(source['state'],True)
                    if r and ts('2026-10-04T00:00:00Z')<=r['time']<ts('2026-10-04T04:00:00Z'):rows.append(r)
        data,conflicts=paths(rows)
        used=set(profile['development_contracts']+profile['calibration_contracts']);assert not used.intersection(data)
        result=dict(profile_sha256=sha(profile),contracts=len(data),unique_observations=sum(map(len,data.values())),conflicting_keys=conflicts,
            first=min(r['time'] for seq in data.values() for r in seq),last=max(r['time'] for seq in data.values() for r in seq),
            results=evaluate(profile,data),promotion='RESTRICT',trusted_profiles_added=0,holdout_contracts=sorted(data))
        (out/'early_holdout_results.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='results'}));print(json.dumps({h:{k:v for k,v in r.items() if k not in ('entries','missed_positive_first_opportunities')} for h,r in result['results'].items()},indent=2))
