"""Offline, fixed-grid FINAL comparison. No fitting, optimization or runtime hook.

Production-grade scoring requires full native causal frames and official labels;
old selected-call CSVs are inventoried, never silently substituted for that data.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

from btc15_v2_product.directional import qualify, protected_frame
from btc15_v2_product.early_entry import ARTIFACT, WEIGHTS

VARIANTS = ('CURRENT_75_50','LATE_40','LATE_30','LATE_20','LATE_10','NO_FIXED_DISTANCE',
            'SETTLEMENT_SUPPLEMENT','SETTLEMENT_REPLACE')


def wilson(successes, n):
    if not n:return None
    z=1.959963984540054; p=successes/n; denominator=1+z*z/n
    centre=(p+z*z/(2*n))/denominator
    width=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
    return [max(0,centre-width),min(1,centre+width)]


def acceptance(f, at, variant, settlement_supported=None):
    """All non-distance protected gates held constant, including >=90%.

LATE variants keep $75 at 6–8 minutes and change only the $50 phase.
NO_FIXED removes both absolute-dollar phases but keeps distance/range >=1.
Settlement alternatives require a separately prevalidated causal decision input;
the diagnostic hurdle or an eventual average alone cannot certify a lock.
"""
    qualify(f,at);raw,_=protected_frame(f,at);g=deepcopy(raw['final']['conditions'])
    left=f['official_close']-f['captured_ts'];gap=abs(f['btc_price']-f['target'])
    if variant.startswith('LATE_'):
        g['gap_ok']=gap >= (75 if left>360 else float(variant.split('_')[1]))
    elif variant=='NO_FIXED_DISTANCE':g['gap_ok']=True
    elif variant in ('SETTLEMENT_SUPPLEMENT','SETTLEMENT_REPLACE'):
        if settlement_supported is None:return None
        if variant=='SETTLEMENT_REPLACE':g['gap_ok']=True
        g['settlement_supported']=settlement_supported is True
    elif variant!='CURRENT_75_50':raise ValueError('UNKNOWN_VARIANT')
    return all(g.values())


def evaluate(frames, labels):
    """First qualified lock per contract, not every poll as an independent win.

Caller must supply an independently reviewed dataset manifest. This function
checks per-row mechanics; it does not certify undocumented provenance/calibration.
Only explicit heldout role rows with matching model bytes enter the comparison.
"""
    rejected=Counter(); eligible=[];seen={};conflicted=set()
    for row in frames:
        try:
            f=row['frame'];at=row['decision_ts'];c=f['contract'];label=labels[c]
            if f.get('kind')!='NATIVE_DECISION':raise ValueError('NATIVE_DECISION_REQUIRED')
            if row.get('role')!='UNTOUCHED_EVALUATION':raise ValueError('NOT_UNTOUCHED_EVALUATION')
            if row.get('provenance_reviewed') is not True:raise ValueError('PROVENANCE_UNREVIEWED')
            if f.get('artifact')!=ARTIFACT or f.get('weights')!=WEIGHTS:raise ValueError('MODEL_IDENTITY')
            if (label.get('status')!='finalized' or label.get('result') not in ('UP','DOWN') or
                label.get('target')!=f['target'] or label.get('official_close')!=f['official_close'] or
                not label.get('source_receipt_sha256')):raise ValueError('OFFICIAL_LABEL_BINDING')
            qualify(f,at)
            if row.get('selected_calls_only') is not False:raise ValueError('SELECTION_BIASED_DATA')
            if not row.get('volatility_regime_from_frozen_development_bins'):raise ValueError('REGIME_PROVENANCE')
            key=(c,f['native_epoch'],f['native_sequence'])
            body=json.dumps(f,sort_keys=True,allow_nan=False)
            if key in seen:
                if body!=seen[key]:conflicted.add(key)
                rejected['DUPLICATE_OR_CONFLICTING_FRAME']+=1;continue
            seen[key]=body;eligible.append((row,label,key))
        except (KeyError,ValueError,TypeError) as exc:rejected[str(exc)]+=1
    eligible=[x for x in eligible if x[2] not in conflicted]
    eligible.sort(key=lambda x:x[0]['decision_ts'])
    chosen={v:{} for v in VARIANTS};coverage=Counter()
    for row,label,key in eligible:
        f=row['frame'];c=f['contract']
        # No trusted settlement model has been supplied in this study. Future
        # integration must verify its receipt/binding before supplying a boolean.
        for variant in VARIANTS:
            decision=acceptance(f,row['decision_ts'],variant)
            if decision is None:continue
            coverage[variant]+=1
            if not decision or c in chosen[variant]:continue
            side=f['fair']['side'];p=f['fair']['fair'];y=int(side==label['result'])
            left=f['official_close']-row['decision_ts']
            chosen[variant][c]=dict(contract=c,side=side,p=p,correct=y,lead_seconds=left,
                volatility_regime=row['volatility_regime_from_frozen_development_bins'],
                time_band=('0–60' if left<=60 else '60–180' if left<=180 else '180–360' if left<=360 else '360–480'))
    def metrics(rows):
        n=len(rows);good=sum(x['correct'] for x in rows)
        return dict(n=n,correct=good,incorrect=n-good,accuracy=good/n if n else None,
            false_lock_rate=(n-good)/n if n else None,accuracy_wilson95=wilson(good,n),
            false_lock_wilson95=wilson(n-good,n),
            mean_confidence=statistics.mean(x['p'] for x in rows) if n else None,
            brier=statistics.mean((x['p']-x['correct'])**2 for x in rows) if n else None,
            mean_lead_seconds=statistics.mean(x['lead_seconds'] for x in rows) if n else None,
            median_lead_seconds=statistics.median(x['lead_seconds'] for x in rows) if n else None)
    summary={};baseline=set(chosen['CURRENT_75_50'])
    for variant,data in chosen.items():
        rows=list(data.values());new=[r for c,r in data.items() if c not in baseline]
        groups={}
        for field in ('side','time_band','volatility_regime'):
            groups[field]={key:metrics([x for x in rows if x[field]==key]) for key in sorted({x[field] for x in rows})}
        paired=[data[c]['lead_seconds']-chosen['CURRENT_75_50'][c]['lead_seconds'] for c in set(data)&baseline]
        summary[variant]=dict(status='SCORABLE' if coverage[variant] else 'INSUFFICIENT_EVIDENCE',
            eligible_frames=coverage[variant],**metrics(rows),additional_contract_locks=len(new) if coverage[variant] and coverage['CURRENT_75_50'] else None,
            additional=metrics(new),groups=groups,mean_earlier_seconds_on_common_contracts=statistics.mean(paired) if paired else None,
            first_lock_records=rows)
    return dict(comparison=summary,accepted_native_frames=len(eligible),rejected=dict(rejected),
        evaluation_is_statistical_validation=False,
        uncertainty_note='Wilson intervals assume independent contracts. Day-block paired uncertainty and regime coverage are required before promotion.',
        optimization_performed=False,production_change=False)


def inventory(root):
    files=[]
    for p in sorted(root.glob('*.csv')):
        with p.open(errors='replace') as stream:
            reader=csv.DictReader(stream);cols=reader.fieldnames or []
            related=any(k in cols for k in ('fair_up','preferred_fair','final60_average','call_side','official_result'))
            if not related:continue
            rows=list(reader)
        ts=[x.get('timestamp_utc') or x.get('snapshot_utc') or x.get('call_time') for x in rows]
        files.append(dict(file=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),rows=len(rows),
            contracts=len({x.get('contract') or x.get('ticker') for x in rows}),
            first=next((x for x in ts if x),None),last=next((x for x in reversed(ts) if x),None),
            columns=cols,complete_native_frame_columns=all(k in cols for k in ('native_epoch','native_sequence','feature_cutoff','quote','brti','artifact','weights'))))
    manifest=json.loads((root/'completion_audit/model_artifact/manifest.json').read_text())
    return dict(files=files,complete_native_csv_files=sum(x['complete_native_frame_columns'] for x in files),
        existing_model_evaluation_roles=manifest['contracts_by_role'],
        historical_evaluation_is_new_holdout=manifest['historical_evaluation_is_new_holdout'],
        limitation='Selected calls cannot measure additional locks. Aggregate BRTI and unrelated logged fair values lack an exact causal native-frame join and current model/source proof. No missing fields imputed.')


if __name__=='__main__':
    root=Path(__file__).resolve().parents[2]
    inv=inventory(root);result=evaluate([], {})
    result.update(inventory=inv,recommendation='KEEP CURRENT 75/50 AND 90% PENDING VALIDATION',
                  production_ready=False,settlement_model_available=False,
                  source_screening=dict(current_native_complete_cohort=0,
                    why_not_reconstruct='No complete causal native-frame cohort with current model/source proof and untouched evaluation was recovered. No missing fields imputed.',
                    not_zero_false_locks='N=0 means unscorable, not evidence of zero false locks.'))
    print(json.dumps(result,indent=2))
