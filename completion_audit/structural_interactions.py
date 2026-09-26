"""Fixed nonlinear scalp interactions after native label-alignment diagnosis.

No hyperparameter search; all candidates frozen in code before challenge scoring.
Contract-blocked tuning folds precede the already-opened development challenge.
"""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier

from structural_batch import DATA,ROOT,SCALP_FEATURES,verify_inputs,passage,markets,score_entries
from structural_path_alignment import native_paths
from joint_diagnosis import load_rows,epoch
from joint_v81 import rows as vrows

NAMES=('constant_control','shallow_tree','shallow_forest')


def labeled(vr,tape):
    chosen={}
    for r in vr:
        if (not r['features_ready'] or not r['brti_fresh'] or r.get('btc_age') is None
            or not 0<=r['btc_age']<=10 or not 2<=r['receipt_left']<=10
            or any(r.get(k) is None for k in SCALP_FEATURES)):continue
        chosen.setdefault((r['ticker'],r['side'],int(r['t']//60)),r)
    out=[]
    for r in chosen.values():
        p=passage(r,tape)
        if p['result'] in ('target','stop'):out.append(dict(r,y=int(p['result']=='target')))
    return out


def fit(rows,name):
    count=Counter(r['ticker'] for r in rows);w=np.array([1/count[r['ticker']] for r in rows])
    y=np.array([r['y'] for r in rows]);x=np.array([[r[k] for k in SCALP_FEATURES] for r in rows])
    if name=='constant_control':return float(np.average(y,weights=w))
    if name=='shallow_tree':model=DecisionTreeClassifier(max_depth=2,min_samples_leaf=20,random_state=2409)
    elif name=='shallow_forest':model=RandomForestClassifier(n_estimators=128,max_depth=3,min_samples_leaf=10,max_features=None,random_state=2409,n_jobs=1)
    else:raise ValueError(name)
    model.fit(x,y,sample_weight=w);return model


def probabilities(model,rows):
    if isinstance(model,float):return np.repeat(model,len(rows))
    ps=model.predict_proba(np.array([[r[k] for k in SCALP_FEATURES] for r in rows]))
    return ps[:,list(model.classes_).index(1)] if 1 in model.classes_ else np.zeros(len(rows))


def calls(vr,model):
    rs=[r for r in vr if r['features_ready'] and r['brti_fresh'] and r.get('btc_age') is not None
        and 0<=r['btc_age']<=10 and 2<=r['receipt_left']<=10 and all(r.get(k) is not None for k in SCALP_FEATURES)]
    from collections import defaultdict
    queues=defaultdict(list);used=set();out=[]
    for r,p in zip(rs,probabilities(model,rs)):
        key=r['ticker'],r['side'];t=r['source_t']
        if p<.70:queues[key].clear();continue
        queues[key]=[x for x in queues[key] if t-x<=4];queues[key].append(t)
        if len(queues[key])>=2 and key not in used:used.add(key);out.append(dict(r,passage_probability=float(p)))
    return out


def score(rows,model):
    ps=probabilities(model,rows);by={}
    for r,p in zip(rows,ps):by.setdefault(r['ticker'],[]).append(float((p-r['y'])**2))
    return {k:float(np.mean(v)) for k,v in by.items()}


def run(output):
    verify_inputs();tape,_=native_paths(load_rows(DATA/'v81.jsonl.gz'));truth=markets('tuning')
    vr,_,_=vrows(DATA/'v81.jsonl.gz',epoch('2026-09-24T00:15Z'),epoch('2026-09-24T06:45Z'))
    labels=labeled(vr,tape);tickers=sorted(truth,key=lambda k:truth[k]['open_time'])
    result=dict(orders=False,signal_only=True,no_hyperparameter_search=True,folds=[],models={},challenge_previously_opened=True,
                selection='minimum contract-mean OOF Brier; existing scalar 70% passage gate fixed',production_promotion=False)
    totals={name:{} for name in NAMES}
    for n in (8,14,20):
        train=[r for r in labels if r['ticker'] in tickers[:n]];test=[r for r in labels if r['ticker'] in tickers[n:n+6]]
        fold=dict(train_contracts=len({r['ticker'] for r in train}),test_contracts=len({r['ticker'] for r in test}),scores={})
        for name in NAMES:
            model=fit(train,name);s=score(test,model);totals[name].update(s);fold['scores'][name]=s
        result['folds'].append(fold)
    result['oof_brier']={name:float(np.mean(list(s.values()))) for name,s in totals.items()}
    result['selected']=min(result['oof_brier'],key=result['oof_brier'].get)
    # All three fixed probes remain reported, including failures; no validation reselection.
    valid=markets('validation');vv,_,_=vrows(DATA/'v81.jsonl.gz',epoch('2026-09-24T07:00Z'),epoch('2026-09-24T12:15Z'))
    vl=labeled(vv,tape)
    for name in NAMES:
        model=fit(labels,name);s=score(vl,model)
        result['models'][name]=dict(validation_contracts=len(s),validation_brier=float(np.mean(list(s.values()))),
            feature_importance=dict(zip(SCALP_FEATURES,model.feature_importances_.tolist())) if not isinstance(model,float) else {},
            tuning=score_entries(calls(vr,model),truth,26,'v81',tape),
            validation=score_entries(calls(vv,model),valid,21,'v81',tape))
    result['code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(selected=result['selected'],oof=result['oof_brier'],models={n:dict(validation_brier=m['validation_brier'],
        tuning={k:m['tuning'][k] for k in ('calls','contracts','first_passage')},validation={k:m['validation'][k] for k in ('calls','contracts','entry','minutes_left','first_passage')}) for n,m in result['models'].items()}),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
