#!/usr/bin/env python3
import json,math,re,statistics
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import requests
URL='https://btc-15min-bot-production.up.railway.app/dashboard_state.json'
features=['elapsed','remaining','current_side','dist_target','abs_dist_target','dist_target_pct','move_from_start','move_from_start_pct','move1','move2','move3','move5','support1','support2','support3','support5','range5','vol5','dist_per_min_remaining','dist_over_range5']
months={m:i+1 for i,m in enumerate(['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'])}
def f(v):
 try:
  x=float(v);return x if math.isfinite(x) else None
 except:return None
def ts(v):
 try:
  d=datetime.fromisoformat(str(v).replace('Z','+00:00'));return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
 except:return None
def contract_times(t):
 m=re.search(r'KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-',str(t).upper())
 if not m:return None,None
 yy,mo,dd,hh,mm=m.groups();close=datetime(2000+int(yy),months[mo],int(dd),int(hh),int(mm),tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc);return close-timedelta(minutes=15),close
print('=== BTC15_FLIP_RISK_LIVE_FEATURE_PARITY_AUDIT_V1 ===',flush=True)
r=requests.get(URL,timeout=15,headers={'Cache-Control':'no-cache'});print('Production state HTTP:',r.status_code,flush=True);r.raise_for_status();d=r.json()
contract=str(d.get('contract') or '');m=d.get('market') or {};timer=d.get('timer') or {};chart=d.get('chart') or {};points=chart.get('points') if isinstance(chart.get('points'),list) else []
left=f(timer.get('seconds_left'));target=f(m.get('target'));brti=f(m.get('brti_value'));start,_=contract_times(contract)
parsed=[]
for p in points:
 if isinstance(p,dict):
  t=ts(p.get('t'));v=f(p.get('brti'))
  if t and v is not None:parsed.append((t,v,p))
parsed.sort(key=lambda x:x[0]);span=(parsed[-1][0]-parsed[0][0]).total_seconds() if parsed else 0
keys=set().union(*(p.keys() for p in points if isinstance(p,dict))) if points else set()
print('Contract:',contract);print('Historical source: Coinbase 1m OHLCV');print('Live authority: direct BRTI');print('seconds_left:',left,'target:',target,'brti:',brti);print('chart count:',len(points),'keys:',sorted(keys));print('chart span sec:',span)
if parsed and start:print('earliest point vs canonical start sec:',(parsed[0][0]-start).total_seconds())
status={}
for n in features:
 if n in {'elapsed','remaining'}:status[n]=(left is not None,'timer semantics available')
 elif n in {'current_side','dist_target','abs_dist_target','dist_target_pct','dist_per_min_remaining'}:status[n]=(target is not None and brti is not None,'derivable from live direct BRTI + target')
 elif n in {'move_from_start','move_from_start_pct','move1','move2','move3','move5','support1','support2','support3','support5'}:status[n]=(False,'source mismatch: historical Coinbase Close vs live direct BRTI')
 elif n=='range5':status[n]=(False,'historical Coinbase 1m High-Low semantics not present live')
 elif n=='vol5':status[n]=(False,'historical Coinbase 1m Close pct-change volatility != live BRTI cadence')
 elif n=='dist_over_range5':status[n]=(False,'depends on non-parity range5')
for n in features:print(n+':',('EXACT' if status[n][0] else 'NOT_EXACT'),'|',status[n][1])
exact=sum(v[0] for v in status.values());print('exact_features=%d/%d | not_exact=%d'%(exact,len(features),len(features)-exact));print('LIVE_FEATURE_PARITY='+('PASS' if exact==len(features) else 'FAIL'));print('NUMERIC_FLIP_RISK_LIVE_ALLOWED=False');print('NEXT_SAFE_STEP='+('FREEZE_FRESH_FORWARD_SHADOW_SAMPLE' if exact==len(features) else 'RETRAIN_AND_CALIBRATE_ON_DIRECT_BRTI_ALIGNED_FEATURES'));print('PRODUCTION_CHANGED=False | SIGNAL_THRESHOLDS_CHANGED=False | ORDERS=False');print('STATE_KEYS='+json.dumps(sorted(d.keys())))
