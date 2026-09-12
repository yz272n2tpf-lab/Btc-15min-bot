#!/usr/bin/env python3
"""Offline release gate for V8.1 scalp integration. SIGNAL ONLY. NO ORDERS."""
from __future__ import annotations
import json, sys

REQUIRED_NON_NEGOTIABLES={
    'NO_ORDERS','preserve_BRTI_transport','preserve_Kalshi_15m_alignment',
    'preserve_Final_Outcome_logic','preserve_Early_Opportunity_logic'
}
ALLOWED_DECISIONS={'GRADUATE','GRADUATE_CAUTIOUSLY','GRADUATE_PROTECT','HOLD','TIGHTEN','REJECT','REJECTED_BY_DESIGN'}

def fail(msg):
    print('RELEASE_GATE=FAIL | '+msg)
    raise SystemExit(2)

def main(path):
    d=json.load(open(path,'r',encoding='utf-8'))
    if not d.get('runtime_integrity_required'): fail('runtime integrity not required')
    if not d.get('brti_health_required'): fail('BRTI health not required')
    if not d.get('signal_only_required'): fail('signal-only guard missing')
    if not REQUIRED_NON_NEGOTIABLES.issubset(set(d.get('non_negotiables',[]))): fail('non-negotiables incomplete')
    lanes=d.get('lanes',{})
    for lane in ('3-7c','7-15c','15-30c','30-45c'):
        if lane not in lanes: fail('missing lane '+lane)
        dec=lanes[lane].get('decision','PENDING')
        if dec=='PENDING': fail('lane decision still pending: '+lane)
        if dec not in ALLOWED_DECISIONS: fail('unknown decision for '+lane+': '+dec)
        enabled=bool(lanes[lane].get('integration_enabled'))
        if enabled and not dec.startswith('GRADUATE'): fail('non-graduated lane enabled: '+lane)
    if lanes['7-15c'].get('integration_enabled'): fail('7-15c must remain disabled under V8.1 design')
    print('RELEASE_GATE=PASS | lane decisions complete | signal-only guard intact')

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: python v81_release_gate.py v81_lane_decision.json')
    main(sys.argv[1])
