#!/usr/bin/env python3
"""Targeted runtime source diagnostics for BTC15 dashboard internals.

Prints focused excerpts for final-state mapping and chart rendering, then launches
existing UI stability wrapper. No trading/scoring logic changes.
"""
from pathlib import Path
import os,re,sys

TERMS=[
    "function renderMainChart",
    "renderMainChart(",
    "finalAction",
    "finalActionSub",
    "finalConfidence",
    "finalSide",
    "finalReason",
    "setText('final",
    'setText("final',
    "latestState",
    "clockTrusted",
    "price-block",
    "static-chart",
]

def excerpt(text,term,radius=1200):
    i=text.lower().find(term.lower())
    if i<0:return None
    a=max(0,i-radius); b=min(len(text),i+len(term)+radius)
    return re.sub(r"\s+"," ",text[a:b])

def main():
    import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer
    d=installer.install(); html=d/'BTC_Kalshi_App_Live_v13.html'
    print('DASH SOURCE DIAG V2 | begin')
    if html.exists():
        text=html.read_text(encoding='utf-8',errors='replace')
        for term in TERMS:
            hit=excerpt(text,term)
            print(f'DASH SOURCE DIAG V2 | TERM={term} | {hit if hit else "NOT_FOUND"}')
    print('DASH SOURCE DIAG V2 | end')
    target=Path(__file__).with_name('BTC15_DASHBOARD_UI_STABILITY_PATCH_V1.py')
    os.execv(sys.executable,[sys.executable,'-u',str(target),*sys.argv[1:]])

if __name__=='__main__': raise SystemExit(main())
