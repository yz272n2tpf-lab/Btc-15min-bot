"""Expanded exact frozen-model and FINAL predicate replay, no gate mutation."""
from collections import Counter
from pathlib import Path
import json, math
import numpy as np
import pandas as pd
from completion_audit.frozen_model_artifact import load_verified
from btc15_v2_product.early_entry import ARTIFACT, WEIGHTS
from audit.existing_evidence_20261011.replay_candidates import final_predicates_from_recorded_inputs
from audit.existing_evidence_20261011.evaluate import epoch, policy_table, gate_diagnostics

def run(w):
    repo=w/'repo';out=repo/'audit/three_ladder_readiness_20261011';frames={};reject=Counter()
    files=sorted((w/'readiness-evidence').glob('features-*.jsonl'))
    for path in files:
        for line in path.open():
            f=json.loads(line);key=(f['ticker'],epoch(f['decision_utc']))
            if f['artifact_sha256']!=ARTIFACT or f['weights_sha256']!=WEIGHTS:reject['model_identity']+=1;continue
            assert epoch(f['btc_source_utc'])<=epoch(f['btc_observed_utc'])<=key[1]
            if key in frames:assert frames[key]==f
            frames[key]=f
    model=load_verified(repo/'completion_audit/model_artifact/frozen_fair_candidate.joblib',expected_artifact_sha256=ARTIFACT,expected_weights_sha256=WEIGHTS)
    keys=sorted(frames);X=pd.DataFrame([frames[k]['features'] for k in keys])[model['features']]
    flip=np.clip(model['sigmoid'].predict_proba(model['forest'].predict_proba(X)[:,1].reshape(-1,1))[:,1],.001,.999)
    predictions={k:float(1-p if frames[k]['features']['current_side']==1 else p) for k,p in zip(keys,flip)}
    observations=[]
    for path in [w/'recovered-common/pr36/records.jsonl',w/'readiness-evidence/final-expanded/records.jsonl']:
        if not path.exists():continue
        for line in path.open():
            o=json.loads(line)
            for source in o.get('sources',[]):
                if source.get('service')=='main' and 'state' in source:observations.append((source['state'],source.get('response_received_utc')))
    rows={};conflicts=set()
    for state,receipt in observations:
        try:key=(state['contract'],epoch(state['source_timestamp_utc']));f=frames.get(key)
        except (KeyError,TypeError,ValueError,AttributeError):continue
        if not f:continue
        if not receipt:reject['receipt_absent']+=1;continue
        received=epoch(receipt)
        if not all(state['health'].get(k)is True for k in ('source_fresh','brti_fresh','paired_quotes','market_open')):reject['unhealthy']+=1;continue
        if not key[1]<=received<=key[1]+10:reject['receipt_clock_or_age']+=1;continue
        m=state['market'];g=state['final'];up=predictions[key];p=max(up,1-up);side='UP' if up>=.5 else 'DOWN'
        if m.get('btc_price')!=f['btc_price'] or m.get('target')!=f['target']:reject['feature_binding']+=1;continue
        if g.get('side')!=side or abs(g.get('confidence',-1)-p)>1e-10:reject['frozen_model_probability_mismatch']+=1;continue
        try:gates,left=final_predicates_from_recorded_inputs(state,f,received)
        except (KeyError,ValueError,TypeError):reject['incomplete_numeric_frame']+=1;continue
        if gates is None:reject['capture_interval_ambiguous']+=1;continue
        row=dict(contract=key[0],time=key[1],left=left,side=side,p=p,gap=f['btc_price']-f['target'],vol5=f['features']['vol5'],gates=gates)
        if key in rows and rows[key]!=row:conflicts.add(key)
        rows.setdefault(key,row)
    labels={r['contract']:r['official_side'] for r in json.loads((repo/'audit/existing_evidence_20261011/final_forward_state.json').read_text())['live']['settled_records']}
    rows=[dict(r,correct=r['side']==labels[r['contract']] if r['contract'] in labels else None) for k,r in rows.items() if k not in conflicts]
    other=lambda r:all(v for k,v in r['gates'].items() if k!='gap_ok')
    table=policy_table(rows,other)
    # Volatility bands are descriptive development quartiles, not tuned gates.
    cuts=np.quantile([r['vol5'] for r in rows],[.25,.5,.75]).tolist() if rows else []
    strata={str(i):policy_table([r for r in rows if int(np.searchsorted(cuts,r['vol5'],side='right'))==i],other) for i in range(4)} if rows else {}
    result=dict(role='ACTUAL_FROZEN_MODEL_AND_CANDIDATE_PREDICATE_REPLAY_NOT_NATIVE_AUTHORITY',feature_records=len(frames),feature_contracts=len({k[0] for k in frames}),
        usable_records=len(rows),usable_contracts=len({r['contract'] for r in rows}),rejections=dict(reject),conflicts=len(conflicts),
        first=min(r['time'] for r in rows) if rows else None,last=max(r['time'] for r in rows) if rows else None,
        table=table,diagnostics=gate_diagnostics(rows,other),volatility_quartiles=cuts,volatility_strata=strata,
        volatility_warning='A contract can appear in different strata; do not add stratum sample counts.',
        settlement_aware_scored=False,settlement_blocker='No reviewed decision-time settlement-path probability model; final-window averages alone do not provide future-second uncertainty.',
        native_authority_missing=['original quote-consumption receipt','native BRTI delivery identity'],
        recommendation='KEEP_75_50_AND_90_PENDING_INDEPENDENT_EVIDENCE',signal_only=True,orders=False)
    (out/'final_expanded_results.json').write_text(json.dumps(result,indent=2));(out/'final_bound_rows.json').write_text(json.dumps(rows,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ('table','volatility_strata')},indent=2));print(json.dumps({k:{x:y for x,y in v.items() if x not in ('records','by_side')} for k,v in table.items()},indent=2))

if __name__=='__main__':
    import sys
    run(Path(sys.argv[1]))
