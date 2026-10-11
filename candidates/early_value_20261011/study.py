"""Chronological offline comparisons. Only observed condition exits are scored."""
from collections import Counter,defaultdict
from copy import deepcopy
from dataclasses import replace,asdict
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from candidates.early_condition_20261011 import engine as old
from candidates.early_condition_20261011.study import load_data,score_episode,subsequent,interval,write_json
from .engine import Engine,Rules

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit/early_value_20261011'
PRIOR=ROOT/'audit/early_condition_20261011'
POLICIES=('tier1_transferred','condition_v1','ceiling45','ceiling50','ceiling55','ceiling58','unified_value')


def make_engine(policy,profile=None,proposal=True):
    if policy=='condition_v1':
        return old.Engine(profile,proposal_mode=proposal)
    rules=Rules()
    if policy=='tier1_transferred':
        rules=replace(rules,max_ask=.45,allow_exception=False,baseline_tier1=True)
    elif policy.startswith('ceiling'):
        rules=replace(rules,max_ask=int(policy[7:])/100,allow_exception=False)
    return Engine(profile,proposal_mode=proposal,rules=rules)


def distribution(values):
    return dict(n=len(values),min=min(values),mean=float(np.mean(values)),median=float(np.median(values)),
                max=max(values)) if values else dict(n=0,min=None,mean=None,median=None,max=None)


def replay(data,policy,profile=None,proposal=True,delay=10):
    episodes=[];events=[];rejections=Counter();invalidations=[];status=Counter()
    for contract,seq in sorted(data.items(),key=lambda kv:kv[1][0]['received']):
        engine=make_engine(policy,profile,proposal)
        tickets={}
        for r in seq:
            result=engine.process(r)
            status[result['guidance']]+=1
            if not engine.origin:rejections.update(result['reasons'])
            if engine.origin:
                if policy=='condition_v1':
                    side=engine.origin['side'];x=old.features(engine.history,r,side,engine.rules)
                    failures=old.screen(r,x,side,engine.rules)
                    if engine.terminal:failures+=['OPPORTUNITY_EXITED']
                    if not r['healthy']:failures+=['UNHEALTHY']
                    records=tickets.setdefault(engine.origin['id'],{})
                    prior_invalid=any(not z['valid'] for z in records.values())
                    records[r['time']]=dict(valid=not failures and not prior_invalid,reasons=failures or (['PRIOR_INVALIDATION_LATCH'] if prior_invalid else []))
                else:
                    ticket=result.get('ticket') or {}
                    tickets.setdefault(engine.origin['id'],{})[r['time']]=dict(
                        valid=result['research_entry_valid'],reasons=ticket.get('invalidation_reasons',[]))
        events.extend(engine.events)
        invalidations.extend(getattr(engine,'invalidations',[]))
        for episode in engine.finish():
            e=score_episode(episode,seq,delay)
            o=e['origin'];a=subsequent(seq,o['decision_available'],delay,seq[0]['time']+seq[0]['left'])
            check=tickets.get(o['id'],{}).get(a['time']) if a else None
            e['delayed_revalidation']=dict(available=a is not None,valid=bool(check and check['valid']),
                failures=(check or {}).get('reasons',['NO_DELAYED_QUOTE']),
                refreshed_ask=a[o['side'].lower()+'_ask'] if a else None,
                available_at=a['received'] if a else None)
            e['scenario_without_revalidation']=deepcopy(e['scenario'])
            if not check or not check['valid']:
                e['scenario']=None
                e['censor']='MANUAL_BUY_INVALIDATED' if check else 'MISSING_DELAYED_ENTRY_QUOTE'
            episodes.append(e)
    return dict(policy=policy,manual_seconds=delay,episodes=episodes,events=events,
                rejections=dict(rejections),statuses=dict(status),invalidations=invalidations)


def summarize(result,data):
    eps=result['episodes'];valid=[e for e in eps if e['delayed_revalidation']['valid']]
    complete=[e for e in valid if e['scenario'] and not e['censor']]
    canceled=[e for e in eps if e['censor']=='MANUAL_BUY_INVALIDATED']
    cluster=defaultdict(list)
    for e in complete:cluster[e['origin']['contract']].append(e['scenario']['net'])
    means=[float(np.mean(v)) for v in cluster.values()]
    warnings=Counter(e['origin_id'] for e in result['events'] if e['event']=='WATCH')
    leads=[];post=[];first_warnings=[]
    for e in eps:
        ws=[x for x in result['events'] if x['origin_id']==e['origin']['id'] and x['event']=='WATCH']
        if e['exit'] and ws:leads.append(e['exit']['time']-ws[0]['time'])
        if ws:
            seq=data[e['origin']['contract']];at=next((r for r in seq if r['time']==ws[0]['time']),None)
            if at:
                s=e['origin']['side'].lower();first_warnings.append(dict(origin=e['origin']['id'],
                    time=at['time'],bid=at[s+'_bid'],gross_vs_original_ask=at[s+'_bid']-e['origin']['ask']))
        if e['exit']:
            seq=data[e['origin']['contract']]
            later=subsequent(seq,e['exit']['available'],30,seq[0]['time']+seq[0]['left'])
            if later:post.append(dict(origin=e['origin']['id'],bid=later[e['origin']['side'].lower()+'_bid'],
                higher=later[e['origin']['side'].lower()+'_bid']>e['exit']['bid']))
    counts=Counter(e['origin']['contract'] for e in eps)
    exact_legacy={}
    for c,seq in data.items():
        for r in seq:
            ask=r[r['side'].lower()+'_ask']
            if r['healthy'] and 0<ask<=.45 and r['p']>=.75 and r['p']-ask>=.08 and 120<=r['left']<=600 and abs(r['btc']-r['target'])>=25:
                exact_legacy[c]=dict(time=r['time'],side=r['side'],ask=ask);break
    byside={}
    for side in ('UP','DOWN'):
        q=[e for e in complete if e['origin']['side']==side]
        byside[side]=dict(proposals=sum(e['origin']['side']==side for e in eps),
            complete=len(q),positive=sum(e['scenario']['net']>1e-10 for e in q),
            directional_correct=sum(e['scenario']['underlying_direction_correct'] for e in q),
            mean_net_cents=float(np.mean([e['scenario']['net'] for e in q]))*100 if q else None)
    no_recheck=[e['scenario_without_revalidation'] for e in eps if e['scenario_without_revalidation'] and e['scenario_without_revalidation']['complete_path']]
    return dict(input_contracts=len(data),observations=sum(map(len,data.values())),
        proposals=len(eps),entry_contracts=len(counts),entry_ask_cents=distribution([e['origin']['ask']*100 for e in eps]),
        delayed_entry_ask_cents=distribution([e['delayed_revalidation']['refreshed_ask']*100 for e in valid]),
        delayed_valid=len(valid),canceled_before_manual_entry=len(canceled),
        cancellation_reasons=dict(Counter(z for e in canceled for z in e['delayed_revalidation']['failures'])),
        complete=len(complete),independent_complete_contracts=len(cluster),
        unresolved_valid_entries=len(valid)-len(complete),
        censor_reasons=dict(Counter(e['censor'] for e in eps if e['censor'])),
        positive=sum(e['scenario']['net']>1e-10 for e in complete),negative_or_zero=sum(e['scenario']['net']<=1e-10 for e in complete),
        mean_net_cents=float(np.mean([e['scenario']['net'] for e in complete]))*100 if complete else None,
        contract_mean_net_cents=float(np.mean(means))*100 if means else None,
        bootstrap_95_cents=[v*100 if v is not None else None for v in interval(means)],
        directional_correct=sum(e['scenario']['underlying_direction_correct'] for e in complete),by_side=byside,
        watch_events=sum(warnings.values()),watch_recoveries=sum(x['event']=='HOLD' for x in result['events']),
        max_watch_per_origin=max(warnings.values(),default=0),median_watch_lead_seconds=float(np.median(leads)) if leads else None,
        first_watch_quotes=first_warnings,post_exit_30s=post,
        later_bid_higher=sum(x['higher'] for x in post),post_exit_n=len(post),
        multiple_entry_contracts={k:v for k,v in counts.items() if v>1},
        min_entry_remaining=min((e['origin']['left'] for e in eps),default=None),
        exact_transferred_tier1_first_predicates=exact_legacy,
        canceled_scenario_diagnostic=dict(n=len(no_recheck),positive=sum(x['net']>1e-10 for x in no_recheck),
            mean_net_cents=float(np.mean([x['net'] for x in no_recheck]))*100 if no_recheck else None),
        rejections=result['rejections'])


def fit_profile(a,b):
    def support(side,exception):
        def selected(result):
            return [e for e in result['episodes'] if e['origin']['side']==side and (e['origin']['ask']>.55)==exception]
        dev,cal=selected(a),selected(b)
        def group(eps):
            clusters=defaultdict(list);valid=[e for e in eps if e['delayed_revalidation']['valid']]
            complete=[e for e in valid if e['scenario'] and not e['censor']]
            for e in complete:clusters[e['origin']['contract']].append(e['scenario']['gross_gain'])
            return [float(np.mean(v)) for v in clusters.values()],len(complete)/max(1,len(valid)),complete
        ag,ac,complete=group(dev);bg,bc,_=group(cal)
        al,bl=interval(ag)[0],interval(bg)[0]
        cost=max([old.fee(e['origin']['ask'])+old.fee(.5)+max(e['origin']['ask']-e['origin']['bid'],.02) for e in dev+cal],default=.06)
        reasons=[]
        if len(ag)<12:reasons.append('DEVELOPMENT_N_LT12')
        if len(bg)<6:reasons.append('CALIBRATION_N_LT6')
        if min(ac,bc)<.8:reasons.append('COMPLETE_COVERAGE_LT80PCT')
        if al is None or bl is None or min(al,bl)<=cost*(2 if exception else 1):reasons.append('COST_STRESSED_LOWER_BOUND_NOT_POSITIVE')
        prices=[v for e in complete for v in (e['origin']['ask'],e['scenario']['entry_ask'])]
        return dict(supported=not reasons,reasons=reasons,development_n=len(ag),calibration_n=len(bg),
            development_proposals=len(dev),calibration_proposals=len(cal),development_coverage=ac,calibration_coverage=bc,
            gross_gain_lower=al,calibration_gross_lower=bl,cost_stress=cost,
            min_ask=min(prices,default=None),max_ask=max(prices,default=None),
            min_left=min((e['origin']['left'] for e in complete),default=None),max_left=max((e['origin']['left'] for e in complete),default=None))
    cells={}
    for side in ('UP','DOWN'):
        cells[side]=support(side,False);cells[side]['exception']=support(side,True)
    return dict(policy='EARLY_UNIFIED_VALUE_RESEARCH_V1',rules=asdict(Rules()),support=cells,
        enabled=False,validated=False,production_authorized=False,signal_only=True,orders=False,
        inference='Contract-level cohort mean uncertainty, not conditional per-entry profit guarantee',
        limitations=['Native source receipt/depth not reconstructed from observation journals','Fee multiplier and reaction delay are explicit stress assumptions','Unresolved supported opportunities are informatively censored'])


def compare_period(name,data,profile=None):
    summaries={};results={}
    for policy in POLICIES:
        result=replay(data,policy)
        summary=summarize(result,data)
        write_json(OUT/(name+'_'+policy+'.json'),dict(summary=summary,**result))
        summaries[policy]=summary;results[policy]=result
    if profile is not None:
        admitted=replay(data,'unified_value',profile,False)
        summaries['economically_admitted']=summarize(admitted,data)
        write_json(OUT/(name+'_admitted.json'),dict(summary=summaries['economically_admitted'],**admitted))
    return summaries,results


def development():
    result={};raw={}
    for name in ('development','calibration'):
        data=load_data(PRIOR/(name+'_inputs.json.gz'))
        result[name],raw[name]=compare_period(name,data)
    profile=fit_profile(raw['development']['unified_value'],raw['calibration']['unified_value'])
    write_json(OUT/'profile_DISABLED.json',profile)
    for name in result:
        data=load_data(PRIOR/(name+'_inputs.json.gz'))
        admitted=replay(data,'unified_value',profile,False)
        result[name]['economically_admitted']=summarize(admitted,data)
    write_json(OUT/'development_comparison.json',result)
    print(json.dumps({n:{p:{k:v[k] for k in ('proposals','delayed_valid','complete','positive','mean_net_cents','entry_ask_cents')} for p,v in d.items()} for n,d in result.items()},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['development']);args=p.parse_args();development()
