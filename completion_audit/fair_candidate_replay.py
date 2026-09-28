"""Research-only fair-engine reproducibility/availability comparison.

No production imports, downloads, orders, threshold search or promotion.
Evaluation uses previously inspected historical contracts: NOT fresh holdout.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

root=Path(__file__).resolve().parents[1]
source=root/'bot_two_output_build_v4_13_profit_protection_shadow.py'
tree=ast.parse(source.read_text())
names={'_fair_parse_contract_times','_fair_price_at_or_before','_fair_build_snapshot'}
nodes=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in names]
env=dict(pd=pd,np=np,re=re,ZoneInfo=ZoneInfo,
         _fair_months={m:i+1 for i,m in enumerate(['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'])})
exec(compile(ast.Module(body=nodes,type_ignores=[]),'<existing pure fair functions>','exec'),env)
features=next(ast.literal_eval(n.value) for n in ast.walk(tree)
              if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_fair_features' for t in n.targets))
cal=pd.read_csv(root/'brti_calibration_results.csv')
btc=pd.read_csv(root/'btc_35d_live_cache.csv',index_col='Datetime',parse_dates=True).sort_index()
fixed_role_contracts=sorted(cal['ticker'],key=lambda t:env['_fair_parse_contract_times'](t)[0])
roles={'fit':fixed_role_contracts[:int(len(fixed_role_contracts)*.5)],
       'calibration':fixed_role_contracts[int(len(fixed_role_contracts)*.5):int(len(fixed_role_contracts)*.7)],
       'historical_evaluation_already_opened':fixed_role_contracts[int(len(fixed_role_contracts)*.7):]}
assert not set(roles['fit']) & set(roles['historical_evaluation_already_opened'])
assert not set(roles['calibration']) & set(roles['historical_evaluation_already_opened'])
manifest=dict(status='RESEARCH_ONLY_NOT_DEPLOYED',new_holdout=False,roles=roles,
              input_sha256={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('brti_calibration_results.csv','btc_35d_live_cache.csv')},
              model_parameters=dict(n_estimators=900,max_depth=9,min_samples_leaf=12,class_weight='balanced',random_state=42),
              calibration_parameters=dict(solver='lbfgs',C=1.,max_iter=1000,random_state=42),
              features=features,threshold_tuning=False)
(root/'completion_audit/fair_candidate_replay_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
output={}
predictions={}
for mode in ('existing_original_history','existing_current_clock_cut','candidate_completed_candle_availability'):
 frame=btc.copy()
 if mode=='existing_current_clock_cut':frame=frame[frame.index>=pd.Timestamp('2026-09-23T12:26:30Z')-pd.Timedelta(days=35)]
 if mode=='candidate_completed_candle_availability':frame.index=frame.index+pd.Timedelta(minutes=1)
 rows=[]
 for row in cal.to_dict('records'):
  opened,closed=env['_fair_parse_contract_times'](row['ticker'])
  if frame.empty or closed<frame.index.min():continue
  for elapsed in range(1,15):
   s=env['_fair_build_snapshot'](frame,opened,float(row['target_brti']),_final_side=int(row['result']=='yes'),_elapsed=elapsed)
   if s is not None:s.update(ticker=row['ticker'],start=opened);rows.append(s)
 d=pd.DataFrame(rows)
 eligible=d.groupby('ticker')['elapsed'].nunique();d=d[d.ticker.isin(eligible[eligible>=10].index)]
 tickers=sorted(d.ticker.unique(),key=lambda t:env['_fair_parse_contract_times'](t)[0])
 a=int(len(tickers)*.5);b=int(len(tickers)*.7)
 # Reproduce the current incumbent's actual shrinking split separately. The
 # candidate has fixed original roles; missing data is an error, not re-split.
 if mode=='existing_current_clock_cut':
  fit_tickers=tickers[:a];cal_tickers=tickers[a:b];eval_tickers=tickers[b:]
 else:
  assert set(tickers)==set(fixed_role_contracts)
  fit_tickers=roles['fit'];cal_tickers=roles['calibration'];eval_tickers=roles['historical_evaluation_already_opened']
 fit=d[d.ticker.isin(fit_tickers)];calibrate=d[d.ticker.isin(cal_tickers)];evaluate=d[d.ticker.isin(eval_tickers)]
 model=RandomForestClassifier(**manifest['model_parameters'],n_jobs=2)
 model.fit(fit[features],fit['flip'])
 sigmoid=LogisticRegression(**manifest['calibration_parameters'])
 sigmoid.fit(model.predict_proba(calibrate[features])[:,1].reshape(-1,1),calibrate['flip'].astype(int))
 flip=np.clip(sigmoid.predict_proba(model.predict_proba(evaluate[features])[:,1].reshape(-1,1))[:,1],.001,.999)
 up=np.where(evaluate['current_side'].to_numpy()==1,1-flip,flip)
 pred=pd.DataFrame(dict(ticker=evaluate.ticker.to_numpy(),elapsed=evaluate.elapsed.to_numpy(),p_up=up,outcome=evaluate.final_side.to_numpy()))
 predictions[mode]=pred
 per_contract=pred.assign(brier=(pred.p_up-pred.outcome)**2).groupby('ticker')['brier'].mean()
 output[mode]=dict(eligible_contracts=len(tickers),fit_contracts=len(fit_tickers),calibration_contracts=len(cal_tickers),
                   evaluation_contracts=len(eval_tickers),evaluation_snapshots=len(evaluate),
                   mean_contract_brier=float(per_contract.mean()),
                   feature_importance=dict(zip(features,map(float,model.feature_importances_))),
                   sigmoid_coefficient=float(sigmoid.coef_[0,0]),sigmoid_intercept=float(sigmoid.intercept_[0]))
 print(mode,json.dumps({k:v for k,v in output[mode].items() if k!='feature_importance'}),flush=True)
common=set.intersection(*(set(p.ticker) for p in predictions.values()))
comparisons={}
for name,pred in predictions.items():
 p=pred[pred.ticker.isin(common)].copy();p['brier']=(p.p_up-p.outcome)**2
 comparisons[name]=dict(contracts=len(common),snapshots=len(p),mean_contract_brier=float(p.groupby('ticker').brier.mean().mean()))
result=dict(status='RESEARCH_ONLY_NOT_DEPLOYED',fresh_holdout=False,variants=output,common_historical_evaluation=comparisons,
            certification_blockers=['Historical evaluation already inspected; no fresh holdout claim.',
                                    'No historical timestamped quotes or BRTI at call means no qualified EARLY/FINAL/SCALP performance inference.',
                                    'Candidate requires separately verified live partial-bar availability integration.',
                                    'Production model weights and thresholds remain unchanged.'])
(root/'completion_audit/fair_candidate_replay_results.json').write_text(json.dumps(result,indent=2)+'\n')
