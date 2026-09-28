"""Qualified offline forward replay from a preserved model, without any refit."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
from cohort_registry import identity,utc,validate
from frozen_model_artifact import load_verified
from replay_clean_inputs import replay
from fair_forward_shadow import predict


def window(policy,cohort,phase,now):
    copy=dict(cohort);digest=copy.pop('canonical_content_sha256_excluding_this_field')
    if identity(copy)!=digest or policy['cohort_manifest_sha256']!=digest:
        raise ValueError('Cohort/policy identity mismatch')
    validate(cohort)
    declared=next(w for w in cohort['windows']if w['role']==phase)
    start,end=utc(declared['start_utc']),utc(declared['end_utc'])
    if now<start:raise ValueError('Phase has not opened')
    if phase=='untouched_holdout' and now<end:
        raise ValueError('Holdout remains sealed until fixed end')
    if utc(policy['registered_utc'])>=utc(policy['start_utc']):
        raise ValueError('Policy was not registered prospectively')
    start=max(start,utc(policy['start_utc']))
    if start>=min(end,now):raise ValueError('No prospective input window available')
    return start,min(end,now),declared


def run(policy,cohort,phase,journal,artifact,root,now=None):
    now=now or datetime.now(timezone.utc)
    start,end,declared=window(policy,cohort,phase,now)
    if policy['collector_run_id']!=cohort['revisions']['clean']['run_id']:
        raise ValueError('Collector identity mismatch')
    for name,expected in policy['source_sha256'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Frozen analysis source changed: '+name)
    for name,expected in policy['runtime_versions'].items():
        package={'sklearn':'scikit-learn'}.get(name,name)
        if importlib.metadata.version(package)!=expected:
            raise ValueError('Runtime package differs: '+name)
    model=load_verified(artifact,expected_artifact_sha256=policy['artifact_sha256'],
                        expected_weights_sha256=policy['weights_sha256'])
    data=replay(journal,root/'bot_two_output_build_v4_13_profit_protection_shadow.py',
                start.isoformat(),end.isoformat(),0,run_id=policy['collector_run_id'])
    predictions=predict(model['forest'],model['sigmoid'],model['features'],data['decisions'])
    return dict(policy_id=policy['policy_id'],cohort_id=cohort['cohort_id'],phase=phase,
        declared_window=declared,evaluated_start_utc=start.isoformat(),evaluated_end_utc=end.isoformat(),
        candidate_not_registered_before=policy['start_utc'],
        retain_pre_policy_slots_in_common_universe=True,
        artifact_sha256=policy['artifact_sha256'],model_weights_sha256=policy['weights_sha256'],
        predictions=predictions,feature_waits=[r for r in data['decisions']if r['status']!='READY'],
        captured_input_cuts=len(data['decisions']),journal_damage=data['journal_damage'],
        baseline_publication_equivalence=False,performance_certified=False,
        production_connected=False,orders=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['policy','cohort','journal','artifact','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--phase',required=True);args=parser.parse_args()
    result=run(json.loads(args.policy.read_text()),json.loads(args.cohort.read_text()),args.phase,
                args.journal,args.artifact,Path(__file__).resolve().parents[1])
    with args.output.open('x')as stream:json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps(dict(captured_input_cuts=result['captured_input_cuts'],
                         predictions=len(result['predictions']),performance_certified=False,orders=False)))
