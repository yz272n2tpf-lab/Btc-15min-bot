"""Six-feature continuation probability. Offline, exposed quote evidence only.

This target is independent of EXIT. No probability returned here grants authority.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from .assessment import SAFETY, Rules, validate_row, price_group
from .resale import digest

FEATURES = ['ask_cents', 'runway_minutes', 'joint_impulse30', 'joint_efficiency30',
            'joint_movement120', 'joint_structure120']
EVIDENCE = 'QUOTE_ONLY_STRESS_EXPOSED'
OBSERVED_DOMAINS = ('OBSERVATION_NO_NATIVE_RECEIPT','COMMON_OBSERVED_NO_NATIVE_RECEIPT')
TARGET = 'DURABLE_10C_60S_DELAYED_OPPORTUNITY_BEFORE_ADVERSE_10C'
METHOD = dict(id='CONTINUATION_LOGISTIC_V1', features=FEATURES, C=1,
    calibration='INTERCEPT_ONLY', cadence=10, selection_probability=.75,
    selection_lower=.50, bootstrap=200, seed=1210, block_contracts=4,
    min_bootstrap=160, min_cell_contracts=12, train='sep26_27_development',
    calibration_period='sep28_29_diagnostic', target=TARGET,
    evidence_class=EVIDENCE, independent_validation=False)


def code_identity():
    root=Path(__file__).resolve().parent
    return {n:hashlib.sha256((root/n).read_bytes()).hexdigest()
            for n in ('continuation.py','durability.py','continuation_engine.py','assessment.py','engine.py')}


def causal_vector(history, r, side):
    if side not in ('UP','DOWN') or validate_row(r): raise ValueError('INVALID_DECISION')
    if price_group(r[side.lower()+'_ask'])!='PRIMARY': raise ValueError('PRIMARY_PRICE_REQUIRED')
    if not history or history[-1]!=r: raise ValueError('DECISION_ENDPOINT_REQUIRED')
    # Reject supplied future data; never silently truncate a contaminated prefix.
    if any(z['received']>r['received'] or z['time']>r['time'] for z in history):
        raise ValueError('FUTURE_FEATURE_INPUT')
    end=r['time']; close=end+r['left']; sign=1 if side=='UP' else -1
    def window(seconds):
        old=next((z for z in reversed(history) if z['time']<=end-seconds),None)
        if old is None or end-seconds-old['time']>15: raise ValueError('CAUSAL_120S_HISTORY_UNAVAILABLE')
        seq=[z for z in history if z['time']>=old['time']]
        if any(validate_row(z) or z['contract']!=r['contract'] or z['target']!=r['target'] or
               abs(z['time']+z['left']-close)>1 or z['source_epoch']!=r['source_epoch'] for z in seq):
            raise ValueError('FEATURE_IDENTITY_OR_SOURCE_INVALID')
        if any(not 0<b['time']-a['time']<=15 or b['received']<a['received']
               for a,b in zip(seq,seq[1:])): raise ValueError('FEATURE_CONTINUITY_INVALID')
        scale=max(max(z['btc'] for z in seq)-min(z['btc'] for z in seq),r['target']*.00001)
        return seq,scale
    short,r30=window(30);long,r120=window(120)
    impulse=min(sign*(r[k]-short[0][k]) for k in ('btc','brti'))/r30
    eff=min(sign*(r[k]-short[0][k])/max(sum(abs(b[k]-a[k]) for a,b in zip(short,short[1:])),1e-6)
            for k in ('btc','brti'))
    older=[z for z in long if z['time']<=end-60]
    newer=[z for z in long if z['time']>end-60]
    if not older or not newer: raise ValueError('STRUCTURE_HALVES_UNAVAILABLE')
    structure=min(min(sign*z[k] for z in newer)-min(sign*z[k] for z in older)
                  for k in ('btc','brti'))/r120
    v=[100*r[side.lower()+'_ask'],(close-r['received'])/60,impulse,eff,
       min(sign*(r[k]-long[0][k]) for k in ('btc','brti'))/r120,structure]
    if not all(math.isfinite(x) for x in v):raise ValueError('NONFINITE_FEATURE')
    return v


def sigmoid(x):
    return np.exp(-np.logaddexp(0,-np.asarray(x,dtype=float)))


def solve(x,y,w):
    """Convex weighted logistic + L2(C=1); unpenalized intercept."""
    if len(set(y[w>0]))!=2:raise ValueError('BOTH_CLASSES_REQUIRED')
    z=np.column_stack([np.ones(len(x)),x]);b=np.zeros(z.shape[1]);pen=np.eye(len(b));pen[0,0]=0
    for _ in range(100):
        p=sigmoid(z@b);g=z.T@(w*(p-y))+pen@b
        h=z.T@((w*p*(1-p))[:,None]*z)+pen
        step=np.linalg.solve(h,g)
        old=float(np.sum(w*(np.logaddexp(0,z@b)-y*(z@b)))+.5*b@pen@b)
        rate=1.
        while rate>1e-8:
            trial=b-rate*step;t=z@trial
            loss=float(np.sum(w*(np.logaddexp(0,t)-y*t))+.5*trial@pen@trial)
            if loss<=old+1e-12:break
            rate*=.5
        b=trial
        if np.max(abs(rate*step))<1e-9:return b
    raise ValueError('LOGISTIC_NOT_CONVERGED')


def calibrate(logits,y,w):
    if len(set(y[w>0]))!=2:raise ValueError('CALIBRATION_BOTH_CLASSES_REQUIRED')
    lo,hi=-50.,50.
    for _ in range(100):
        mid=(lo+hi)/2
        if np.sum(w*(sigmoid(logits+mid)-y))>0:hi=mid
        else:lo=mid
    return (lo+hi)/2


def _data(rows):
    rr=[r for r in rows if r.get('y') in (0,1) and r.get('features') is not None]
    counts=Counter(r['contract'] for r in rr)
    return rr,np.array([r['features'] for r in rr]),np.array([r['y'] for r in rr],dtype=float),np.array([1/counts[r['contract']] for r in rr])


def _fit(x,y,w,cx,cy,cw,calibration_supported=True):
    mean=np.average(x,axis=0,weights=w);scale=np.sqrt(np.average((x-mean)**2,axis=0,weights=w));scale[scale<1e-8]=1
    b=solve((x-mean)/scale,y,w)
    shift=calibrate(np.column_stack([np.ones(len(cx)),(cx-mean)/scale])@b,cy,cw) if calibration_supported else 0.
    return dict(center=mean.tolist(),scale=scale.tolist(),coefficients=b.tolist(),calibration_intercept=float(shift))


def _block_weights(rows,base,rng):
    order=sorted({r['contract'] for r in rows},key=lambda c:min(r['decision_time'] for r in rows if r['contract']==c))
    blocks=[order[i:i+4] for i in range(0,len(order),4)]
    chosen=Counter(c for i in rng.integers(0,len(blocks),len(blocks)) for c in blocks[i])
    return base*np.array([chosen[r['contract']] for r in rows])


def fit(training,calibration,provenance):
    for rows,period in ((training,METHOD['train']),(calibration,METHOD['calibration_period'])):
        if any(r['period']!=period or r['evidence_class']!=EVIDENCE for r in rows):raise ValueError('PARTITION_OR_EVIDENCE_MISMATCH')
    tr,x,y,w=_data(training);cr,cx,cy,cw=_data(calibration)
    if not tr or not cr:raise ValueError('LABELED_FIT_AND_CALIBRATION_REQUIRED')
    if {r['contract'] for r in training}&{r['contract'] for r in calibration}:raise ValueError('CONTRACT_OVERLAP')
    if max(r['label_available_at'] for r in tr)>=min(r['decision_time'] for r in calibration):raise ValueError('CHRONOLOGY_CONFLICT')
    calibration_supported=len(set(cy))==2
    model=_fit(x,y,w,cx,cy,cw,calibration_supported);rng=np.random.default_rng(METHOD['seed']);boots=[];failed=Counter()
    for _ in range(METHOD['bootstrap']):
        try:boots.append(_fit(x,y,_block_weights(tr,w,rng),cx,cy,_block_weights(cr,cw,rng),calibration_supported))
        except (ValueError,np.linalg.LinAlgError) as exc:failed[str(exc)]+=1
    cells={}
    for cell in sorted({r['side']+'_'+r['context'] for r in tr}):
        rr=[r for r in tr if r['side']+'_'+r['context']==cell];xx=np.array([r['features'] for r in rr]);n=len({r['contract'] for r in rr})
        cells[cell]=dict(contracts=n,min=xx.min(axis=0).tolist(),max=xx.max(axis=0).tolist(),supported=n>=12,
                        class_contracts={str(k):len({r['contract'] for r in rr if r['y']==k}) for k in (0,1)})
    body=dict(schema=1,method=METHOD,code_identity=code_identity(),model=model,bootstrap=boots,
        calibration_status='FITTED_EXPLORATORY' if calibration_supported else 'UNAVAILABLE_BOTH_CLASSES_REQUIRED',
        calibration_intercept_applied=calibration_supported,
        availability_semantics='HYPOTHETICAL_COMPLETED_CALIBRATION_PARTITION_FOR_EXPOSED_OFFLINE_RESEARCH',
        bootstrap_failed=dict(failed),support=cells,provenance=provenance,evidence_class=EVIDENCE,
        available_after=max(r['label_available_at'] for r in cr),training_prevalence=float(np.average(y,weights=w)),
        train_contracts=sorted({r['contract'] for r in training}),calibration_contracts=sorted({r['contract'] for r in calibration}),
        counts=dict(training_labels=len(tr),calibration_labels=len(cr)),
        limitations=['ALL_PERIODS_EXPOSED','INFORMATIVE_CENSORING','NORMALIZED_NOT_ORIGINAL_RECEIPTS',
                     'NO_DEPTH_OR_APPLICABLE_FEES','OVERLAPPING_LANDMARKS','MARGINAL_SUPPORT_ONLY'])
    return dict(body=body,artifact_sha256=digest(body))


def predict(model,v):
    z=np.r_[1,(np.array(v)-model['center'])/model['scale']]
    return float(sigmoid(z@model['coefficients']+model['calibration_intercept']))


class ContinuationEstimator:
    def __init__(self,artifact,*,expected_sha256):
        b=artifact['body']
        if artifact.get('artifact_sha256')!=expected_sha256 or digest(b)!=expected_sha256:raise ValueError('ARTIFACT_IDENTITY_MISMATCH')
        if b.get('method')!=METHOD or b.get('schema')!=1 or b.get('code_identity')!=code_identity():raise ValueError('METHOD_OR_CODE_MISMATCH')
        if b.get('evidence_class')!=EVIDENCE:raise ValueError('EVIDENCE_CLASS_MISMATCH')
        calibrated=b.get('calibration_status')=='FITTED_EXPLORATORY'
        if b.get('calibration_status') not in ('FITTED_EXPLORATORY','UNAVAILABLE_BOTH_CLASSES_REQUIRED') or b.get('calibration_intercept_applied')!=calibrated:raise ValueError('CALIBRATION_IDENTITY')
        if not math.isfinite(b['available_after']):raise ValueError('INVALID_AVAILABILITY')
        if len(b['bootstrap'])>200:raise ValueError('BOOTSTRAP_SHAPE')
        for m in [b['model']]+b['bootstrap']:
            if len(m['center'])!=6 or len(m['scale'])!=6 or len(m['coefficients'])!=7:raise ValueError('MODEL_SHAPE')
            if min(m['scale'])<=0 or not all(math.isfinite(v) for v in m['center']+m['scale']+m['coefficients']+[m['calibration_intercept']]):raise ValueError('MODEL_NUMERICS')
            if not calibrated and m['calibration_intercept']!=0:raise ValueError('UNSUPPORTED_CALIBRATION_SHIFT')
        for c in b['support'].values():
            if len(c['min'])!=6 or len(c['max'])!=6 or any(not math.isfinite(a+b) or a>b for a,b in zip(c['min'],c['max'])):raise ValueError('INVALID_SUPPORT')
            if c['supported'] and c['contracts']<12:raise ValueError('INSUFFICIENT_SUPPORT')
        self.body=deepcopy(b);self.identity=expected_sha256

    @classmethod
    def load(cls,path,*,expected_sha256):return cls(json.loads(Path(path).read_text()),expected_sha256=expected_sha256)

    def infer(self,r,side,history,context):
        out=dict(**SAFETY,target=TARGET,status='UNESTIMATED',ready=False,probability=None,lower95=None,upper95=None,
            diagnostic_selected=False,artifact_sha256=self.identity,validation='EXPLORATORY_ONLY',
            evidence_class=EVIDENCE,decision_time=r['received'],side=side,context=context,
            reasons=['NO_INDEPENDENT_VALIDATION','NO_NATIVE_EXECUTION_AUTHORITY'])
        try:
            if r.get('evidence_class') not in OBSERVED_DOMAINS:raise ValueError('ARTIFACT_EVIDENCE_DOMAIN_UNSUPPORTED')
            if r['received']<=self.body['available_after']:raise ValueError('ARTIFACT_NOT_AVAILABLE_AT_DECISION')
            v=causal_vector(history,r,side);cell=self.body['support'].get(side+'_'+context)
            if not cell or not cell['supported']:raise ValueError('DIRECTION_CONTEXT_UNSUPPORTED')
            if any(x<a-1e-8 or x>b+1e-8 for x,a,b in zip(v,cell['min'],cell['max'])):raise ValueError('FEATURE_OUT_OF_SUPPORT')
            p=predict(self.body['model'],v);lo=hi=None
            if len(self.body['bootstrap'])>=160:lo,hi=np.quantile([predict(m,v) for m in self.body['bootstrap']],[.025,.975]).tolist()
            else:out['reasons'].append('BOOTSTRAP_INSUFFICIENT')
            calibrated=self.body['calibration_intercept_applied']
            if not calibrated:out['reasons'].append('CALIBRATION_BOTH_CLASSES_REQUIRED')
            out.update(status='EXPLORATORY_CONTINUATION_ESTIMATE' if calibrated else 'UNCALIBRATED_EXPLORATORY_ESTIMATE',
                       calibration_status=self.body['calibration_status'],features=v,probability=p,lower95=lo,upper95=hi,
                       diagnostic_selected=bool(calibrated and p>=.75 and lo is not None and lo>.5))
        except (ValueError,TypeError,KeyError) as exc:out['reasons'].append(str(exc))
        return out
