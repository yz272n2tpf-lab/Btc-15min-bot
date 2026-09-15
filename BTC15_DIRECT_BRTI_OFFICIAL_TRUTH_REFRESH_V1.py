#!/usr/bin/env python3
import json,time,urllib.request
import pandas as pd
import numpy as np
TAPE='kalshi_direct_brti_parity_v1.csv';LIVE='https://external-api.kalshi.com/trade-api/v2/markets/';HIST='https://external-api.kalshi.com/trade-api/v2/historical/markets/'
def fetch(u):
 req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read().decode('utf-8'))
def market(t):
 errs=[]
 for b in (LIVE,HIST):
  try:
   p=fetch(b+t);m=p.get('market',p)
   if isinstance(m,dict) and m.get('ticker'):return m,None
  except Exception as e:errs.append(type(e).__name__+':'+str(e))
 return None,' | '.join(errs)
print('=== BTC15 DIRECT BRTI OFFICIAL TRUTH REFRESH V1 ===',flush=True);print('READ ONLY | PUBLIC GETS | NO MODEL FIT | NO ORDERS',flush=True)
df=pd.read_csv(TAPE);df['timestamp_utc']=pd.to_datetime(df.timestamp_utc,utc=True,errors='coerce');df['seconds_left']=pd.to_numeric(df.seconds_left,errors='coerce');st=[]
for c,g in df.groupby('contract',sort=False):
 g=g.sort_values('timestamp_utc');ts=g.timestamp_utc.dropna();d=ts.diff().dt.total_seconds().dropna();d=d[(d>0)&np.isfinite(d)];first=g.seconds_left.max() if g.seconds_left.notna().any() else np.nan;span=(ts.max()-ts.min()).total_seconds() if len(ts)>=2 else 0.;p95=float(d.quantile(.95)) if len(d) else np.nan;rr=float(g.direct_brti_ready.astype(str).str.lower().isin(['true','1','yes']).mean());usable=bool(pd.notna(first) and first>=600 and span>=300 and pd.notna(p95) and p95<=8 and rr>=.95);complete=g.final60_complete.astype(str).str.lower().isin(['true','1','yes']);proxy=''
 if complete.any():
  v=g.loc[complete,'final60_side'].dropna().astype(str).str.upper();proxy=v.iloc[-1] if len(v) and v.iloc[-1] in {'UP','DOWN'} else ''
 st.append((str(c),usable,proxy))
out=[]
for i,(t,usable,proxy) in enumerate(st,1):
 m,e=market(t)
 if m is None:r={'ticker':t,'status':'FETCH_ERROR','result':'','official_side':'','settlement_ts':'','usable':usable,'final60_proxy':proxy,'error':e or ''}
 else:
  result=str(m.get('result') or '').lower().strip();side='UP' if result=='yes' else ('DOWN' if result=='no' else '');r={'ticker':t,'status':str(m.get('status') or '').lower().strip(),'result':result,'official_side':side,'settlement_ts':str(m.get('settlement_ts') or ''),'usable':usable,'final60_proxy':proxy,'error':''}
 out.append(r);print(f"[{i:03d}/{len(st)}] {t} | {r['status']} | {r['official_side'] or 'NO_RESULT'}",flush=True);time.sleep(.05)
o=pd.DataFrame(out);settled=o[o.official_side.isin(['UP','DOWN'])];u=o[o.usable==True];us=u[u.official_side.isin(['UP','DOWN'])];p=settled[settled.final60_proxy.isin(['UP','DOWN'])].copy();p['agree']=p.final60_proxy==p.official_side
print('\n=== TARGETED OFFICIAL TRUTH COVERAGE ===');print('tape_contracts:',len(o));print('official_results:',len(settled),'/',len(o),'rate=',round(len(settled)/len(o),6));print('usable_contracts:',len(u));print('usable_with_official_truth:',len(us),'/',len(u),'rate=',round(len(us)/len(u),6) if len(u) else None);print('fetch_errors:',int((o.status=='FETCH_ERROR').sum()));print('not_finalized_or_no_result:',int((~o.official_side.isin(['UP','DOWN'])&(o.status!='FETCH_ERROR')).sum()));print('proxy_and_official_n:',len(p));print('final60_proxy_vs_official_agreement:',round(float(p.agree.mean()),6) if len(p) else None);print('proxy_disagreements:',','.join(p.loc[~p.agree,'ticker'].tolist()) if len(p) and (~p.agree).any() else 'NONE')
sufficient=len(us)>=80;print('\n=== REFRESH DECISION ===');print('OFFICIAL_TRUTH_REFRESH_SUFFICIENT_FOR_MODEL_STUDY='+str(sufficient));print('MODEL_LABEL_SOURCE=OFFICIAL_KALSHI_SETTLEMENT_ONLY');print('FINAL60_PROXY_ALLOWED_AS_MODEL_LABEL=False');print('NO_MODEL_WAS_FIT=True');print('PRODUCTION_CHANGED=False | SIGNAL_THRESHOLDS_CHANGED=False | ORDERS=False');records=[{k:r[k] for k in ['ticker','status','result','official_side','settlement_ts']} for r in sorted(out,key=lambda x:x['ticker'])];print('TRUTH_JSON='+json.dumps(records,separators=(',',':'),sort_keys=True),flush=True);print('NEXT_SAFE_STEP='+('CACHE_TRUTH_AND_FREEZE_DIRECT_BRTI_MODEL_METHODOLOGY' if sufficient else 'DO_NOT_FIT_MODEL'))
