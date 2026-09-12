#!/usr/bin/env python3
"""Offline guard for post-test integration diffs. No deployment actions."""
from __future__ import annotations
import sys, re

FORBIDDEN_PATTERNS=(
    r'place_order', r'create_order', r'submit_order', r'auto.?buy', r'auto.?sell',
    r'KALSHI_PRIVATE_KEY_B64\s*=', r'KALSHI_KEY_ID\s*=',
)
PROTECTED_MARKERS=(
    'Final Outcome', 'Early Opportunity', 'BRTI', '15-minute', 'signal-only'
)

def main(path):
    text=open(path,'r',encoding='utf-8',errors='replace').read()
    problems=[]
    for p in FORBIDDEN_PATTERNS:
        if re.search(p,text,re.I): problems.append('forbidden pattern: '+p)
    # This guard is intentionally conservative: integration diffs should mention
    # protection of all major subsystems in their commit/diff context.
    for marker in PROTECTED_MARKERS:
        if marker.lower() not in text.lower(): problems.append('missing protected-context marker: '+marker)
    if problems:
        print('V81 INTEGRATION DIFF GUARD: BLOCK')
        for x in problems: print('- '+x)
        raise SystemExit(2)
    print('V81 INTEGRATION DIFF GUARD: PASS')

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: python v81_integration_diff_guard.py <diff-or-review.txt>')
    main(sys.argv[1])
