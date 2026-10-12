"""One offline exposed-data pass for NEW continuation labels, not an old replay."""
from collections import Counter,defaultdict
from copy import deepcopy
from pathlib import Path
import argparse,gzip,hashlib,json,statistics
from .assessment import SAFETY,Rules,features,validate_row
from .continuation import METHOD,fit,ContinuationEstimator,code_identity
from .continuation_engine import ContinuationEngine,common_eligibility
from .durability import label,CHECKPOINTS,net_cents
from .resale import digest
from .management import Management,Origin

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'audit/early_continuation_20261012'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,sort_keys=True,indent=2,allow_nan=False)+'\n')
def packed(p,v):p.write_bytes(gzip.compress(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode(),mtime=0))
def stats(v):return dict(n=len(v),mean=statistics.mean(v) if v else None,median=statistics.median(v) if v else None,min=min(v) if v else None,max=max(v) if v else None)


def summary(rows):
    n=len(rows);unknown=sum(r['y'] is None for r in rows);success=sum(r['y']==1 for r in rows)
    episodes=[e for r in rows for e in r['episodes']]
    entries=[r for r in rows if r['entry']]
    delayed=[r['delayed_price_observation'] for r in rows if r.get('delayed_price_observation')]
    return dict(attempts=n,contracts=len({r['contract'] for r in rows}),status=dict(Counter(r['status'] for r in rows)),
        success_bounds=[success/n,(success+unknown)/n] if n else None,entry_count=len(entries),
        price_lost=sum(r['price_lost'] for r in rows),burst_observed=sum(r['burst_observed'] for r in rows),
        delayed_price=dict(observed=len(delayed),unavailable=n-len(delayed),above55=sum(d['ask']>.55 for d in delayed),
            below25=sum(d['ask']<.25 for d in delayed),primary=sum(d['primary'] for d in delayed),
            delay_seconds=stats([d['elapsed'] for d in delayed])),
        entry_delay_seconds=stats([r['entry']['elapsed'] for r in entries]),
        entry_ask_cents=stats([100*r['entry']['ask'] for r in entries]),
        episode_span_seconds=stats([e['span'] for e in episodes]),
        maximum_episode_per_entry_seconds=stats([max((e['span'] for e in r['episodes']),default=0) for r in entries]),
        coverage_fraction=stats([r['coverage_fraction'] for r in entries]),
        worst_observed_net_cents=stats([r['worst_observed_net_cents'] for r in entries if r['worst_observed_net_cents'] is not None]),
        first_certificate_delayed_net_cents=stats([r['delayed_liquidation']['net_cents'] for r in rows if r['delayed_liquidation']]),
        checkpoints={str(s):dict(runway_possible=sum(r['checkpoints'][str(s)]['runway_possible'] for r in entries),
            observed_attempts=sum(r['checkpoints'][str(s)]['observed_certificates']>0 for r in entries),
            accessible_attempts=sum(r['checkpoints'][str(s)]['accessible']>0 for r in entries),
            delayed_failed_attempts=sum(r['checkpoints'][str(s)]['delayed_failed']>0 for r in entries),
            delayed_unknown_attempts=sum(r['checkpoints'][str(s)]['delayed_unknown']>0 for r in entries),
            primary_success_and_accessible=sum(r['y']==1 and r['checkpoints'][str(s)]['accessible']>0 for r in entries)) for s in CHECKPOINTS})


def managed_new(lm,result,tape,retained):
    """Only a new selected origin; inherited manager and all its expiry semantics."""
    if not result['entry']:return dict(status='NO_ENTRY',net_cents=None)
    entry=result['entry'];r=tape[entry['index']]['row'];old=retained.get(lm['setup_id'])
    if old and old.get('management') and old['management']['origin']['entry_time']==entry['time']:
        h=old['hypothetical_after_cost']
        return dict(status=old['status'],net_cents=h['net_cents'] if h else None,reused=True,
            final_verified=False,terminal=old['management']['terminal'])
    seq=[t['row'] for t in tape];hist=[z for z in seq[:entry['index']+1] if z['time']>=r['time']-135]
    o=Origin(digest([lm['id'],'simulation']),lm['setup_id'],None,r['contract'],lm['side'],'SIMULATED',entry['time'],entry['ask'],1,'QUOTE_ONLY_COMPARISON_SIZE_ASSUMPTION')
    m=Management(o,hist,r,features(hist,r,lm['side'],Rules()),Rules());prev=r
    for row in seq[entry['index']+1:]:
        if row['received']>=prev['time']+10:m.unavailable('SOURCE_EXPIRED_WITHOUT_NEW_OBSERVATION')
        if validate_row(row):m.unavailable('INVALID_SOURCE');hist=[];prev=row;continue
        if row['time']-prev['time']>15 or row['source_epoch']!=prev['source_epoch']:
            m.unavailable('SOURCE_GAP_OR_EPOCH_CHANGE');hist=[]
        hist.append(row);hist=[z for z in hist if z['time']>=row['time']-135]
        m.update(hist,row);prev=row
    term=m.core.terminal;sale=None
    if term:
        sale=next((z for z in seq if z['time']>=term['available']+10 and z['received']<=term['available']+20
                   and not validate_row(z) and z['received']<z['time']+z['left']),None)
    intact=bool(term and term['complete'] and sale)
    return dict(status='COMPLETE_HYPOTHETICAL' if intact else 'CENSORED_MANAGEMENT_PATH',
        net_cents=net_cents(tape[lm['index']]['row'],r,sale,lm['side']) if intact else None,
        reused=False,final_verified=False,terminal=term)


def scan(data,period,estimator):
    tapes={};marks=[];recognized=set();confirmed=set()
    for contract,seq in sorted(data.items(),key=lambda kv:kv[1][0]['received']):
        e=ContinuationEngine(estimator);tape=[]
        for index,r in enumerate(seq):
            previous=len(e.landmarks);e.process(r)
            sides={side:dict(**common_eligibility(a,e.setups.get(side)),score=deepcopy(a['economics']),
                            short_agreement=(min(a['features']['move_short'],a['features']['brti_short'])>0 if a.get('features') else None))
                   for side,a in e.last_assessments.items()}
            tape.append(dict(row=r,sides=sides))
            for lm in e.landmarks[previous:]:lm.update(index=index,period=period);marks.append(deepcopy(lm))
        recognized.update(ev['setup']['id'] for ev in e.events if ev['event']=='SETUP_RECOGNIZED')
        confirmed.update(ev['setup_id'] for ev in e.events if ev['event']=='SETUP_CONFIRMED')
        if e.tickets:raise ValueError('UNAUTHORIZED_RESEARCH_TICKET')
        tapes[contract]=tape
    return tapes,marks,dict(recognized=len(recognized),confirmed=len(confirmed))


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    freeze=json.loads((BASE/'FREEZE.json').read_text())
    if freeze['code_identity']!=code_identity() or freeze['study_sha256']!=sha(Path(__file__)) or freeze['method_sha256']!=digest(METHOD):raise ValueError('FROZEN_IMPLEMENTATION_CHANGED')
    if (out/'RESULTS.json').exists():raise ValueError('OUTPUT_EXISTS_USE_NEW_DIRECTORY_FOR_EXPLICIT_REPRODUCTION')
    manifest=json.loads((ROOT/'audit/early_rebuild_20261012/evaluation/INPUTS.json').read_text())
    baseline_files={r['path']:r['sha256'] for r in json.loads((BASE/'COPY_BASELINE.json').read_text())['records']}
    ledger=[];landmarks=[];retained={};all_tapes={};periods={};estimator=None;artifact=None;seen=set();last_close=None
    for n,item in enumerate(manifest):
        path=ROOT/item['path'];rp='audit/early_rebuild_20261012/evaluation/'+item['period']+'.json'
        if sha(path)!=item['sha256'] or sha(ROOT/rp)!=baseline_files[rp]:raise ValueError('INPUT_HASH_CONFLICT')
        data=json.loads(gzip.decompress(path.read_bytes()))
        if set(data)!=set(item['contracts']) or seen.intersection(data):raise ValueError('CONTRACT_IDENTITY_CONFLICT')
        seen.update(data)
        first=min(r['received'] for seq in data.values() for r in seq)
        if last_close is not None and first<last_close:raise ValueError('PARTITION_CHRONOLOGY')
        last_close=max(r['time']+r['left'] for seq in data.values() for r in seq)
        old=json.loads((ROOT/rp).read_text())['setups'];retained.update({r['setup']['id']:r for r in old})
        tapes,marks,counts=scan(data,item['period'],estimator)
        expected={(r['setup']['id'],r['observational_qualification']['time']) for r in old if r['observational_qualification']}
        firstmarks={}
        for lm in marks:firstmarks.setdefault(lm['setup_id'],lm)
        actual={(lm['setup_id'],lm['decision_time']) for lm in firstmarks.values()}
        if actual!=expected:raise ValueError('COMMON_COMPARATOR_CHANGED:'+str((actual-expected,expected-actual)))
        labels=[label(lm,tapes[lm['contract']]) for lm in marks]
        for lm,lab in zip(marks,labels):
            lab['feature_error']=lm['feature_error'];lab['score']=lm['score'];lab['first_common']=firstmarks[lm['setup_id']]['id']==lm['id']
        ledger+=labels;landmarks+=marks;all_tapes.update(tapes)
        periods[item['period']]=dict(contracts=len(data),observations=sum(len(v) for v in data.values()),**counts,
            landmarks=len(marks),labels=summary(labels),comparator=summary([r for r in labels if r['first_common']]))
        print(item['period'],json.dumps({**counts,'landmarks':len(marks),'labels':dict(Counter(r['status'] for r in labels))}),flush=True)
        if n==1:
            try:
                artifact=fit([r for r in ledger if r['period']==METHOD['train']],labels,manifest[:2])
                write(out/'CONTINUATION_ARTIFACT.json',artifact)
                estimator=ContinuationEstimator(artifact,expected_sha256=artifact['artifact_sha256'])
                write(out/'ARTIFACT_FROZEN_BEFORE_DIAGNOSTIC.json',dict(artifact_sha256=artifact['artifact_sha256'],file_sha256=sha(out/'CONTINUATION_ARTIFACT.json'),diagnostic_labels_opened=False))
                print('FIT_COMPLETE',artifact['artifact_sha256'],flush=True)
            except (ValueError,ArithmeticError) as exc:
                write(out/'ESTIMATION_UNAVAILABLE.json',dict(reason=str(exc)));print('FIT_UNAVAILABLE',str(exc),flush=True)
    byid={r['id']:r for r in ledger};selected=[];selected_lm=[];used=set();policy_cancel=[];management=[]
    for lm in landmarks:
        if lm['score'].get('diagnostic_selected') and lm['setup_id'] not in used:
            used.add(lm['setup_id']);lab=deepcopy(byid[lm['id']]);selected_lm.append(lm)
            tape=all_tapes[lm['contract']]
            if lab['entry']:
                for point in tape[lm['index']+1:lab['entry']['index']+1]:
                    sc=point['sides'][lm['side']]['score']
                    if not sc.get('diagnostic_selected') or point['row']['received']>=sc.get('expires_at',0):
                        policy_cancel.append(lm['id']);lab.update(y=0,status='MODEL_SCORE_CANCELED_ENTRY',underlying_path_y=lab['y'],entry=None);break
            selected.append(lab)
            if lab['entry']:management.append(dict(landmark_id=lm['id'],contract=lm['contract'],side=lm['side'],**managed_new(lm,lab,tape,retained)))
    later=[r for r in ledger if r['period'] not in (METHOD['train'],METHOD['calibration_period'])]
    baseline=[r for r in later if r['first_common']]
    supported=[r for r in later if r['score']['probability'] is not None]
    measured=[r for r in supported if r['y'] is not None]
    prior=float(artifact['body']['training_prevalence']) if artifact else None
    def direction(rows):return {side:summary([r for r in rows if r['side']==side]) for side in ('UP','DOWN')}
    bcontracts={r['contract'] for r in baseline if r['y']==1};scontracts={r['contract'] for r in selected if r['y']==1}
    summary_result=dict(**SAFETY,method=METHOD,fit_status=('EXPLORATORY_QUOTE_ONLY' if artifact['body']['calibration_intercept_applied'] else 'UNCALIBRATED_EXPLORATORY_QUOTE_ONLY') if artifact else 'UNESTIMATED',
        artifact_sha256=artifact['artifact_sha256'] if artifact else None,periods=periods,
        input_contracts=len(seen),input_rows=sum(len(t) for t in all_tapes.values()),all_periods_exposed=True,
        later_landmarks=len(later),supported_predictions=len(supported),supported_labeled_predictions=len(measured),
        unsupported=dict(Counter(r['score']['reasons'][-1] for r in later if r['score']['probability'] is None)),
        brier=statistics.mean((r['score']['probability']-r['y'])**2 for r in measured) if measured else None,
        training_prevalence_brier=statistics.mean((prior-r['y'])**2 for r in measured) if measured else None,
        baseline_observational=summary(baseline),candidate=summary(selected),baseline_by_direction=direction(baseline),candidate_by_direction=direction(selected),
        all_first_common=summary([r for r in ledger if r['first_common']]),
        model_score_cancellations=len(policy_cancel),baseline_success_contract_capture=len(bcontracts&scontracts)/len(bcontracts) if bcontracts else None,
        newly_identified_success_contracts=sorted(scontracts-bcontracts),candidate_managed=stats([r['net_cents'] for r in management if r['net_cents'] is not None]),
        candidate_managed_status=dict(Counter(r['status'] for r in management)),
        actual_native_supported_labels=0,actual_native_supported_selections=0,full_native_FINAL_verified=False,
        independent_validation=False,economic_readiness=False,
        exposed_inherited_baseline=json.loads((ROOT/'audit/early_rebuild_20261012/evaluation/COMPARISON.json').read_text())['aggregate']['net_quote_cents'],
        limitations=['NO_ORIGINAL_RECEIPTS','NO_SIZE_DEPTH_CHAINS','NO_APPLICABLE_FEES','EXPOSED_AND_INFORMATIVELY_CENSORED',
                     'DEPENDENT_OVERLAPPING_LANDMARKS','NO_PORTFOLIO_OR_REALIZED_RETURN','NO_NATIVE_FINAL_PATH'])
    packed(out/'LABEL_LEDGER.json.gz',ledger);packed(out/'LANDMARKS.json.gz',landmarks)
    write(out/'SELECTED_ATTEMPTS.json',selected);write(out/'NEW_MANAGEMENT_RESULTS.json',management)
    write(out/'SOURCE_MANIFEST.json',manifest);write(out/'RESULTS.json',summary_result)
    print(json.dumps({k:summary_result[k] for k in ('fit_status','later_landmarks','supported_predictions','brier','training_prevalence_brier','candidate','baseline_observational')},indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default=str(BASE/'evaluation'));a=p.parse_args();out=Path(a.output).resolve()
    if not out.is_relative_to(BASE):raise SystemExit('ISOLATED_AUDIT_OUTPUT_REQUIRED')
    run(out)
