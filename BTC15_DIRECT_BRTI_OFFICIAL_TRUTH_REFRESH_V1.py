#!/usr/bin/env python3
"""
BTC15 direct-BRTI targeted official truth refresh V1.
READ ONLY | PUBLIC KALSHI GETS ONLY | NO MODEL FIT | NO ORDERS

Fetches official finalized Kalshi result only for contracts present in the
committed direct-BRTI tape. Does not overwrite the older settlement cache.
"""
from __future__ import annotations
import json,time,urllib.request
import pandas as pd
import numpy as np

TAPE='kalshi_direct_brti_parity_v1.csv'
LIVE='https://external-api.kalshi.com/trade-api/v2/markets/'
HIST='https://external-api.kalshi.com/trade-api/v2/historical/markets/'

def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read().decode('utf-8'))
def market(t):
 errs=[]
 for base in (LIVE,HIST):
  try:
   p=fetch(base+t);m=p.get('market',p)
   if isinstance(m,dict) and m.get('ticker'):return m,None
  except Exception as e:errs.append(type(e).__name__+':'+str(e))
 return None,' | '.join(errs)

print('=== BTC15 DIRECT BRTI OFFICIAL TRUTH REFRESH V1 ===',flush=True)
print('READ ONLY | PUBLIC GETS | NO MODEL FIT | NO ORDERS',flush=True)
df=pd.read_csv(TAPE);df['timestamp_utc']=pd.to_datetime(df.timestamp_utc,utc=True,errors='coerce');df['seconds_left']=pd.to_numeric(df.seconds_left,errors='coerce')
# Recreate inventory usable definition so official-truth sufficiency applies to the same universe.
st=[]
for c,g in df.groupby('contract',sort=False):
 g=g.sort_values('timestamp_utc');ts=g.timestamp_utc.dropna();d=ts.diff().dt.total_seconds().dropna();d=d[(d>0)&np.isfinite(d)];first=g.seconds_left.max() if g.seconds_left.notna().any() else np.nan;span=(ts.max()-ts.min()).total_seconds() if len(ts)>=2 else 0.;p95=float(d.quantile(.95)) if len(d) else np.nan;rr=float(g.direct_brti_ready.astype(str).str.lower().isin(['true','1','yes']).mean());usable=bool(pd.notna(first) and first>=600 and span>=300 and pd.notna(p95) and p95<=8 and rr>=.95);complete=g.final60_complete.astype(str).str.lower().isin(['true','1','yes']);proxy=None
 if complete.any():
  v=g.loc[complete,'final60_side'].dropna().astype(str).str.upper();proxy=v.iloc[-1] if len(v) and v.iloc[-1] in {'UP','DOWN'} else None
 st.append((str(c),usable,proxy))

out=[]
for i,(t,usable,proxy) in enumerate(st,1):
 m,err=market(t)
 if m is None:
  rec={'ticker':t,'status':'FETCH_ERROR','result':'','official_side':'','settlement_ts':'','usable':usable,'final60_proxy':proxy or '','error':err or ''}
 else:
  result=str(m.get('result') or '').lower().strip();side='UP' if result=='yes' else ('DOWN' if result=='no' else '');rec={'ticker':t,'status':str(m.get('status') or '').lower().strip(),'result':result,'official_side':side,'settlement_ts':str(m.get('settlement_ts') or ''),'usable':usable,'final60_proxy':proxy or '','error':''}
 out.append(rec)
 print(f"[{i:03d}/{len(st)}] {t} | {rec['status']} | {rec['official_side'] or 'NO_RESULT'}",flush=True);time.sleep(.05)

o=pd.DataFrame(out);settled=o[o.official_side.isin(['UP','DOWN'])].copy();usable=o[o.usable==True].copy();usable_settled=usable[usable.official_side.isin(['UP','DOWN'])].copy();proxy=settled[settled.final60_proxy.isin(['UP','DOWN'])].copy();proxy['agree']=proxy.final60_proxy==proxy.official_side
print('\n=== TARGETED OFFICIAL TRUTH COVERAGE ===');print('tape_contracts:',len(o));print('official_results:',len(settled),'/',len(o),'rate=',round(len(settled)/len(o),6) if len(o) else None);print('usable_contracts:',len(usable));print('usable_with_official_truth:',len(usable_settled),'/',len(usable),'rate=',round(len(usable_settled)/len(usable),6) if len(usable) else None);print('fetch_errors:',int((o.status=='FETCH_ERROR').sum()));print('not_finalized_or_no_result:',int((~o.official_side.isin(['UP','DOWN']) & (o.status!='FETCH_ERROR')).sum()));print('proxy_and_official_n:',len(proxy));print('final60_proxy_vs_official_agreement:',round(float(proxy.agree.mean()),6) if len(proxy) else None);print('proxy_disagreements:',','.join(proxy.loc[~proxy.agree,'ticker'].tolist()) if len(proxy) and (~proxy.agree).any() else 'NONE')
sufficient=len(usable_settled)>=80
print('\n=== REFRESH DECISION ===');print('OFFICIAL_TRUTH_REFRESH_SUFFICIENT_FOR_MODEL_STUDY='+str(sufficient));print('MODEL_LABEL_SOURCE=OFFICIAL_KALSHI_SETTLEMENT_ONLY');print('FINAL60_PROXY_ALLOWED_AS_MODEL_LABEL=False');print('NO_MODEL_WAS_FIT=True');print('PRODUCTION_CHANGED=False | SIGNAL_THRESHOLDS_CHANGED=False | ORDERS=False')
# Exact reproducibility payload for later commit/caching. Keep compact, deterministic ticker order.
records=[{k:r[k] for k in ['ticker','status','result','official_side','settlement_ts']} for r in sorted(out,key=lambda x:x['ticker'])]
print('TRUTH_JSON='+json.dumps(records,separators=(',',':'),sort_keys=True),flush=True)
print('NEXT_SAFE_STEP='+('CACHE_TRUTH_AND_FREEZE_DIRECT_BRTI_MODEL_METHODOLOGY' if sufficient else 'DO_NOT_FIT_MODEL'))
