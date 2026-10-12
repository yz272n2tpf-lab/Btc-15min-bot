"""One frozen fit and targeted checks. Reuses prior selection and terminal labels."""
from collections import Counter,defaultdict
from copy import deepcopy
import gzip,hashlib,json,statistics
from pathlib import Path
from .assessment import SAFETY,Rules,features,validate_row
from .management import Origin,Management,ThesisRecoveryManagement
from .execution import bind_native,execution_assessment
from .resale import METHOD,digest,build_label,fit,Estimator,causal_features

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit/early_blocker_resolution_20261012'


def write(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def native_row():
    raw=json.loads((ROOT/'audit/existing_evidence_20261011/early_native_replay_frame.json').read_text())
    f=raw['frame']
    r=dict(contract=f['contract'],target=f['target'],time=f['feature_cutoff'],received=raw['decision_ts'],
        left=f['official_close']-f['feature_cutoff'],btc=f['btc_price'],brti=f['brti']['value'],
        side=f['fair']['side'],p=f['fair']['fair'],publication_id=digest(f),source_epoch=f['native_epoch'],
        healthy=True,evidence_class='RETAINED_NATIVE_FRAME',native_frame=deepcopy(f))
    r.update({k:f[k] for k in ('up_bid','up_ask','down_bid','down_ask')})
    return r


def history_at(seq,at):
    hist=[];prev=None
    for r in seq:
        if r['received']>at:break
        if validate_row(r):hist=[];prev=r;continue
        if prev and (r['time']-prev['time']>15 or r['source_epoch']!=prev['source_epoch']):hist=[]
        hist.append(r);hist=[v for v in hist if v['time']>=r['time']-135];prev=r
    return hist


def management_pair(rec,seq):
    o=Origin(**rec['management']['origin']);hist=history_at(seq,o.entry_time);r=hist[-1]
    x=features(hist,r,o.side,Rules())
    baseline=Management(o,hist,r,x,Rules());candidate=ThesisRecoveryManagement(o,hist,r,x,Rules())
    changed=0;recoveries=0;previous=r
    for r in seq:
        if r['received']<=o.entry_time:continue
        # Engine.process calls tick BEFORE consuming the next row. A >=10s
        # publication hiatus resets management even when the <=15s history remains.
        if r['received']>=previous['time']+Rules().max_age:
            baseline.unavailable('SOURCE_EXPIRED_WITHOUT_NEW_OBSERVATION')
            candidate.unavailable('SOURCE_EXPIRED_WITHOUT_NEW_OBSERVATION')
        if validate_row(r):
            baseline.unavailable('INVALID_SOURCE');candidate.unavailable('INVALID_SOURCE');hist=[];previous=r;continue
        gap=r['time']-previous['time']>15 or r['source_epoch']!=previous['source_epoch']
        if gap:
            baseline.unavailable('SOURCE_GAP_OR_EPOCH_CHANGE');candidate.unavailable('SOURCE_GAP_OR_EPOCH_CHANGE');hist=[]
        hist.append(r);hist=[v for v in hist if v['time']>=r['time']-135]
        a=baseline.update(hist,r);b=candidate.update(hist,r)
        changed+=a['internal_state']!=b['internal_state']
        recoveries+=b['reasons']==['PRE_CROSSING_APPROACH_RECOVERED_TARGET_NOT_REQUIRED']
        previous=r
    return dict(setup_id=rec['setup']['id'],contract=o.contract,side=o.side,
        initial_entry_context=x['context'],state_difference_rows=changed,recovery_rows=recoveries,
        baseline_terminal_matches_retained=baseline.core.terminal==rec['management']['terminal'],
        candidate_terminal_matches_baseline=candidate.core.terminal==baseline.core.terminal,
        candidate_terminal=candidate.core.terminal,baseline_terminal=baseline.core.terminal,
        origins_equal=candidate.origin==baseline.origin==o,
        source_complete_equal=candidate.core.origin['complete']==baseline.core.origin['complete'],
        full_native_FINAL_path_verified=False,
        inherited_quote_net_cents=rec['hypothetical_after_cost']['net_cents'] if rec['hypothetical_after_cost'] else None)


def stats(v):
    return dict(n=len(v),mean=statistics.mean(v) if v else None,median=statistics.median(v) if v else None)


def run():
    frozen=json.loads((OUT/'FREEZE.json').read_text())
    if frozen['method_sha256']!=digest(METHOD):raise ValueError('METHOD_CHANGED_AFTER_FREEZE')
    for path,h in frozen['implementation_sha256'].items():
        if sha(ROOT/path)!=h:raise ValueError('IMPLEMENTATION_CHANGED_AFTER_FREEZE:'+path)
    copied=json.loads((OUT/'COPY_BASELINE.json').read_text())['source_files_sha256']
    inputs=json.loads((ROOT/'audit/early_rebuild_20261012/evaluation/INPUTS.json').read_text())
    ledger=[];all_data={};records=[];sources=[];groups={}
    for item in inputs:
        p=ROOT/item['path'];result_path='audit/early_rebuild_20261012/evaluation/'+item['period']+'.json'
        if sha(p)!=item['sha256'] or sha(ROOT/result_path)!=copied[result_path]:raise ValueError('RETAINED_INPUT_IDENTITY')
        data=json.loads(gzip.decompress(p.read_bytes()))
        if set(data)!=set(item['contracts']) or set(all_data).intersection(data):raise ValueError('CONTRACT_MEMBERSHIP')
        all_data.update(data);rr=json.loads((ROOT/result_path).read_text())['setups'];records+=rr
        for rec in rr:
            label=build_label(rec,data[rec['setup']['contract']]);label['period']=item['period'];ledger.append(label)
        groups[item['period']]=sorted(data)
        sources.append(dict(period=item['period'],input_path=item['path'],input_sha256=sha(p),
                            result_path=result_path,result_sha256=sha(ROOT/result_path)))
    write('LABEL_LEDGER.json',ledger)
    train=[r for r in ledger if r['period']==METHOD['train_period']]
    later=[r for r in ledger if r['period']!=METHOD['train_period']]
    management_sha=frozen['baseline_management_sha256']
    artifact=fit(train,sources[:1],management_sha);write('EXPLORATORY_RESALE_ARTIFACT.json',artifact)
    estimator=Estimator(artifact,expected_sha256=artifact['artifact_sha256'],management_sha256=management_sha)
    predictions=[]
    for row in later:
        if row['features'] is None:continue
        r,x=causal_features(all_data[row['contract']],row['decision_time'],row['side'])
        pred=estimator.infer(r,row['side'],x,selection_point=True)
        predictions.append(dict(setup_id=row['setup_id'],contract=row['contract'],status=row['status'],
            net_cents=row['net_cents'],label_error=row['label_error'],estimate=pred))
    write('EXPOSED_LATER_PREDICTIONS.json',predictions)
    estimated=[p for p in predictions if p['estimate']['status']=='EXPLORATORY_QUOTE_ESTIMATE']
    measured=[p for p in estimated if p['net_cents'] is not None]
    selected=[p for p in estimated if p['estimate']['diagnostic_selected']]
    paired=[management_pair(r,all_data[r['setup']['contract']]) for r in records if r.get('simulation_origin_id')]
    write('MANAGEMENT_MATCHED.json',paired)
    nr=native_row();binding=bind_native(nr,nr['received']);native=execution_assessment(nr,'UP',nr['received'])
    write('ACTUAL_NATIVE_BINDING.json',dict(source='audit/existing_evidence_20261011/early_native_replay_frame.json',
          source_sha256=sha(ROOT/'audit/existing_evidence_20261011/early_native_replay_frame.json'),
          row=nr,binding=binding,execution=native,actual_full_packets=0,actual_orderbook_chains=0,
          historical_observation_rows=sum(len(v) for v in all_data.values()),
          historical_rows_with_native_frame=sum('native_frame' in r for vv in all_data.values() for r in vv)))
    overlaps=0
    sims=[r for r in ledger if r.get('entry_time')]
    for i,a in enumerate(sims):
        for b in sims[i+1:]:
            if a['contract']==b['contract'] and max(a['entry_time'],b['entry_time'])<min(a['exit_time'],b['exit_time']):overlaps+=1
    summary=dict(**SAFETY,method=METHOD,artifact_sha256=artifact['artifact_sha256'],
        fit_status='EXPLORATORY_QUOTE_ESTIMATE',economic_readiness=False,independent_validation=False,
        split_contracts={k:len(v) for k,v in groups.items()},all_periods_previously_exposed=True,
        ledger_status_counts=dict(Counter(r['status'] for r in ledger)),label_errors=dict(Counter(r['label_error'] for r in ledger if r['label_error'])),
        train_complete_labels=sum(r['net_cents'] is not None for r in train),
        later_complete_labels=sum(r['net_cents'] is not None for r in later),
        cells={k:{n:v[n] for n in ('n','contracts','min','max','coefficients','residual_q10')} for k,v in artifact['body']['cells'].items()},
        later_qualification_predictions=len(predictions),supported_predictions=len(estimated),
        unsupported_reasons=dict(Counter(p['estimate']['reasons'][-1] for p in predictions if p not in estimated)),
        supported_status_counts=dict(Counter(p['status'] for p in estimated)),
        matched_complete_prediction_error=dict(mae=stats([abs(p['estimate']['expected_net_cents']-p['net_cents']) for p in measured]),
          bias=stats([p['estimate']['expected_net_cents']-p['net_cents'] for p in measured]),
          observed_net=stats([p['net_cents'] for p in measured]),
          training_cell_mean_mae=stats([abs(p['net_cents']-statistics.mean([r['net_cents'] for r in train if r['net_cents'] is not None and r['cell']==p['estimate']['side']+'_'+p['estimate']['context']])) for p in measured])),
        diagnostic_selected=len(selected),selected_status_counts=dict(Counter(p['status'] for p in selected)),
        selected_complete_observed_net=stats([p['net_cents'] for p in selected if p['net_cents'] is not None]),
        complete_path_overlap_pairs=overlaps,
        management_pairs=len(paired),baseline_retained_terminal_mismatches=sum(not p['baseline_terminal_matches_retained'] for p in paired),
        candidate_baseline_terminal_differences=sum(not p['candidate_terminal_matches_baseline'] for p in paired),
        management_paths_with_state_changes=sum(p['state_difference_rows']>0 for p in paired),
        management_state_difference_rows=sum(p['state_difference_rows'] for p in paired),
        management_correction_economic_improvement_claim=False,
        inherited_complete_net=stats([r['net_cents'] for r in ledger if r['net_cents'] is not None]),
        limitations=artifact['body']['limitations']+['COMPLETE_PATH_OVERLAPS_ARE_NOT_ALL_SIMULATION_OVERLAPS',
                 'FULL_NATIVE_FINAL_UNAVAILABLE','TRAINED_MODEL_CAN_BE_WRONG','NOT_SEQUENTIAL_PORTFOLIO_RETURN'])
    write('RESULTS.json',summary);write('SOURCE_MANIFEST.json',sources)
    print(json.dumps({k:summary[k] for k in ['fit_status','train_complete_labels','later_complete_labels','label_errors','supported_predictions','diagnostic_selected','matched_complete_prediction_error','management_pairs','baseline_retained_terminal_mismatches','candidate_baseline_terminal_differences','management_paths_with_state_changes']},indent=2))

def management_only():
    """Repair only the matched diagnostic wrapper; no refit or BUY replay."""
    data={};records=[]
    for item in json.loads((ROOT/'audit/early_rebuild_20261012/evaluation/INPUTS.json').read_text()):
        p=ROOT/item['path']
        if sha(p)!=item['sha256']:raise ValueError('INPUT_IDENTITY')
        data.update(json.loads(gzip.decompress(p.read_bytes())))
        records+=json.loads((ROOT/('audit/early_rebuild_20261012/evaluation/'+item['period']+'.json')).read_text())['setups']
    paired=[management_pair(r,data[r['setup']['contract']]) for r in records if r.get('simulation_origin_id')]
    write('MANAGEMENT_MATCHED.json',paired)
    s=json.loads((OUT/'RESULTS.json').read_text())
    s.update(baseline_retained_terminal_mismatches=sum(not p['baseline_terminal_matches_retained'] for p in paired),
        candidate_baseline_terminal_differences=sum(not p['candidate_terminal_matches_baseline'] for p in paired),
        management_paths_with_state_changes=sum(p['state_difference_rows']>0 for p in paired),
        management_state_difference_rows=sum(p['state_difference_rows'] for p in paired),
        management_diagnostic_correction='Restored inherited Engine.tick source-expiry event before each row; no model refit or policy change')
    write('RESULTS.json',s)
    print(json.dumps({k:v for k,v in s.items() if k.startswith(('management_','baseline_retained','candidate_baseline'))},indent=2))

if __name__=='__main__':
    import sys
    if '--management-only' in sys.argv:management_only()
    else:run()
