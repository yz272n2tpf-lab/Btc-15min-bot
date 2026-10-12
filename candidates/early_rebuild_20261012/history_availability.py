"""Narrow saved-landmark availability check. Never fit, predict, select or label."""
from collections import Counter
from pathlib import Path
import gzip,hashlib,json
from .continuation import causal_vector
from .underlying_history import UnderlyingHistory,observed_proxy

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit/early_history_20261012'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def run():
    baseline={v['path']:v['sha256'] for v in json.loads((OUT/'COPY_BASELINE.json').read_text())['records']}
    ledger_path=ROOT/'audit/early_continuation_20261012/evaluation/LANDMARKS.json.gz'
    if sha(ledger_path)!=baseline[str(ledger_path.relative_to(ROOT))]:raise ValueError('LANDMARK_PROVENANCE_MISMATCH')
    marks=json.loads(gzip.decompress(ledger_path.read_bytes()))
    missing=[m for m in marks if m['feature_error']=='CAUSAL_120S_HISTORY_UNAVAILABLE']
    manifest=json.loads((ROOT/'audit/early_rebuild_20261012/evaluation/INPUTS.json').read_text())
    results=[];input_checks=[]
    for item in manifest:
        path=ROOT/item['path']
        if sha(path)!=item['sha256'] or sha(path)!=baseline[item['path']]:raise ValueError('INPUT_PROVENANCE_MISMATCH')
        data=json.loads(gzip.decompress(path.read_bytes()))
        if set(data)!=set(item['contracts']):raise ValueError('CONTRACT_MEMBERSHIP_MISMATCH')
        look={}
        for m in missing:
            if m['period']==item['period']:look.setdefault((m['contract'],m['publication_id']),[]).append(m)
        h=UnderlyingHistory(allow_observation_proxy=True);seen=0;ingest_errors=Counter();previous=None;previous_contract=None
        boundary={};contract_history=[]
        for contract,seq in sorted(data.items(),key=lambda kv:kv[1][0]['received']):
            contract_history=[]
            boundary[contract]=dict(first_time=seq[0]['time'],previous_contract=previous_contract,
                gap_seconds=seq[0]['time']-previous['time'] if previous else None)
            for r in seq:
                if previous and (r['time']-previous['time']>15 or r['source_epoch']!=previous['source_epoch']):contract_history=[]
                contract_history.append(r);contract_history=[z for z in contract_history if z['time']>=r['time']-135]
                try:h.ingest(observed_proxy(r,source_id=item['sha256']),r['received'])
                except ValueError as exc:
                    h.invalidate(exc);ingest_errors[str(exc)]+=1
                for m in look.get((contract,r['publication_id']),[]):
                    if r['received']!=m['decision_time']:raise ValueError('DECISION_BINDING_MISMATCH')
                    seen+=1;record={k:m[k] for k in ('id','setup_id','period','contract','side','decision_time','feature_error')}
                    record.update(before_available=False,after_proxy_available=False,after_native_available=False,
                        after_features=None,after_error=None,native_error=None,input_path=item['path'],
                        evidence_class='RETAINED_OBSERVATION_PROXY',boundary=boundary[contract],
                        current_contract_history_seconds=r['time']-seq[0]['time'])
                    try:
                        causal_vector(contract_history,r,m['side']);record['before_available']=True
                    except ValueError as exc:record['before_error']=str(exc)
                    if record['before_available']:raise ValueError('FROZEN_UNAVAILABILITY_NOT_REPRODUCED')
                    snap=h.snapshot()
                    try:
                        v=causal_vector(contract_history,r,m['side'],underlying_history=snap,allow_observation_proxy=True)
                        record.update(after_proxy_available=True,after_features=v,
                            used_prefix=[dict(record_id=z.record_id,time=z.time,received=z.received,source_epoch=z.source_epoch)
                                         for z in snap.observations],
                            earliest_time=min(z.time for z in snap.observations))
                    except ValueError as exc:record['after_error']=str(exc)
                    try:causal_vector(contract_history,r,m['side'],underlying_history=snap)
                    except ValueError as exc:record['native_error']=str(exc)
                    else:raise ValueError('OBSERVATION_PROXY_PROMOTED_TO_NATIVE')
                    results.append(record)
                previous=r
            previous_contract=contract
        if seen!=sum(len(v) for v in look.values()):raise ValueError('MISSING_SAVED_LANDMARK')
        input_checks.append(dict(path=item['path'],sha256=item['sha256'],inspected_landmarks=seen,ingest_errors=dict(ingest_errors)))
    if len(results)!=len(missing):raise ValueError('DIAGNOSTIC_DENOMINATOR_MISMATCH')
    known={'KXBTC15M-26SEP280300-00','KXBTC15M-26OCT072345-45','KXBTC15M-26OCT111230-30'}
    cross=[r for r in results if r['after_proxy_available'] and r['earliest_time']<r['boundary']['first_time']]
    report=dict(scope='SAVED_MISSING_120S_LANDMARKS_ONLY_NO_STRATEGY_EVALUATION',total_saved_landmarks=len(marks),
        inspected=len(results),before_available=0,after_proxy_available=sum(r['after_proxy_available'] for r in results),
        after_native_available=0,cross_boundary_recovered=len(cross),cross_boundary_cases=cross,
        remaining_proxy_reasons=dict(Counter(r['after_error'] for r in results if r['after_error'])),
        by_period={p:dict(inspected=sum(r['period']==p for r in results),recovered_proxy=sum(r['period']==p and r['after_proxy_available'] for r in results)) for p in sorted({r['period'] for r in results})},
        recovered_contracts=sorted({r['contract'] for r in results if r['after_proxy_available']}),
        recovered_setups=len({r['setup_id'] for r in results if r['after_proxy_available']}),
        known_review_cases=[r for r in results if r['contract'] in known],input_checks=input_checks,
        landmark_sha256=sha(ledger_path),model_fits=0,calibrations=0,predictions=0,new_labels=0,orders=0,
        limitations=['NORMALIZED_COMPONENT_CLOCKS_ABSENT','NO_NATIVE_EXECUTION_PROOF','ALL_PERIODS_EXPOSED'])
    (OUT/'AVAILABILITY_ROWS.json').write_text(json.dumps(results,sort_keys=True,indent=2)+'\n')
    (OUT/'AVAILABILITY_RESULTS.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('inspected','after_proxy_available','after_native_available','remaining_proxy_reasons','by_period','recovered_contracts')},indent=2))

if __name__=='__main__':run()
