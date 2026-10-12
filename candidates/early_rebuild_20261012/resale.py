"""Small, frozen exploratory conditional-resale estimator. Never grants BUY authority.

Labels are complete observed delayed-entry/condition-exit quote scenarios. The
fee stress is an assumption; this is NOT an estimate of executable strategy P&L.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from .assessment import SAFETY, TARGET, Rules, features, validate_row, price_group
from candidates.early_value_20261011.engine import fee

FEATURES = ['ask_cents', 'runway_minutes', 'joint_impulse_over_range', 'joint_efficiency']
METHOD = dict(id='CONDITIONAL_QUOTE_RIDGE_V1', features=FEATURES, ridge=1.0,
    min_cell_contracts=12, bootstrap_contracts=200, bootstrap_seed=1210,
    train_period='sep26_27_development', evaluation='ALL_LATER_WHOLE_CONTRACTS_EXPOSED',
    cells='SIDE_AND_DECISION_CONTEXT', weighting='ONE_TOTAL_WEIGHT_PER_CONTRACT_IN_CELL',
    selection='FIRST_PRIMARY_OBSERVATIONAL_QUALIFICATION_PER_RETAINED_SETUP',
    diagnostic_selection='SUPPORTED_AND_MEAN_GT_ZERO_AND_BOOTSTRAP_MEAN_LOWER_GT_ZERO',
    entry_delay_seconds=10, exit_delay_seconds=10, observation_tolerance_seconds=10,
    cost='ONE_CONTRACT_CEIL_CENT_0.07_P_1_MINUS_P_EACH_LEG_STRESS',
    reserve='MAX_2C_QUALIFICATION_SPREAD_ENTRY_SPREAD_EXIT_SPREAD',
    management='UNCHANGED_COREENGINE_MANAGE', target=TARGET,
    estimand='NET_QUOTE_CENTS_CONDITIONAL_ON_VALID_OBSERVED_ENTRY_AND_COMPLETE_PATH',
    noncausal_exclusions=['settlement_probability','fair_value','future_best_bid','settlement_outcome'],
    support='PRIMARY_PRICE_ONLY; TRAIN_CELL_FEATURE_MIN_MAX; NO_EXTRAPOLATION',
    independent_validation=False, native_execution_verified=False)


def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def vector(r, side, x):
    if side not in ('UP','DOWN') or not x or price_group(r[side.lower()+'_ask'])!='PRIMARY':
        raise ValueError('PRICE_OR_CONTEXT_UNSUPPORTED')
    values=[100*r[side.lower()+'_ask'], (r['time']+r['left']-r['received'])/60,
            min(x['move_short'],x['brti_short'])/max(x['short_range'],1e-6),
            min(x['short_efficiency'],x['brti_efficiency'])]
    if not all(type(v) in (int,float) and math.isfinite(v) for v in values):
        raise ValueError('INVALID_CAUSAL_FEATURES')
    return values


def causal_features(seq, at, side):
    """Replay only the small causal input prefix, not BUY or management selection."""
    hist=[];previous=None;q=Rules()
    for r in seq:
        if r['received']>at: break
        if validate_row(r): hist=[];previous=r;continue
        if previous and (r['time']-previous['time']>q.max_gap or r['source_epoch']!=previous['source_epoch']):hist=[]
        hist.append(r);hist=[z for z in hist if z['time']>=r['time']-q.lookback-q.max_gap]
        previous=r
    if not hist or hist[-1]['received']!=at:raise ValueError('DECISION_ROW_UNAVAILABLE')
    r=hist[-1]
    if any(z['time']>r['time'] or z['received']>at for z in hist):raise ValueError('FUTURE_FEATURE_INPUT')
    return r,features(hist,r,side,q)


def build_label(rec, seq):
    """Validate retained labels against exact rows; never search for a better sale.

    A canceled or censored record remains in the ledger with no numerical label.
    Native receipt/size/fee applicability is explicitly NOT asserted by this path.
    """
    s=rec['setup'];qual=rec['observational_qualification'];side=s['side']
    out=dict(setup_id=s['id'],contract=s['contract'],side=side,status=rec['status'],
        decision_time=None,cell=None,features=None,net_cents=None,label_error=None,
        execution_verified=False,evidence_class='EXPOSED_OBSERVATIONAL_QUOTE_SCENARIO',
        cancellation_reasons=rec['cancellation_reasons'],complete_case_only=True)
    if not qual:return out
    try:
        r,x=causal_features(seq,qual['time'],side)
        if not x or x['context']!=qual['context'] or r['time']!=qual['source_time'] or r[side.lower()+'_ask']!=qual['ask']:
            raise ValueError('DECISION_BINDING_CONFLICT')
        out.update(decision_time=qual['time'],cell=side+'_'+x['context'],features=vector(r,side,x))
        if not rec['hypothetical_after_cost']:return out
        h=rec['hypothetical_after_cost'];d=rec['delayed_recheck'];m=rec['management'];t=m['terminal']
        if rec['status']!='COMPLETE_HYPOTHETICAL_QUOTE_SCENARIO' or rec['cancellation_reasons'] or not t or not t['complete']:
            raise ValueError('INCOMPLETE_OR_CANCELED_LABEL')
        entry=next((z for z in seq if z['time']>=qual['time']+10),None)
        if not entry or entry['received']!=d['available_at'] or entry['received']>qual['time']+20:
            raise ValueError('FIRST_DELAYED_ENTRY_BINDING')
        if not .25<=entry[side.lower()+'_ask']<=.55 or entry[side.lower()+'_ask']!=h['entry_ask']:
            raise ValueError('ENTRY_PRICE_BINDING')
        terminal=next((z for z in seq if z['publication_id']==t['publication_id']),None)
        if not terminal or terminal['received']!=t['available'] or terminal['time']!=t['time']:
            raise ValueError('CONDITION_EXIT_BINDING')
        sold=next((z for z in seq if z['time']>=t['available']+10 and z['received']<=t['available']+20
                   and not validate_row(z) and z['received']<z['time']+z['left']),None)
        if not sold or sold['received']!=h['exit_observed_at'] or sold[side.lower()+'_bid']!=h['exit_bid']:
            raise ValueError('FIRST_DELAYED_EXIT_BID_BINDING')
        origin=m['origin']
        if (origin['contract']!=s['contract'] or origin['side']!=side or origin['setup_id']!=s['id'] or
            origin['entry_time']!=entry['received'] or origin['observed_ask']!=h['entry_ask']):
            raise ValueError('IMMUTABLE_ORIGIN_BINDING')
        path=[z for z in seq if qual['time']<=z['received']<=sold['received']]
        close=r['time']+r['left']
        if (any(validate_row(z) or z['contract']!=s['contract'] or z['target']!=r['target'] or
                abs(z['time']+z['left']-close)>1 for z in path) or
            any(not 0<b['time']-a['time']<=15 or b['received']<a['received'] or
                b['source_epoch']!=a['source_epoch'] for a,b in zip(path,path[1:]))):
            raise ValueError('OBSERVATIONAL_PATH_NOT_CONTINUOUS')
        reserve=max(.02,qual['ask']-qual['bid'],h['entry_ask']-entry[side.lower()+'_bid'],sold[side.lower()+'_ask']-h['exit_bid'])
        net=100*(h['exit_bid']-h['entry_ask']-fee(h['entry_ask'])-fee(h['exit_bid'])-reserve)
        if any(abs(a-b)>1e-8 for a,b in [(reserve,h['reserve']),(net,h['net_cents']),
                   (fee(h['entry_ask']),h['entry_fee_stress']),(fee(h['exit_bid']),h['exit_fee_stress'])]):
            raise ValueError('COST_OR_NET_LABEL_CONFLICT')
        out.update(net_cents=net,label_available_at=sold['received'],entry_time=entry['received'],
                   exit_time=sold['received'],entry_ask=h['entry_ask'],exit_bid=h['exit_bid'],
                   fees_and_reserve=dict(entry_stress=fee(h['entry_ask']),exit_stress=fee(h['exit_bid']),reserve=reserve))
    except (ValueError,KeyError,TypeError,StopIteration) as exc:
        out.update(net_cents=None,label_error=str(exc))
    return out


def _solve(x,y,w):
    z=np.column_stack([np.ones(len(x)),x]);penalty=np.eye(z.shape[1])*METHOD['ridge'];penalty[0,0]=0
    return np.linalg.solve(z.T@(w[:,None]*z)+penalty,z.T@(w*y))


def fit(ledger, provenance, management_sha256):
    """Fit once on the declared earlier contracts. Does not receive evaluation labels."""
    if any(r.get('period')!=METHOD['train_period'] for r in ledger):raise ValueError('TRAIN_PERIOD_CONFLICT')
    if any(r.get('evidence_class')!='EXPOSED_OBSERVATIONAL_QUOTE_SCENARIO' for r in ledger):
        raise ValueError('TRAINING_EVIDENCE_CLASS_CONFLICT')
    eligible=[r for r in ledger if r['net_cents'] is not None and not r['label_error']]
    cells={}
    for cell in sorted({r['cell'] for r in eligible}):
        rr=[r for r in eligible if r['cell']==cell];contracts=sorted({r['contract'] for r in rr})
        if len(contracts)<METHOD['min_cell_contracts']:continue
        x=np.array([r['features'] for r in rr]);y=np.array([r['net_cents'] for r in rr])
        counts=Counter(r['contract'] for r in rr);w=np.array([1/counts[r['contract']] for r in rr])
        center=np.average(x,axis=0,weights=w);scale=np.sqrt(np.average((x-center)**2,axis=0,weights=w));scale[scale<1e-8]=1
        z=(x-center)/scale;b=_solve(z,y,w)
        rng=np.random.default_rng(METHOD['bootstrap_seed']);boots=[]
        for _ in range(METHOD['bootstrap_contracts']):
            chosen=Counter(rng.choice(contracts,len(contracts),replace=True))
            bw=np.array([chosen[r['contract']]/counts[r['contract']] for r in rr])
            boots.append(_solve(z,y,bw).tolist())
        residual=y-(np.column_stack([np.ones(len(z)),z])@b)
        order=np.argsort(residual);cum=np.cumsum(w[order])/sum(w)
        q10=float(residual[order[np.searchsorted(cum,.1)]])
        cells[cell]=dict(n=len(rr),contracts=len(contracts),center=center.tolist(),scale=scale.tolist(),
            min=x.min(axis=0).tolist(),max=x.max(axis=0).tolist(),coefficients=b.tolist(),
            bootstrap_coefficients=boots,residual_q10=q10,training_contracts=contracts)
    if not cells:raise ValueError('NO_CELL_WITH_12_COMPLETE_TRAINING_CONTRACTS')
    body=dict(schema=1,method=METHOD,management_sha256=management_sha256,cells=cells,
        provenance=provenance,trained_through=max(r['label_available_at'] for r in eligible),
        evidence_class='EXPOSED_OBSERVATIONAL_QUOTE_SCENARIO',
        train_status_counts=dict(Counter(r['status'] for r in ledger)),
        limitations=['INFORMATIVE_COMPLETE_CASE_CENSORING','OVERLAPPING_SIMULATIONS',
                     'NO_NATIVE_EXECUTION_PROOF','FEES_ARE_STRESS_ASSUMPTIONS','NO_UNTOUCHED_HOLDOUT'])
    return dict(body=body,artifact_sha256=digest(body))


class Estimator:
    def __init__(self, artifact, *, expected_sha256, management_sha256):
        body=artifact['body']
        if digest(body)!=expected_sha256 or artifact.get('artifact_sha256')!=expected_sha256:
            raise ValueError('ARTIFACT_IDENTITY_MISMATCH')
        if body.get('schema')!=1 or body.get('method')!=METHOD or body.get('management_sha256')!=management_sha256:
            raise ValueError('METHOD_OR_MANAGEMENT_IDENTITY_MISMATCH')
        if body.get('evidence_class')!='EXPOSED_OBSERVATIONAL_QUOTE_SCENARIO':raise ValueError('ARTIFACT_EVIDENCE_CLASS')
        if not isinstance(body.get('trained_through'),(int,float)) or not math.isfinite(body['trained_through']):
            raise ValueError('ARTIFACT_AVAILABILITY_INVALID')
        actual=hashlib.sha256((Path(__file__).resolve().parents[2]/'candidates/early_value_20261011/engine.py').read_bytes()).hexdigest()
        if actual!=management_sha256:raise ValueError('CURRENT_MANAGEMENT_CODE_MISMATCH')
        for c in body['cells'].values():
            if (len(c['center'])!=4 or len(c['scale'])!=4 or len(c['min'])!=4 or len(c['max'])!=4 or len(c['coefficients'])!=5 or
                len(c['bootstrap_coefficients'])!=200 or c['contracts']<12 or c['n']<c['contracts']):
                raise ValueError('ARTIFACT_SHAPE_OR_SUPPORT_INVALID')
            nums=c['center']+c['scale']+c['min']+c['max']+c['coefficients']+[c['residual_q10']]
            nums += [v for b in c['bootstrap_coefficients'] for v in b]
            if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in nums) or min(c['scale'])<=0:
                raise ValueError('ARTIFACT_NUMERIC_INVALID')
            if any(len(b)!=5 for b in c['bootstrap_coefficients']):raise ValueError('BOOTSTRAP_SHAPE')
            if any(a>b for a,b in zip(c['min'],c['max'])):raise ValueError('INVALID_SUPPORT_BOUNDARIES')
        self.body=deepcopy(body);self.identity=expected_sha256

    @classmethod
    def load(cls,path,*,expected_sha256,management_sha256):
        return cls(json.loads(Path(path).read_text()),expected_sha256=expected_sha256,management_sha256=management_sha256)

    def infer(self,r,side,x,*,selection_point=False):
        out=dict(**SAFETY,target=TARGET,side=side,context=x.get('context') if x else None,
            price_group=price_group(r[side.lower()+'_ask']),status='UNESTIMATED',ready=False,
            expected_net_cents=None,lower95_net_cents=None,downside_tail_cents=None,
            independent_complete_contracts=0,artifact_sha256=self.identity,
            validation_status='EXPLORATORY_ONLY',live_recommendation_authorized=False,
            decision_time=r['received'],reasons=['EXPLORATORY_NOT_ECONOMICALLY_VALIDATED','NATIVE_EXECUTION_UNVERIFIED'],
            basis=METHOD['estimand'],uncertainty='Nominal contract-bootstrap fitted-mean interval; no validated coverage. Residual q10 is outcome tail, not path drawdown.')
        try:
            if not selection_point:raise ValueError('FIRST_QUALIFICATION_SELECTION_REQUIRED')
            if r.get('evidence_class')=='SYNTHETIC_FIXTURE':raise ValueError('EMPIRICAL_ARTIFACT_NOT_FIXTURE_SUPPORT')
            if validate_row(r):raise ValueError('INVALID_DECISION_ROW')
            if r['received']<=self.body['trained_through']:raise ValueError('ARTIFACT_LABELS_NOT_AVAILABLE_AT_DECISION')
            v=np.array(vector(r,side,x));cell=self.body['cells'].get(side+'_'+x['context'])
            if not cell:raise ValueError('DIRECTION_CONTEXT_UNSUPPORTED')
            if np.any(v<np.array(cell['min'])-1e-8) or np.any(v>np.array(cell['max'])+1e-8):
                raise ValueError('FEATURE_PRICE_OR_RUNWAY_OUT_OF_SUPPORT')
            z=np.r_[1,(v-np.array(cell['center']))/np.array(cell['scale'])]
            mean=float(z@cell['coefficients']);boot=np.array(cell['bootstrap_coefficients'])@z
            lower,upper=np.quantile(boot,[.025,.975]).tolist()
            out.update(status='EXPLORATORY_QUOTE_ESTIMATE',expected_net_cents=mean,
                lower95_net_cents=lower,upper95_net_cents=upper,
                downside_tail_cents=mean+cell['residual_q10'],support_contracts=cell['contracts'],
                diagnostic_selected=mean>0 and lower>0,features=dict(zip(FEATURES,v.tolist())))
        except (ValueError,KeyError,TypeError) as exc:out['reasons'].append(str(exc))
        return out
