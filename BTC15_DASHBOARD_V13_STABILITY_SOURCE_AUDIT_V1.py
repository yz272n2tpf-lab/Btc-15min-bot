#!/usr/bin/env python3
"""Inspect exact V13 HTML source around presentation-stability anchors.
PRESENTATION AUDIT ONLY | NO ORDERS
"""
from __future__ import annotations
import re
from pathlib import Path
import BTC15_DASHBOARD_COMBINED_SCALP_UI_V13 as v13

ANCHORS=(
    'id="btcPrice"','btcPrice','id="finalCard"','id="finalReason"',
    'class="card early-card"','id="earlyFlow"','class="timer-card"',
    'id="timerRemaining"','id="timerEnd"','id="scalpCard"',
)
CSS_SELECTORS=(r'#btcPrice\b[^\{]*\{[^\}]*\}',r'\.price-block\b[^\{]*\{[^\}]*\}',r'\.final-card\b[^\{]*\{[^\}]*\}',r'\.early-card\b[^\{]*\{[^\}]*\}',r'\.timer-card\b[^\{]*\{[^\}]*\}',r'\.reason-line\b[^\{]*\{[^\}]*\}')

def compact(s:str)->str:
    return re.sub(r'\s+',' ',s).strip()

def main()->int:
    p:Path=v13.build_dashboard(); html=p.read_text(encoding='utf-8',errors='replace')
    print('BTC15 V13 STABILITY SOURCE AUDIT | EXACT GENERATED HTML | NO ORDERS')
    for anchor in ANCHORS:
        hits=[m.start() for m in re.finditer(re.escape(anchor),html)]
        print(f'ANCHOR COUNT | {anchor} | {len(hits)}')
        for i in hits[:8]:
            print(f'ANCHOR SRC | {anchor} | '+compact(html[max(0,i-420):min(len(html),i+700)])[:1200])
    for pattern in CSS_SELECTORS:
        rows=re.findall(pattern,html,re.I|re.S)
        print(f'CSS RULE COUNT | {pattern} | {len(rows)}')
        for row in rows[:8]: print('CSS RULE | '+compact(row)[:1200])
    assert html.count('id="btcPrice"')==1
    assert html.count('id="finalCard"')==1
    assert html.count('id="finalReason"')==1
    assert html.count('id="timerRemaining"')==1
    assert html.count('id="timerEnd"')==1
    assert html.count('id="scalpCard"')==1
    assert html.count('class="card early-card"')==1
    assert 'SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS' in html
    assert 'flip_risk_percent' not in html
    return 0
if __name__=='__main__': raise SystemExit(main())
