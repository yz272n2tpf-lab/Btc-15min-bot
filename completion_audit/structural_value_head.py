"""Fixed cheap-domain EARLY architecture probes, not another gate sweep.

The generic outcome models were already evaluated. These heads specifically
train on both UP/DOWN 25-50c opportunities. Contract weights, chronological
folds and policy gates are fixed before running the opened challenge.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, logit
from sklearn.ensemble import RandomForestClassifier
from structural_batch import DATA,ROOT,enrich,markets,verify_inputs,signed,score_entries
from joint_diagnosis import load_rows,paths,epoch

NAMES=('existing_control','market_control','cheap_prior_residual','cheap_interactions')
FEATURES=('p_logit','z','basis','m15','m30','m60','receipt_left','spread')
RULES=dict(domain='Both sides 25-50c at 2-10 minutes; first side observation per fixed10/8/6/4/2m anchor',
    fit='Equal contract weights; residual logistic fixed market-logit offset + L2=1; forest128 depth3 leaf10',
    folds='First8->next6, first14->next6, first20->next6 official tuning contracts',
    qualification='Existing EARLY75%/8c edge/<=45c/2-10m unchanged; replace generic predictor and redundant absolute25 dollar gap only',
    selection='Contract-mean chronological Brier including existing/market controls; no challenge reselection',
    challenge='Previously opened 07:00-12:15 development only; no promotion without corrected reserved validation')


def cheap_rows(main):
    out=[]
    for r in main:
        if r['p_existing'] is None or not 2<=r['receipt_left']<=10:continue
        for side in ('UP','DOWN'):
            s=1 if side=='UP' else -1
            p=r['p_existing'] if s==1 else 1-r['p_existing']
            c=signed(r,r['p_existing'],side)
            if not .25<=c['ask']<=.50:continue
            q=r['q'] if s==1 else 1-r['q']
            out.append(dict(c, **{k:s*r[k] for k in ('z','basis','m15','m30','m60')},
                p_logit=float(logit(np.clip(p,.001,.999))),q=q,p_held=p,
                spread=c['ask']-c['bid']))
    return out


def anchors(rows):
    chosen={}
    for r in rows:
        for a in (10,8,6,4,2):
            if a-.5<=r['receipt_left']<=a:chosen.setdefault((r['ticker'],r['side'],a),r)
    return list(chosen.values())


def fit(rows,truth,name):
    if name.endswith('control'):return dict(name=name)
    rows=anchors(rows);count=Counter(r['ticker'] for r in rows)
    x=np.array([[r[f] for f in FEATURES] for r in rows]);w=np.array([1/count[r['ticker']] for r in rows])
    y=np.array([int((r['side']=='UP')==(truth[r['ticker']]['result']=='yes')) for r in rows])
    if name=='cheap_interactions':
        model=RandomForestClassifier(n_estimators=128,max_depth=3,min_samples_leaf=10,max_features=None,random_state=240924,n_jobs=1)
        model.fit(x,y,sample_weight=w);return dict(name=name,model=model)
    center=np.average(x,axis=0,weights=w);scale=np.maximum(np.sqrt(np.average((x-center)**2,axis=0,weights=w)),1e-6)
    x=np.column_stack((np.ones(len(x)),(x-center)/scale));offset=logit([r['q'] for r in rows])
    def loss(beta):
        eta=offset+x@beta
        return np.sum(w*(np.logaddexp(0,eta)-y*eta))+.5*np.sum(beta*beta)
    def grad(beta):return x.T@(w*(expit(offset+x@beta)-y))+beta
    result=minimize(loss,np.zeros(x.shape[1]),jac=grad,method='BFGS')
    if not result.success:raise RuntimeError('Residual fit failed: '+result.message)
    return dict(name=name,center=center.tolist(),scale=scale.tolist(),beta=result.x.tolist())


def predict(model,rows):
    name=model['name']
    if name=='existing_control':return np.array([r['p_held'] for r in rows])
    if name=='market_control':return np.array([r['q'] for r in rows])
    x=np.array([[r[f] for f in FEATURES] for r in rows])
    if name=='cheap_interactions':
        m=model['model'];p=m.predict_proba(x)
        return p[:,list(m.classes_).index(1)] if 1 in m.classes_ else np.zeros(len(rows))
    x=np.column_stack((np.ones(len(x)),(x-model['center'])/model['scale']))
    return expit(logit([r['q'] for r in rows])+x@model['beta'])


def score(model,rows,truth):
    selected=anchors(rows);ps=predict(model,selected);scores=defaultdict(list)
    for r,p in zip(selected,ps):
        y=int((r['side']=='UP')==(truth[r['ticker']]['result']=='yes'))
        scores[r['ticker']].append(float((p-y)**2))
    return {k:float(np.mean(v)) for k,v in scores.items()}


def calls(model,rows):
    seen=set();out=[]
    for r,p in zip(rows,predict(model,rows)):
        if r['ticker'] in seen:continue
        if p>=.75 and r['ask']<=.45 and p-r['ask']>=.08:
            seen.add(r['ticker']);out.append(dict(r,fair=float(p),edge=float(p-r['ask'])))
    return out


def run(output):
    verify_inputs();main=cheap_rows(enrich());truth=markets('tuning');valid=markets('validation')
    tr=[r for r in main if r['ticker'] in truth];vv=[r for r in main if r['ticker'] in valid]
    tickers=sorted(truth,key=lambda k:truth[k]['open_time']);oof={name:{} for name in NAMES};folds=[]
    for n in (8,14,20):
        train=[r for r in tr if r['ticker'] in tickers[:n]];test=[r for r in tr if r['ticker'] in tickers[n:n+6]]
        fold=dict(training_contracts=n,test_contracts=6,scores={})
        for name in NAMES:
            scores=score(fit(train,truth,name),test,truth);oof[name].update(scores);fold['scores'][name]=scores
        folds.append(fold)
    result=dict(rules=RULES,folds=folds,orders=False,signal_only=True,production_promotion=False,
        oof_brier={name:float(np.mean(list(v.values()))) for name,v in oof.items()},models={})
    result['selected']=min(result['oof_brier'],key=result['oof_brier'].get)
    clean=paths(load_rows(DATA/'inputs.jsonl.gz'))
    for name in NAMES:
        model=fit(tr,truth,name);s=score(model,vv,valid)
        result['models'][name]=dict(validation_brier=float(np.mean(list(s.values()))),
            validation_contracts=len(s),training_anchors=len(anchors(tr)),training_contracts=len({r['ticker'] for r in anchors(tr)}),
            parameters={k:v for k,v in model.items() if k!='model'},
            feature_importance=dict(zip(FEATURES,model['model'].feature_importances_.tolist())) if 'model' in model else {},
            tuning=score_entries(calls(model,tr),truth,26,'early',clean),
            validation=score_entries(calls(model,vv),valid,21,'early',clean))
    result['source_code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(selected=result['selected'],oof=result['oof_brier'],models={k:dict(brier=v['validation_brier'],
        tuning_calls=v['tuning']['calls'],validation={f:v['validation'][f] for f in ('calls','wins','entry','minutes_left')}) for k,v in result['models'].items()}),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
