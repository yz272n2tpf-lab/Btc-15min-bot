"""Offline reproduction of the existing fair engine's wall-clock support loss.

Extracts pure feature functions without importing the live bot or credentials.
No network, fitting, predictions, threshold changes or production mutations.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'bot_two_output_build_v4_13_profit_protection_shadow.py'
tree = ast.parse(source.read_text())
names = {'_fair_parse_contract_times','_fair_price_at_or_before','_fair_build_snapshot'}
nodes = [n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in names]
assert len(nodes) == len(names)
env = dict(pd=pd,np=np,re=re,ZoneInfo=ZoneInfo,
           _fair_months={m:i+1 for i,m in enumerate(['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'])})
exec(compile(ast.Module(body=nodes,type_ignores=[]),'<pure fair feature functions>','exec'),env)
cal = pd.read_csv(ROOT/'brti_calibration_results.csv')
btc = pd.read_csv(ROOT/'btc_35d_live_cache.csv',index_col='Datetime',parse_dates=True).sort_index()
rows=[]
for now in ['2026-09-02T12:26:30Z','2026-09-22T12:26:30Z','2026-09-23T12:26:30Z',
            '2026-09-24T12:26:30Z','2026-09-25T12:26:30Z','2026-09-26T12:26:30Z','2026-09-27T12:26:30Z']:
 cutoff=pd.Timestamp(now)-pd.Timedelta(days=35)
 frame=btc[btc.index>=cutoff]
 eligible=[]
 for row in cal.to_dict('records'):
  opened,closed=env['_fair_parse_contract_times'](row['ticker'])
  if frame.empty or closed < frame.index.min():continue
  snapshots=[]
  for elapsed in range(1,15):
   snap=env['_fair_build_snapshot'](frame,opened,float(row['target_brti']),_final_side=int(row['result']=='yes'),_elapsed=elapsed)
   if snap is not None:snapshots.append(snap)
  if len(snapshots)>=10:eligible.append((opened,row['ticker'],len(snapshots)))
 eligible.sort()
 n=len(eligible);a=int(n*.50);b=int(n*.70)
 report=dict(restart_utc=now,cutoff_utc=cutoff.isoformat(),eligible_contracts=n,
             fit_contracts=a,calibration_contracts=b-a,
             calibration_snapshots=sum(c for _,_,c in eligible[a:b]),
             existing_min20_calibration_gate_passes=b-a>=20,
             first_contract=eligible[0][1] if eligible else None,
             last_contract=eligible[-1][1] if eligible else None,
             eligible_identity_sha256=hashlib.sha256(json.dumps([t for _,t,_ in eligible]).encode()).hexdigest())
 rows.append(report);print(json.dumps(report),flush=True)
output=dict(purpose='deterministic support audit, not a fitted-model or accuracy comparison',
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            input_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ('brti_calibration_results.csv','btc_35d_live_cache.csv')},
            live_recent_bars_note='Recent September bars do not overlap August labeled contracts and cannot restore their missing historical support.',results=rows)
(ROOT/'completion_audit/training_support_expiry.json').write_text(json.dumps(output,indent=2)+'\n')
