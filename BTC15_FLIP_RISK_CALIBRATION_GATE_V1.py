#!/usr/bin/env python3
import runpy
import numpy as np
from sklearn.metrics import brier_score_loss

print('=== BTC15 FLIP RISK CALIBRATION GATE V1 ===', flush=True)
print('Frozen criteria only | historical OOS only | shadow-display authority at most | NO ORDERS', flush=True)
ns=runpy.run_path('kalshi_flip_probability_calibration_validation.py',run_name='__flip_gate_source__')
oos=ns['oos']; label_ok=ns['label_ok']
raw=float(brier_score_loss(oos['flip'],oos['raw_flip_prob']))
cal=float(brier_score_loss(oos['flip'],oos['flip_prob']))
block_ok=0
rows=[]
for b in (1,2,3):
 q=oos[oos['block']==b]; r=float(brier_score_loss(q['flip'],q['raw_flip_prob'])); c=float(brier_score_loss(q['flip'],q['flip_prob'])); ok=c<=r+1e-12; block_ok+=int(ok); rows.append((b,len(q),r,c,ok))
bins=[(0,.05),(.05,.10),(.10,.20),(.20,.30),(.30,.40),(.40,.50),(.50,.60),(.60,.70),(.70,.80),(.80,.90),(.90,.95),(.95,1.001)]
rel=[]
for lo,hi in bins:
 q=oos[(oos['flip_prob']>=lo)&(oos['flip_prob']<hi)]
 if len(q)>=20:
  a=float(q['flip'].mean()); s=float(q['flip_prob'].mean()); rel.append((lo,min(hi,1.0),len(q),a,s,abs(a-s)))
ece=sum(n*e for _,_,n,_,_,e in rel)/sum(n for _,_,n,_,_,e in rel)
max30=max(e for _,_,n,_,_,e in rel if n>=30)
monotonic=all(rel[i][3]<=rel[i+1][3]+1e-12 for i in range(len(rel)-1))
q90=oos[oos['stay_prob']>=.90]
stay90=float((q90['current_side']==q90['final_side']).mean())
minutes=set(int(x) for x in oos['elapsed'].unique())==set(range(1,15))
blocks=set(int(x) for x in oos['block'].unique())=={1,2,3}
finite=bool(np.isfinite(oos['raw_flip_prob']).all() and np.isfinite(oos['flip_prob']).all() and ((oos['flip_prob']>=0)&(oos['flip_prob']<=1)).all())
integrity=bool(label_ok.all() and minutes and blocks and finite)
passed=bool(integrity and cal<=raw+1e-12 and block_ok>=2 and monotonic and ece<=.05+1e-12 and max30<=.10+1e-12 and stay90>=.90-1e-12)
print('\n=== MACHINE-SCORED FROZEN GATE ===')
print(f'OOS snapshots: {len(oos)} | contracts: {oos.ticker.nunique()}')
print(f'Aggregate raw Brier: {raw:.6f}')
print(f'Aggregate calibrated Brier: {cal:.6f}')
print(f'Aggregate Brier tie/improve: {cal<=raw+1e-12}')
for b,n,r,c,ok in rows: print(f'Block {b} | n={n} | raw={r:.6f} | calibrated={c:.6f} | tie/improve={ok}')
print(f'Blocks tie/improve: {block_ok}/3 | required>=2 | pass={block_ok>=2}')
print('\n=== RELIABILITY GATE ===')
for lo,hi,n,a,s,e in rel: print(f'Flip {lo:.0%}-{hi:.0%} | n={n} | actual={a:.4f} | stated={s:.4f} | abs_error={e:.4f}')
print(f'Weighted absolute calibration error: {ece:.6f} | limit=0.050 | pass={ece<=.05+1e-12}')
print(f'Max bin abs error (n>=30): {max30:.6f} | limit=0.100 | pass={max30<=.10+1e-12}')
print(f'Actual flip frequency non-decreasing across populated bins: {monotonic}')
print('\n=== STAY >=90% GATE ===')
print(f'n={len(q90)} | actual stay={stay90:.6f} | avg stated stay={float(q90.stay_prob.mean()):.6f} | required>=0.90 | pass={stay90>=.90-1e-12}')
print('\n=== HARD INTEGRITY ===')
print(f'Settlement-label consistency: {bool(label_ok.all())}')
print(f'Minutes 1-14 represented: {minutes}')
print(f'Untouched blocks 1/2/3 represented: {blocks}')
print(f'Finite bounded probabilities: {finite}')
print('Future-data guard / chronological split / historical-only calibration: enforced by frozen source; source completed without exception')
print('\n=== DECISION ===')
print('FLIP_RISK_GATE_STATUS=' + ('HISTORICAL_GATE_PASS_SHADOW_ONLY' if passed else 'HISTORICAL_GATE_FAIL'))
print(f'PASS={passed}')
print('AUTHORITY=' + ('SHADOW_NUMERIC_DISPLAY_VALIDATION_ONLY' if passed else 'KEEP_NUMERIC_FLIP_RISK_HIDDEN'))
print('PRODUCTION_CHANGED=False | SIGNAL_THRESHOLDS_CHANGED=False | ORDERS=False')
raise SystemExit(0 if passed else 2)
