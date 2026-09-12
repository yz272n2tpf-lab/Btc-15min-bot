#!/usr/bin/env python3
"""Offline V8.1 runtime-integrity check. Read-only. No orders."""
import re,sys
START='SCALP V8.1 START | LOCKED SURGICAL SUB30'
HB='V81 HEARTBEAT'
BAD=('UNIFIED SCALP V8 START','SUB30_FORWARD_TEST_PARKED','Traceback (most recent call last)')

def main(path):
    t=open(path,'r',encoding='utf-8',errors='replace').read()
    hb=len(re.findall(r'V81 HEARTBEAT',t))
    contracts=len(re.findall(r'V81 CONTRACT \|',t))
    results=len(re.findall(r'V81 RESULT \|',t))
    checks={
      'v81_start': START in t,
      'heartbeats_present': hb>=2,
      'no_plain_v8_start': 'UNIFIED SCALP V8 START' not in t,
      'not_parked': 'SUB30_FORWARD_TEST_PARKED' not in t,
      'no_traceback': 'Traceback (most recent call last)' not in t,
      'signal_only_banner': 'NO ORDERS' in t,
    }
    print('V8.1 RUNTIME INTEGRITY')
    for k,v in checks.items(): print(f'{k}={"PASS" if v else "FAIL"}')
    print(f'heartbeats={hb} contracts={contracts} results={results}')
    ok=all(checks.values())
    print('OVERALL=' + ('PASS' if ok else 'FAIL'))
    raise SystemExit(0 if ok else 2)

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: python v81_runtime_integrity_check.py <railway-log.txt>')
    main(sys.argv[1])
