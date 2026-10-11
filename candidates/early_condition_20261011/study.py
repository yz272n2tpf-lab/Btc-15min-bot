"""Offline chronological replay, contract-level calibration and bounded diagnostics."""
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import argparse, bisect, gzip, hashlib, json, math
import numpy as np
from .engine import Engine, Rules, fee, digest, cell_key
from candidates.three_ladder_20261011.profile_study import normalize, ts


def cohort(path):
    out=defaultdict(list)
    for line in path.open():
        raw=json.loads(line);r=normalize(raw)
        if r:
            r.update(received=r['time'],publication_id=digest([raw['schema'],r['contract'],raw['timestamp_utc']]),
                source_epoch='COHORT_V1',evidence_class='OBSERVATION_NO_NATIVE_RECEIPT',baseline_ready=raw['early'].get('provisional_candidate',False))
            out[r['contract']].append(r)
    return dict(out)


def common(path, start, end):
    out=defaultdict(list);seen={};stats=Counter()
    with path.open() as f:
        for line in f:
            ev=json.loads(line)
            for source in ev.get('sources',[]):
                if source.get('service')!='main' or not isinstance(source.get('state'),dict):continue
                raw=source['state'];r=normalize(raw,True)
                if not r or not start<=r['time']<end:continue
                k=(r['contract'],r['time']);fingerprint=digest({a:b for a,b in r.items() if a!='healthy'})
                if k in seen:
                    stats['duplicate_publications']+=1
                    if seen[k]!=fingerprint:stats['conflicting_later_publications']+=1
                    continue
                seen[k]=fingerprint
                received=ts(source['response_received_utc'])
                r.update(received=received,publication_id=digest([raw.get('display_build'),r['contract'],raw['source_timestamp_utc']]),
                    source_epoch=raw.get('display_build'),evidence_class='COMMON_OBSERVED_NO_NATIVE_RECEIPT',baseline_ready=raw.get('early',{}).get('ready',False))
                # Probability, settlement and prices are never taken from chart future/history expansion.
                r['healthy'] &= 0<=received-r['time']<=10
                out[r['contract']].append(r)
    return dict(out),dict(stats)


def save_data(path,data):
    with gzip.GzipFile(filename=str(path),mode='wb',mtime=0)as f:
        f.write(json.dumps(data,sort_keys=True,separators=(',',':')).encode())
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_data(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def subsequent(seq, at, delay, end):
    # Source quote must itself be >= desired decision+manual time; later receipt
    # of an older cached quote is not an execution opportunity.
    target=at+delay
    for r in seq:
        if r['time']>=target:
            if r['time']>target+10 or r['time']>=end or not r['healthy']:return None
            return r
    return None


def score_episode(e, seq, delay=10):
    o=e['origin'];x=e['exit'];s=o['side'].lower();base=deepcopy(e)
    base['scenario']=None;base['manual_seconds']=delay
    if not x:
        return base
    close=seq[0]['time']+seq[0]['left']
    a=subsequent(seq,o['decision_available'],delay,close)
    b=subsequent(seq,x['available'],delay,close)
    if not a or not b or a['time']>=b['time']:
        base['censor']='MISSING_DELAYED_ENTRY_OR_EXIT_QUOTE';return base
    chain=[r for r in seq if o['time']<=r['time']<=b['time']]
    complete=o['complete'] and all(r['healthy'] for r in chain) and all(v['time']-u['time']<=15 for u,v in zip(chain,chain[1:]))
    ask=a[s+'_ask'];bid=b[s+'_bid'];reserve=max(o['ask']-o['bid'],a[s+'_ask']-a[s+'_bid'],b[s+'_ask']-b[s+'_bid'],.02)
    base['scenario']=dict(entry_ask=ask,entry_at=a['time'],exit_bid=bid,exit_at=b['time'],
        gross_gain=bid-ask,entry_fee=fee(ask),exit_fee=fee(bid),reserve=reserve,
        net=bid-ask-fee(ask)-fee(bid)-reserve,complete_path=complete,
        at_signal_ask_net=bid-o['ask']-fee(o['ask'])-fee(bid)-reserve,
        underlying_direction_correct=(1 if o['side']=='UP' else -1)*(b['btc']-a['btc'])>0,
        duration=x['time']-o['time'],realized_profit=None,confirmed_fill=False)
    if not complete:base['censor']='INCOMPLETE_OBSERVED_PATH'
    return base


def replay(data,profile=None,proposal=False,delay=10):
    episodes=[];events=[];rejections=Counter();statuses=Counter();baseline=[]
    for contract,seq in sorted(data.items(),key=lambda kv:kv[1][0]['received']):
        engine=Engine(profile,proposal_mode=proposal)
        first_baseline=next((r for r in seq if r.get('baseline_ready') and r['healthy']),None)
        if first_baseline:baseline.append(dict(contract=contract,time=first_baseline['time'],side=first_baseline['side'],ask=first_baseline[first_baseline['side'].lower()+'_ask']))
        for r in seq:
            result=engine.process(r);statuses[result['guidance']]+=1
            if result['guidance']=='PASS':rejections.update(result['reasons'])
        events.extend(engine.events)
        episodes.extend(score_episode(e,seq,delay)for e in engine.finish())
    return dict(episodes=episodes,events=events,rejections=dict(rejections),statuses=dict(statuses),baseline_first_ready=baseline)


def interval(values,seed=1011):
    """Contract-resampled mean percentile interval, descriptive, not per-trade guarantee."""
    if not values:return [None,None]
    a=np.array(values,dtype=float);rng=np.random.default_rng(seed)
    samples=rng.choice(a,(5000,len(a)),replace=True).mean(1)
    return np.quantile(samples,[.025,.975]).tolist()


def stats(result):
    eps=result['episodes'];labels=[e for e in eps if e['scenario'] and not e['censor']]
    observed=[e for e in eps if e['scenario']]
    clusters=defaultdict(list)
    for e in labels:clusters[e['origin']['contract']].append(e['scenario']['net'])
    values=[float(np.mean(a))for a in clusters.values()]
    counts=Counter(e['origin']['contract']for e in eps)
    watch=Counter(e['origin_id']for e in result['events']if e['event']=='WATCH')
    durations=[e['scenario']['duration']for e in observed]
    leads=[];recoveries=0
    for e in eps:
        event=[v for v in result['events']if v['origin_id']==e['origin']['id']]
        ws=[v for v in event if v['event']=='WATCH']
        if e['exit'] and ws:leads.append(e['exit']['time']-ws[0]['time'])
        recoveries+=sum(v['event']=='HOLD'for v in event)
    return dict(proposals_or_buys=len(eps),entry_contracts=len(counts),side_counts=dict(Counter(e['origin']['side']for e in eps)),
        condition_exits=sum(e['exit']is not None for e in eps),complete_scored=len(labels),independent_scored_contracts=len(clusters),
        endpoint_observed=len(observed),censored=len(eps)-len(labels),censor_reasons=dict(Counter(e['censor']for e in eps if e['censor'])),
        positive_net=sum(e['scenario']['net']>0 for e in labels),negative_or_zero_net=sum(e['scenario']['net']<=0 for e in labels),
        underlying_direction_correct=sum(e['scenario']['underlying_direction_correct']for e in labels),
        mean_net_cents=100*float(np.mean([e['scenario']['net']for e in labels]))if labels else None,
        contract_mean_net_cents=100*float(np.mean(values))if values else None,
        contract_bootstrap_95_cents=[None if v is None else 100*v for v in interval(values)],
        endpoint_only_positive=sum(e['scenario']['net']>0 for e in observed),
        watch_events=sum(watch.values()),watch_recovery_events=recoveries,
        max_watch_episodes=max(watch.values(),default=0),median_watch_lead_seconds=float(np.median(leads))if leads else None,
        multiple_entry_contracts={k:v for k,v in counts.items()if v>1},
        minimum_entry_remaining=min((e['origin']['left']for e in eps),default=None),
        exit_duration_seconds=dict(min=min(durations),median=float(np.median(durations)),max=max(durations))if durations else None,
        rejections=result['rejections'])


def fit_profile(dev,cal):
    cells={}
    for key in ('UP_LOW','UP_HIGH','DOWN_LOW','DOWN_HIGH'):
        def select(result):
            return [e for e in result['episodes']if e['origin']['side']+('_LOW'if e['origin']['ask']<=.5 else '_HIGH')==key]
        a=select(dev);b=select(cal)
        def group(eps):
            d=defaultdict(list)
            for e in eps:
                if e['scenario'] and not e['censor']:d[e['origin']['contract']].append(e['scenario']['gross_gain'])
            return [float(np.mean(v))for v in d.values()]
        ag=group(a);bg=group(b)
        lower=interval(ag)[0];bl=interval(bg)[0]
        covered=lambda eps:sum(e['scenario']is not None and not e['censor']for e in eps)/max(len(eps),1)
        complete=[e for e in a if e['scenario'] and not e['censor']]
        cost=max([fee(e['origin']['ask'])+fee(.5)+max(e['origin']['ask']-e['origin']['bid'],.02)for e in a+b],default=.06)
        supported=len(ag)>=12 and len(bg)>=6 and min(covered(a),covered(b))>=.8 and lower is not None and bl is not None and min(lower,bl)>cost
        reasons=[]
        if len(ag)<12:reasons.append('DEVELOPMENT_N_LT12')
        if len(bg)<6:reasons.append('CALIBRATION_N_LT6')
        if min(covered(a),covered(b))<.8:reasons.append('COMPLETE_PATH_COVERAGE_LT80PCT')
        if lower is None or bl is None or min(lower,bl)<=cost:reasons.append('NET_LOWER_BOUND_NOT_POSITIVE')
        cells[key]=dict(supported=supported,development_proposals=len(a),calibration_proposals=len(b),
            development_contract_n=len(ag),calibration_contract_n=len(bg),development_coverage=covered(a),calibration_coverage=covered(b),
            development_mean_gross=float(np.mean(ag))if ag else None,calibration_mean_gross=float(np.mean(bg))if bg else None,
            gross_gain_lower=lower,calibration_gross_lower=bl,cost_ceiling=cost,reasons=reasons,
            min_left=min((e['origin']['left']for e in complete),default=None),max_left=max((e['origin']['left']for e in complete),default=None),
            min_ask=min((e['origin']['ask']for e in complete),default=None),max_ask=max((e['origin']['ask']for e in complete),default=None))
    return dict(policy='EARLY_CONDITION_RESEARCH_V1',rules=asdict(Rules()),cells=cells,enabled=False,validated=False,
        production_authorized=False,signal_only=True,orders=False,independent_acceptance_pending=True,
        uncertainty='Contract bootstrap of condition-exit gross gain; retrospective matched-cohort mean only, not a per-trade bound',
        missing=['native receipt chronology','decision-time fee and depth bindings','measured manual reaction budget','independent full-path economic acceptance'])


def write_json(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def run_dev(root,cohort_path):
    data=cohort(cohort_path)
    prior=json.loads((root/'audit/three_ladder_readiness_20261011/research_profile_DISABLED.json').read_text())
    train={c:data[c]for c in prior['development_contracts']};cal={c:data[c]for c in prior['calibration_contracts']}
    out=root/'audit/early_condition_20261011'
    a=replay(train,proposal=True);b=replay(cal,proposal=True)
    profile=fit_profile(a,b)
    write_json(out/'profile_DISABLED.json',profile)
    write_json(out/'development_results.json',dict(summary=stats(a),**a))
    write_json(out/'calibration_results.json',dict(summary=stats(b),**b))
    manifest=dict(source_sha256=hashlib.sha256(cohort_path.read_bytes()).hexdigest(),development_contracts=list(train),calibration_contracts=list(cal),
        development_data_sha256=save_data(out/'development_inputs.json.gz',train),calibration_data_sha256=save_data(out/'calibration_inputs.json.gz',cal))
    write_json(out/'input_manifest.json',manifest)
    print(json.dumps(dict(development=stats(a),calibration=stats(b),cells=profile['cells']),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['development']);p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--cohort',type=Path,required=True);a=p.parse_args()
    run_dev(a.root,a.cohort)
