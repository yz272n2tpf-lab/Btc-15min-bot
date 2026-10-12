"""One frozen observational comparison. No fitting, network, live writes, or pseudo-fills."""
from collections import Counter,defaultdict
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import argparse,gzip,hashlib,json,statistics
from candidates.early_value_20261011.study import replay as legacy_replay, summarize as legacy_summary
from candidates.early_value_20261011.engine import fee
from .assessment import SAFETY,validate_row,price_group,Rules
from .engine import Engine

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit/early_rebuild_20261012'
INPUTS=[
 ('sep26_27_development','audit/early_condition_20261011/development_inputs.json.gz'),
 ('sep28_29_diagnostic','audit/early_condition_20261011/calibration_inputs.json.gz'),
 ('oct4_diagnostic','audit/early_condition_20261011/diagnostic_inputs.json.gz'),
 ('oct6_diagnostic','audit/early_condition_20261011/acceptance_inputs.json.gz'),
 ('oct7_diagnostic','audit/early_value_20261011/acceptance_inputs.json.gz'),
 ('oct8_diagnostic','audit/early_rebuild_20261012/retained_directional/RESERVED_INPUTS.json.gz'),
 ('oct11_diagnostic','audit/early_rebuild_20261012/retained_directional/UNTOUCHED_INPUTS.json.gz')]


def write(p,x):
    p.write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')

def distribution(v):
    return dict(n=len(v),min=min(v),median=statistics.median(v),mean=statistics.mean(v),max=max(v)) if v else dict(n=0,min=None,median=None,mean=None,max=None)

def first_observed(seq,available,delay):
    # Same frozen 10s human delay and 10s observation tolerance on both legs.
    return next((r for r in seq if r['time']>=available+delay and r['received']<=available+delay+10
                 and not validate_row(r) and r['received']<r['time']+r['left']),None)

def observational_ready(a,s):
    # Unsupported exception groups never enter even a candidate execution diagnostic.
    return bool(s and s['confirmed'] and a['recognized'] and not a['execution_blockers']
                and price_group(a['ask'])=='PRIMARY')

def contract_replay(contract,seq):
    e=Engine();records={};blocks=Counter();q=Rules()
    for r in seq:
        e.process(r)
        for side,a in e.last_assessments.items():
            blocks.update(a.get('authorization_blockers',a.get('recognition_blockers',[])))
            s=e.setups.get(side)
            if not s:continue
            rec=records.setdefault(s['id'],dict(setup=deepcopy(s),first_confirmation=None,
                observational_qualification=None,delayed_recheck=None,status='RECOGNITION_ONLY',
                cancellation_reasons=[],usable_price_end=s['recognized_at'],usable_price_censored=True,
                _price_open=True,_waiting=False,_cancel_latched=False,simulation_origin_id=None))
            if rec['_price_open']:
                if a.get('ask') is not None and .25<=a['ask']<=.55 and not a.get('execution_blockers') and not validate_row(r):
                    if r['received']-rec['usable_price_end']<=q.max_gap:rec['usable_price_end']=r['received']
                    else:rec['_price_open']=False;rec['usable_price_censored']=True
                else:rec['_price_open']=False;rec['usable_price_censored']=False
            if s['confirmed'] and rec['first_confirmation'] is None:
                rec['first_confirmation']=dict(time=r['received'],source_time=r['time'],ask=a['ask'],context=a['features']['context'])
            ready=observational_ready(a,s)
            if rec['observational_qualification'] is None and ready:
                rec['observational_qualification']=dict(time=r['received'],source_time=r['time'],ask=a['ask'],bid=a['bid'],
                    left=r['time']+r['left']-r['received'],context=a['features']['context'])
                rec['_waiting']=True;rec['status']='AWAITING_HYPOTHETICAL_RECHECK'
            qual=rec['observational_qualification']
            if rec['_waiting']:
                if not ready:
                    rec['_cancel_latched']=True
                    rec['cancellation_reasons']=sorted(set(rec['cancellation_reasons']+
                        a.get('recognition_blockers',[])+a.get('execution_blockers',[])+
                        ([] if s['confirmed'] else ['CONFIRMATION_LOST'])+
                        (['PRIMARY_PRICE_WINDOW_LOST'] if price_group(a.get('ask',1))!='PRIMARY' else [])))
                if r['time']>=qual['time']+q.manual_seconds:
                    rec['_waiting']=False
                    rec['delayed_recheck']=dict(available_at=r['received'],source_time=r['time'],ask=a.get('ask'),
                                               actual_observed_elapsed=r['received']-qual['time'])
                    rec['delayed_recheck']['within_tolerance']=r['received']<=qual['time']+q.manual_seconds+10 and not validate_row(r)
                    if rec['_cancel_latched'] or not ready:rec['status']='CANCELED_BEFORE_SIMULATION'
                    elif not rec['delayed_recheck']['within_tolerance']:
                        rec['status']='UNASSESSABLE_DELAYED_RECHECK'
                    else:
                        started=e.start_simulation(side,'diagnostic:'+s['id'],r['received'])
                        if not started['accepted']:rec['status']='UNASSESSABLE_SIMULATION_ORIGIN'
                        else:
                            rec['simulation_origin_id']=started['origin']['id'];rec['status']='SIMULATION_PENDING_EXIT'
        # Invalid/gap data must latch cancellations, including when the assessment lacks a setup.
        for rec in records.values():
            if rec['_waiting'] and (validate_row(r) or not e.history or len(e.history)==1 and
                  r['received']>rec['observational_qualification']['time']):
                rec['_cancel_latched']=True;rec['cancellation_reasons'].append('SOURCE_CONTINUITY_LOST')
    for rec in records.values():
        sid=rec['setup']['id'];side=rec['setup']['side']
        live=next((s for s in list(e.setups.values())+e.setup_archive if s['id']==sid),None)
        rec['reset_at']=live.get('reset_at') if live else None
        rec['usable_price_observed_seconds']=rec['usable_price_end']-rec['setup']['recognized_at']
        if rec['_waiting']:
            rec['status']='CANCELED_BEFORE_SIMULATION' if rec['_cancel_latched'] else 'UNASSESSABLE_DELAYED_RECHECK'
        m=next((m for m in e.managers if m.origin.id==rec['simulation_origin_id']),None)
        rec['hypothetical_after_cost']=None
        if m:
            terminal=m.core.terminal
            rec['management']=dict(origin=asdict(m.origin),terminal=deepcopy(terminal),
                internal_state=m.core.guidance,complete_source_observation_path=m.core.origin['complete'],
                final_contribution='UNVERIFIED_ON_OBSERVATION_INPUTS',
                transitions=deepcopy(m.core.events))
            entry=rec['delayed_recheck'];at=entry['available_at'];ask=entry['ask']
            sold=first_observed(seq,terminal['available'],q.exit_execution_seconds) if terminal else None
            end=sold['received'] if sold else seq[-1]['received']
            path=[r for r in seq if at<=r['received']<=end]
            intact=(m.core.origin['complete'] if terminal is None else terminal['complete']) and all(not validate_row(r) for r in path)
            intact &= not any(b['time']-a['time']>q.max_gap or b['source_epoch']!=a['source_epoch'] for a,b in zip(path,path[1:]))
            rec['observed_downside_cents']=100*(min((r[side.lower()+'_bid'] for r in path if not validate_row(r)),default=ask)-ask)
            rec['downside_basis']='Worst OBSERVED bid versus refreshed ask; not guaranteed executable and never selected as the exit'
            if not terminal:rec['status']='CENSORED_NO_CONDITION_EXIT'
            elif not sold:rec['status']='CENSORED_NO_DELAYED_EXIT_QUOTE'
            elif not intact:rec['status']='CENSORED_INCOMPLETE_OBSERVATION_PATH'
            else:
                bid=sold[side.lower()+'_bid']
                reserve=max(.02,rec['observational_qualification']['ask']-rec['observational_qualification']['bid'],
                            ask-next(r for r in seq if r['received']==at)[side.lower()+'_bid'],
                            sold[side.lower()+'_ask']-bid)
                rec['status']='COMPLETE_HYPOTHETICAL_QUOTE_SCENARIO'
                rec['hypothetical_after_cost']=dict(**SAFETY,entry_ask=ask,exit_bid=bid,
                    entry_fee_stress=fee(ask),exit_fee_stress=fee(bid),reserve=reserve,
                    net_cents=100*(bid-ask-fee(ask)-fee(bid)-reserve),
                    entry_actual_observed_elapsed=entry['actual_observed_elapsed'],
                    exit_actual_observed_elapsed=sold['received']-terminal['available'],
                    exit_observed_at=sold['received'],realized_profit=None,manual_fill=None,
                    label='Hypothetical top-of-book scenario; native receipts/depth/fees/fills unverified')
        for k in list(rec):
            if k.startswith('_'):del rec[k]
    return list(records.values()),dict(blocks),len(e.tickets)


def summarize(records,blocks,tickets):
    complete=[r for r in records if r['hypothetical_after_cost']]
    cluster=defaultdict(list)
    for r in complete:cluster[r['setup']['contract']].append(r['hypothetical_after_cost']['net_cents'])
    status=Counter(r['status'] for r in records)
    by={}
    for side in ('UP','DOWN'):
        for context in ('CONTINUATION','PRE_CROSSING'):
            rr=[r for r in records if r['setup']['side']==side and r['setup']['initial_context']==context]
            cc=[r for r in rr if r['hypothetical_after_cost']]
            by[side+'_'+context]=dict(setups=len(rr),confirmed=sum(r['first_confirmation'] is not None for r in rr),
                observational_primary_qualifications=sum(r['observational_qualification'] is not None for r in rr),
                complete_quote_scenarios=len(cc),net_cents=distribution([r['hypothetical_after_cost']['net_cents'] for r in cc]))
    return dict(distinct_setups=len(records),setup_contracts=len(set(r['setup']['contract'] for r in records)),
        algorithmically_confirmed=sum(r['first_confirmation'] is not None for r in records),
        observational_primary_qualifications=sum(r['observational_qualification'] is not None for r in records),
        qualified_research_tickets=tickets,real_entries=0,independent_economic_evaluations=0,
        status_counts=dict(status),by_side_context=by,
        recognition_ask_cents=distribution([100*r['setup']['recognition_ask'] for r in records]),
        observational_qualification_ask_cents=distribution([100*r['observational_qualification']['ask'] for r in records if r['observational_qualification']]),
        delayed_recheck_ask_cents=distribution([100*r['delayed_recheck']['ask'] for r in records if r['delayed_recheck'] and r['delayed_recheck']['ask'] is not None]),
        actual_observed_entry_delay_seconds=distribution([r['delayed_recheck']['actual_observed_elapsed'] for r in records if r['delayed_recheck']]),
        observed_usable_price_seconds=distribution([r['usable_price_observed_seconds'] for r in records]),
        usable_price_right_censored=sum(r['usable_price_censored'] for r in records),
        complete_quote_scenario_contracts=len(cluster),net_quote_cents=distribution([r['hypothetical_after_cost']['net_cents'] for r in complete]),
        positive_quote_scenarios=sum(r['hypothetical_after_cost']['net_cents']>1e-9 for r in complete),
        contract_mean_quote_net_cents=distribution([statistics.mean(v) for v in cluster.values()]),
        observed_downside_cents=distribution([r['observed_downside_cents'] for r in records if 'observed_downside_cents' in r]),
        repeated_setup_contracts=sum(v>1 for v in Counter(r['setup']['contract'] for r in records).values()),
        distinct_same_side_requalifications=sum(max(0,v-1) for v in Counter((r['setup']['contract'],r['setup']['side']) for r in records).values()),
        both_side_recognition_contracts=sum(len(v)>1 for v in _side_sets(records).values()),
        overlapping_observation_blockers=dict(blocks),
        cancellations=dict(Counter(v for r in records for v in set(r['cancellation_reasons']))),
        uncertainty='No independent profitability CI: all cohorts exposed, paths observational, missing native execution proof; complete-only means are informatively censored')

def _side_sets(records):
    result=defaultdict(set)
    for r in records:result[r['setup']['contract']].add(r['setup']['side'])
    return result


def run(destination):
    destination.mkdir(parents=True,exist_ok=True)
    all_records=[];all_blocks=Counter();periods={};seen=set();input_manifest=[];baseline_eps=[]
    profile=json.loads((ROOT/'audit/early_value_20261011/profile_DISABLED.json').read_text())
    for name,p in INPUTS:
        path=ROOT/p;data=json.loads(gzip.decompress(path.read_bytes()))
        assert not seen.intersection(data),'OVERLAPPING_CONTRACTS';seen.update(data)
        rows=[r for seq in data.values() for r in seq]
        input_manifest.append(dict(period=name,path=p,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
             contracts=sorted(data),observations=len(rows),first=min(r['received'] for r in rows),last=max(r['received'] for r in rows),
             evidence_class='PREVIOUSLY_EXPOSED_OBSERVATIONAL_DIAGNOSTIC'))
        records=[];blocks=Counter();tickets=0
        for contract,seq in sorted(data.items(),key=lambda item:item[1][0]['received']):
            rr,bb,tt=contract_replay(contract,seq);records+=rr;blocks.update(bb);tickets+=tt
        prior=legacy_replay(data,'unified_value',proposal=True)
        admitted=legacy_replay(data,'unified_value',profile,False)
        bsum=legacy_summary(prior,data)
        oldevents=[v for v in prior['events'] if v['event']=='BUY']
        lead=[]
        for rec in records:
            matching=[b for b in oldevents if b['contract']==rec['setup']['contract'] and b['side']==rec['setup']['side'] and
                       b['time']>=rec['setup']['recognition_source_time'] and
                       (rec['reset_at'] is None or b['time']<rec['reset_at'])]
            rec['legacy_proposal_match']=matching[0] if matching else None
            if matching:
                lead.append(matching[0]['time']-rec['setup']['recognition_source_time'])
        summary=summarize(records,blocks,tickets)
        summary.update(input_contracts=len(data),observations=len(rows),
            matched_legacy_proposal_recognition_lead_source_seconds=distribution(lead),
            legacy_unified=bsum,legacy_economic_tickets=len(admitted['episodes']))
        periods[name]=summary
        write(destination/(name+'.json'),dict(**SAFETY,summary=summary,setups=records,baseline=prior))
        all_records+=records;all_blocks.update(blocks);baseline_eps+=prior['episodes']
        print(name,json.dumps({k:summary[k] for k in ('input_contracts','distinct_setups','algorithmically_confirmed','observational_primary_qualifications','status_counts','qualified_research_tickets')}),flush=True)
    aggregate=summarize(all_records,all_blocks,sum(p['qualified_research_tickets'] for p in periods.values()))
    aggregate.update(input_contracts=len(seen),observations=sum(p['observations'] for p in periods.values()),
       legacy_proposals=len(baseline_eps),legacy_delayed_valid=sum(e['delayed_revalidation']['valid'] for e in baseline_eps),
       legacy_economic_tickets=sum(p['legacy_economic_tickets'] for p in periods.values()),
       legacy_qualified_research_tickets=0,live_identity='NOT_VERIFIED',
       earlier_usable_buy_opportunities='UNPROVEN',economic_evidence='UNPROVEN')
    write(destination/'INPUTS.json',input_manifest)
    write(destination/'COMPARISON.json',dict(**SAFETY,aggregate=aggregate,periods=periods))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(OUT/'evaluation'))
    args=parser.parse_args();dest=Path(args.output).resolve()
    if not dest.is_relative_to(OUT.resolve()):raise SystemExit('Output must remain under isolated audit/early_rebuild_20261012')
    run(dest)
