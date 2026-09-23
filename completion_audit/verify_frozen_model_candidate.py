"""Offline deterministic fitting check. Does not import or start the bot.

Historical evaluation was already opened; this is not performance acceptance.
No production model, training artifact, threshold or weight is changed.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
import platform
import subprocess
import sys
import joblib
import scipy
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from fair_input_candidate import load_frozen_inputs, price_at_or_before, select_frozen_rows


def main():
    root=Path(__file__).resolve().parents[1]
    source=root/'bot_two_output_build_v4_13_profit_protection_shadow.py'
    manifest_path=root/'completion_audit/fair_candidate_replay_manifest.json'
    manifest, labels, completed=load_frozen_inputs(root,manifest_path)
    tree=ast.parse(source.read_text())
    nodes=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)
           and n.name in ('_fair_parse_contract_times','_fair_build_snapshot')]
    env=dict(pd=pd,np=np,re=re,ZoneInfo=ZoneInfo,_fair_price_at_or_before=price_at_or_before,
             _fair_months={m:i+1 for i,m in enumerate(['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'])})
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<pure fair feature functions>','exec'),env)
    rows=[]
    for row in labels.to_dict('records'):
        start,_=env['_fair_parse_contract_times'](row['ticker'])
        for elapsed in range(1,15):
            snapshot=env['_fair_build_snapshot'](completed,start,float(row['target_brti']),
                                                _final_side=int(row['result']=='yes'),_elapsed=elapsed)
            if snapshot is not None:
                snapshot.update(ticker=row['ticker'],start=start)
                rows.append(snapshot)
    data=pd.DataFrame(rows)
    groups=select_frozen_rows(data,manifest)
    fit=groups['fit'];cal=groups['calibration'];evaluate=groups['historical_evaluation_already_opened']
    assert fit.start.max()<cal.start.min() and cal.start.max()<evaluate.start.min()
    features=manifest['features'];models=[];predictions=[]
    for run in range(2):
        # Same existing hyperparameters and random seeds; no search or tuning.
        # Serial accumulation avoids thread-order rounding changes feeding the
        # sigmoid fit. This changes execution, not tree/model hyperparameters.
        forest=RandomForestClassifier(**manifest['model_parameters'],n_jobs=1)
        forest.fit(fit[features],fit['flip'])
        sigmoid=LogisticRegression(**manifest['calibration_parameters'])
        sigmoid.fit(forest.predict_proba(cal[features])[:,1].reshape(-1,1),cal['flip'])
        weights=hashlib.sha256()
        for estimator in forest.estimators_:
            for field in ('children_left','children_right','feature','threshold','value'):
                weights.update(getattr(estimator.tree_,field).tobytes())
        tree_hash=weights.hexdigest()
        calibration_hash=hashlib.sha256(sigmoid.coef_.tobytes()+sigmoid.intercept_.tobytes()).hexdigest()
        weights.update(sigmoid.coef_.tobytes());weights.update(sigmoid.intercept_.tobytes())
        models.append(weights.hexdigest())
        predictions.append(sigmoid.predict_proba(forest.predict_proba(evaluate[features])[:,1].reshape(-1,1))[:,1])
        print(json.dumps({'fit_run':run+1,'weights_sha256':models[-1],
                          'tree_weights_sha256':tree_hash,'calibration_weights_sha256':calibration_hash}),flush=True)
    assert models[0]==models[1]
    difference=float(np.max(np.abs(predictions[0]-predictions[1])))
    assert np.array_equal(predictions[0],predictions[1])
    # Preserve one fitted artifact. A production consumer must load this exact
    # checked hash, never refit opportunistically at restart.
    artifact_dir=root/'completion_audit/model_artifact'
    artifact_dir.mkdir(exist_ok=True)
    artifact=artifact_dir/'frozen_fair_candidate.joblib'
    joblib.dump(dict(forest=forest,sigmoid=sigmoid,features=features,
                    weights_sha256=models[-1],input_sha256=manifest['input_sha256']),artifact,compress=3)
    np.save(artifact_dir/'verification_features.npy',evaluate[features].to_numpy())
    np.save(artifact_dir/'expected_predictions.npy',predictions[-1])
    subprocess.run([sys.executable,'-c',
        "import numpy as np,pandas as pd,sys;from pathlib import Path;"
        "sys.path.insert(0,sys.argv[4]);from frozen_model_artifact import load_verified;"
        "p=Path(sys.argv[1]);m=load_verified(p/'frozen_fair_candidate.joblib',"
        "expected_artifact_sha256=sys.argv[2],expected_weights_sha256=sys.argv[3]);"
        "x=pd.DataFrame(np.load(p/'verification_features.npy'),columns=m['features']);"
        "r=m['sigmoid'].predict_proba(m['forest'].predict_proba(x)[:,1].reshape(-1,1))[:,1];"
        "assert np.array_equal(r,np.load(p/'expected_predictions.npy'));"
        "print('FROZEN_ARTIFACT_RELOAD_EXACT_PASS')",str(artifact_dir),
        hashlib.sha256(artifact.read_bytes()).hexdigest(),models[-1],str(root/'completion_audit')],check=True)
    result=dict(status='OFFLINE_CANDIDATE_ONLY_NOT_DEPLOYED',
                manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                pure_feature_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                input_sha256=manifest['input_sha256'],
                runtime_versions=dict(numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__,
                    scipy=scipy.__version__,python=sys.version.split()[0],machine=platform.machine()),
                contracts_by_role={k:int(v.ticker.nunique()) for k,v in groups.items()},
                snapshots_by_role={k:len(v) for k,v in groups.items()},
                identical_refit_weight_hashes=models,max_prediction_difference=difference,
                tree_weights_sha256=tree_hash,calibration_weights_sha256=calibration_hash,
                artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),artifact_bytes=artifact.stat().st_size,
                new_process_artifact_reload_exact=True,forest_prediction_jobs=1,
                historical_evaluation_is_new_holdout=False,production_promoted=False,
                remaining=['Online model-shadow integration and native publication equivalence remain unverified.',
                           'A registered common universe still needs meaningful separated forward evidence.',
                           'No EARLY/FINAL/SCALP threshold or weight optimization is justified.'])
    (root/'completion_audit/frozen_model_candidate_verification.json').write_text(json.dumps(result,indent=2)+'\n')
    (artifact_dir/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    forward_path=root/'completion_audit/forward_features_development_20260923.json'
    if forward_path.exists():
        from fair_forward_shadow import predict
        forward=json.loads(forward_path.read_text())
        output=dict(scope='Offline fixed-model replay of prospectively captured DEVELOPMENT inputs only',
                    model_weights_sha256=models[-1],runtime_versions=result['runtime_versions'],
                    forward_features_sha256=hashlib.sha256(forward_path.read_bytes()).hexdigest(),
                    predictions=predict(forest,sigmoid,features,forward['decisions']),
                    missing_feature_cuts=sum(r['status']!='READY'for r in forward['decisions']),
                    certified_performance=False,production_promoted=False,orders=False)
        (root/'completion_audit/fair_forward_shadow_result.json').write_text(json.dumps(output,indent=2)+'\n')
        print('FROZEN_FORWARD_SHADOW '+json.dumps(output),flush=True)


if __name__=='__main__':main()
