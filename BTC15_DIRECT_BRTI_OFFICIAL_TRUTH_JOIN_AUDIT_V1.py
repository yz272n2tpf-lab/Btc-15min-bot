#!/usr/bin/env python3
"""
BTC15 direct-BRTI tape -> official Kalshi settlement join audit V1.
READ ONLY | NO MODEL FIT | NO SIGNAL CHANGES | NO ORDERS
"""
from pathlib import Path
import pandas as pd
import numpy as np

TAPE=Path('kalshi_direct_brti_parity_v1.csv')
TRUTH=Path('kalshi_official_settlement_check.csv')
print('=== BTC15 DIRECT BRTI OFFICIAL TRUTH JOIN AUDIT V1 ===',flush=True)
print('READ ONLY | NO MODEL FIT | NO ORDERS',flush=True)
for p in (TAPE,TRUTH):
 if not p.exists(): raise SystemExit('STOP: missing '+str(p))
df=pd.read_csv(TAPE); truth=pd.read_csv(TRUTH)
df['timestamp_utc']=pd.to_datetime(df['timestamp_utc'],utc=True,errors='coerce')
for c in ['seconds_left','direct_brti','brti_age_seconds']:df[c]=pd.to_numeric(df[c],errors='coerce')
truth['ticker']=truth['ticker'].astype(str);truth['official_side']=truth['official_side'].astype(str).str.upper();truth['status']=truth['status'].astype(str).str.lower()
truth=truth[(truth.status=='finalized') & truth.official_side.isin(['UP','DOWN'])].copy()
conflicts=truth.groupby('ticker').official_side.nunique();conflict_tickers=conflicts[conflicts>1].index.tolist()
truth_one=truth.sort_values('settlement_ts').drop_duplicates('ticker',keep='last').set_index('ticker')

stats=[]
for c,g in df.groupby('contract',sort=False):
 g=g.sort_values('timestamp_utc');ts=g.timestamp_utc.dropna();d=ts.diff().dt.total_seconds().dropna();d=d[(d>0)&np.isfinite(d)]
 first=g.seconds_left.max() if g.seconds_left.notna().any() else np.nan;last=g.seconds_left.min() if g.seconds_left.notna().any() else np.nan;span=(ts.max()-ts.min()).total_seconds() if len(ts)>=2 else 0.;p95=float(d.quantile(.95)) if len(d) else np.nan;rr=float(g.direct_brti_ready.astype(str).str.lower().isin(['true','1','yes']).mean());usable=bool(pd.notna(first) and first>=600 and span>=300 and pd.notna(p95) and p95<=8 and rr>=.95)
 complete=g.final60_complete.astype(str).str.lower().isin(['true','1','yes']);proxy=None
 if complete.any():
  vals=g.loc[complete,'final60_side'].dropna().astype(str).str.upper();proxy=vals.iloc[-1] if len(vals) and vals.iloc[-1] in {'UP','DOWN'} else None
 official=truth_one.loc[c,'official_side'] if c in truth_one.index else None
 stats.append(dict(contract=c,usable=usable,official=official,proxy=proxy,truth_match=official in {'UP','DOWN'},proxy_available=proxy in {'UP','DOWN'},proxy_agrees=(proxy==official) if proxy in {'UP','DOWN'} and official in {'UP','DOWN'} else None,first_left=first,last_left=last,span=span,p95=p95,ready_rate=rr))
s=pd.DataFrame(stats)
all_n=len(s);matched=int(s.truth_match.sum());usable=s[s.usable];usable_matched=int(usable.truth_match.sum())
proxy=s[s.proxy_available & s.truth_match]
print('tape_contracts:',all_n)
print('official_finalized_truth_rows_unique:',len(truth_one))
print('truth_conflict_tickers:',len(conflict_tickers))
print('tape_contracts_with_official_truth:',matched,'/',all_n,'rate=',round(matched/all_n,6) if all_n else None)
print('usable_feature_contracts:',len(usable))
print('usable_with_official_truth:',usable_matched,'/',len(usable),'rate=',round(usable_matched/len(usable),6) if len(usable) else None)
print('missing_official_truth_contracts:',','.join(s.loc[~s.truth_match,'contract'].astype(str).tolist()) if matched<all_n else 'NONE')
print('proxy_complete_and_official_n:',len(proxy))
print('final60_proxy_vs_official_agreement:',round(float(proxy.proxy_agrees.mean()),6) if len(proxy) else None)
print('proxy_disagreement_contracts:',','.join(proxy.loc[proxy.proxy_agrees==False,'contract'].astype(str).tolist()) if len(proxy) and (~proxy.proxy_agrees.astype(bool)).any() else 'NONE')
# Development-study sufficiency requires official truth on at least 80 feature-usable contracts.
sufficient=bool(usable_matched>=80 and len(conflict_tickers)==0)
print('\n=== JOIN DECISION ===')
print('OFFICIAL_TRUTH_JOIN_SUFFICIENT_FOR_MODEL_STUDY='+str(sufficient))
print('MODEL_LABEL_SOURCE=OFFICIAL_KALSHI_SETTLEMENT_ONLY')
print('FINAL60_PROXY_ALLOWED_AS_MODEL_LABEL=False')
print('NO_MODEL_WAS_FIT=True')
print('PRODUCTION_CHANGED=False | SIGNAL_THRESHOLDS_CHANGED=False | ORDERS=False')
print('NEXT_SAFE_STEP='+('FREEZE_DIRECT_BRTI_MODEL_DEV_HOLDOUT_METHODOLOGY_BEFORE_ANY_FIT' if sufficient else 'INSPECT_OR_REFRESH_OFFICIAL_SETTLEMENT_TRUTH_BEFORE_MODEL_FIT'))
