#!/usr/bin/env python3
from pathlib import Path
import pandas as pd
import numpy as np
PATH=Path('kalshi_direct_brti_parity_v1.csv')
REQ=['timestamp_utc','contract','target','seconds_left','direct_brti','brti_timestamp_utc','brti_age_seconds','brti_gap_to_target','brti_side','final60_count','final60_average','final60_gap_to_target','final60_side','final60_complete','direct_brti_ready']
print('=== BTC15 DIRECT BRTI TAPE INVENTORY V1 ===',flush=True)
print('READ ONLY | NO MODEL FIT | NO ORDERS',flush=True)
if not PATH.exists(): raise SystemExit('STOP: missing '+str(PATH))
df=pd.read_csv(PATH);print('rows:',len(df));print('columns:',','.join(df.columns));missing=[c for c in REQ if c not in df.columns];print('required_columns_missing:',missing)
if missing: raise SystemExit(2)
df['timestamp_utc']=pd.to_datetime(df['timestamp_utc'],utc=True,errors='coerce');df['brti_timestamp_utc']=pd.to_datetime(df['brti_timestamp_utc'],utc=True,errors='coerce')
for c in ['target','seconds_left','direct_brti','brti_age_seconds','brti_gap_to_target','final60_count','final60_average','final60_gap_to_target']:df[c]=pd.to_numeric(df[c],errors='coerce')
df=df.sort_values(['contract','timestamp_utc']).reset_index(drop=True);print('contracts:',df.contract.nunique());print('time_min:',df.timestamp_utc.min());print('time_max:',df.timestamp_utc.max());print('timestamp_nulls:',int(df.timestamp_utc.isna().sum()));print('direct_brti_nulls:',int(df.direct_brti.isna().sum()));print('target_nulls:',int(df.target.isna().sum()));print('seconds_left_nulls:',int(df.seconds_left.isna().sum()))
ready=df.direct_brti_ready.astype(str).str.lower().isin(['true','1','yes']);print('direct_brti_ready_rate:',round(float(ready.mean()),6));ages=df.brti_age_seconds.dropna();print('brti_age_median_s:',round(float(ages.median()),3) if len(ages) else None);print('brti_age_p95_s:',round(float(ages.quantile(.95)),3) if len(ages) else None);print('brti_age_max_s:',round(float(ages.max()),3) if len(ages) else None)
stats=[];all_d=[]
for c,g in df.groupby('contract',sort=False):
 g=g.sort_values('timestamp_utc');ts=g.timestamp_utc.dropna();d=ts.diff().dt.total_seconds().dropna();d=d[(d>0)&np.isfinite(d)];all_d.extend(d.tolist());first=g.seconds_left.max() if g.seconds_left.notna().any() else np.nan;last=g.seconds_left.min() if g.seconds_left.notna().any() else np.nan;span=(ts.max()-ts.min()).total_seconds() if len(ts)>=2 else 0.;p95=float(d.quantile(.95)) if len(d) else np.nan;complete=g.final60_complete.astype(str).str.lower().isin(['true','1','yes']).any();rr=float(g.direct_brti_ready.astype(str).str.lower().isin(['true','1','yes']).mean());stats.append(dict(contract=c,rows=len(g),first_left=first,last_left=last,span=span,p95=p95,complete60=complete,ready_rate=rr,seen_by_10=bool(pd.notna(first) and first>=600),seen_by_12=bool(pd.notna(first) and first>=720),near_close=bool(pd.notna(last) and last<=10),history5=span>=300,history10=span>=600,cadence_ok=bool(pd.notna(p95) and p95<=8)))
s=pd.DataFrame(stats)
def n(x):return int(s[x].sum())
def rate(x):return round(float(s[x].mean()),6) if len(s) else None
print('\n=== CADENCE ===')
if all_d:
 a=pd.Series(all_d);print('global_median_spacing_s:',round(float(a.median()),3));print('global_p95_spacing_s:',round(float(a.quantile(.95)),3));print('global_p99_spacing_s:',round(float(a.quantile(.99)),3));print('global_max_spacing_s:',round(float(a.max()),3))
print('contract_median_rows:',round(float(s.rows.median()),1) if len(s) else None);print('contract_median_span_s:',round(float(s.span.median()),1) if len(s) else None);print('contract_median_first_seen_left_s:',round(float(s.first_left.median()),1) if len(s) else None);print('contract_median_last_seen_left_s:',round(float(s.last_left.median()),1) if len(s) else None);print('contracts_p95_spacing_le_8s:',n('cadence_ok'),'/',len(s),'rate=',rate('cadence_ok'))
print('\n=== COVERAGE ===')
for flag,label in [('seen_by_12','first_seen>=12m'),('seen_by_10','first_seen>=10m'),('history5','>=5m observed history'),('history10','>=10m observed history'),('near_close','observed<=10s left'),('complete60','final60_complete')]:print(label+':',n(flag),'/',len(s),'rate=',rate(flag))
usable=s.seen_by_10&s.history5&s.cadence_ok&(s.ready_rate>=.95);labelable=usable&(s.near_close|s.complete60);print('candidate_feature_usable_contracts:',int(usable.sum()),'/',len(s),'rate=',round(float(usable.mean()),6) if len(s) else None);print('candidate_feature_plus_close_truth_proxy_contracts:',int(labelable.sum()),'/',len(s),'rate=',round(float(labelable.mean()),6) if len(s) else None)
print('\n=== RECONSTRUCTABILITY ===');print('elapsed_remaining=YES');print('current_side_target_distance=YES');print('brti_move_1m_2m_3m_5m=', 'YES' if int(usable.sum())>0 else 'NO');print('brti_support_signs=', 'YES' if int(usable.sum())>0 else 'NO');print('brti_native_range5=', 'YES' if int(usable.sum())>0 else 'NO');print('brti_native_vol5=', 'YES' if int(usable.sum())>0 else 'NO');print('coinbase_ohlc_equivalence=NO_AND_NOT_REQUIRED_FOR_NEW_MODEL')
sufficient=bool(len(s)>=100 and int(usable.sum())>=80 and int(labelable.sum())>=60);print('\n=== INVENTORY DECISION ===');print('DIRECT_BRTI_TAPE_SUFFICIENT_FOR_MODEL_STUDY='+str(sufficient));print('NO_MODEL_WAS_FIT=True');print('PRODUCTION_CHANGED=False | SIGNAL_THRESHOLDS_CHANGED=False | ORDERS=False');print('NEXT_SAFE_STEP='+('FREEZE_DIRECT_BRTI_MODEL_DEV_HOLDOUT_METHODOLOGY_BEFORE_ANY_FIT' if sufficient else 'INSPECT_NEXT_EXISTING_DIRECT_BRTI_DATASET_BEFORE_STARTING_NEW_COLLECTOR'))
