#!/usr/bin/env python3
"""Targeted runtime diagnostics for dashboard state mapping and scalp/chart rendering.
No trading/scoring/order logic changes. Diagnostic branch only.
"""
from pathlib import Path
import os,re,sys

TERMS=[
    "function applyState",
    "function renderMainChart",
    "setText('finalAction'",
    "setText('finalConfidence'",
    "setText('finalSide'",
    "setText('finalReason'",
    "setText('scalp",
    "scalpAction",
    "scalpSide",
    "scalpEntry",
    "scalpExit",
    "SCALP OPPORTUNITY",
    "SCALP",
    "d.scalp",
    "earlyAction",
    "EARLY OPPORTUNITY",
    "livePrice",
    "brti_value",
    "price-block",
    "lastChartSignature",
    "svg.textContent=''",
]

def excerpt(text,term,radius=2200):
    i=text.find(term)
    if i<0:
        i=text.lower().find(term.lower())
    if i<0:return None
    a=max(0,i-radius);b=min(len(text),i+len(term)+radius)
    return re.sub(r"\s+"," ",text[a:b])

def main():
    import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer
    d=installer.install(); html=d/'BTC_Kalshi_App_Live_v13.html'
    text=html.read_text(encoding='utf-8',errors='replace')
    print('DASH SOURCE DIAG V3 | begin')
    for term in TERMS:
        hit=excerpt(text,term)
        print(f"DASH SOURCE DIAG V3 | TERM={term} | {hit if hit else 'NOT_FOUND'}")
    print('DASH SOURCE DIAG V3 | end')
    target=Path(__file__).with_name('BTC15_DASHBOARD_UI_STABILITY_PATCH_V1.py')
    os.execv(sys.executable,[sys.executable,'-u',str(target),*sys.argv[1:]])

if __name__=='__main__': raise SystemExit(main())
