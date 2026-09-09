#!/usr/bin/env python3
"""Research-only BRTI health diagnostic. NO ORDERS.

Purpose:
Measure how often the live BRTI endpoint is available, how long degraded streaks last,
and whether transport retries recover a clean sample. This is diagnostic only and does
not change production or V6 qualification logic.
"""

import time
from collections import deque

# Reuse authenticated research plumbing without starting V5 main loop.
_src = open('scalp_lead_shadow_v5.py','r',encoding='utf-8').read()
_prefix = _src.split("print('SCALP LEAD SHADOW V5 START",1)[0]
exec(compile(_prefix,'scalp_lead_shadow_v5.py','exec'), globals())

POLL = 2.0
WINDOW = 300.0
samples = deque()
last_state = None
degraded_start = None
recovered_streaks = []


def fetch_once():
    try:
        r=requests.get(EXT+BRTI_PATH,headers=hdr('GET',BRTI_PATH),params={'id':'BRTI','maxResolution':'PER_SECOND'},timeout=1.5)
        r.raise_for_status()
        return brti_value(r.json())
    except Exception:
        return None


def fetch_with_retries():
    attempts=0
    for i in range(3):
        attempts += 1
        v=fetch_once()
        if v is not None:
            return v, attempts
        if i<2:
            time.sleep(0.08)
    return None, attempts

print('BRTI HEALTH SHADOW V1 START | diagnostic only | NO ORDERS', flush=True)
while True:
    t=time.time()
    v, attempts = fetch_with_retries()
    ok = v is not None
    samples.append((t, ok, attempts))
    while samples and samples[0][0] < t-WINDOW:
        samples.popleft()

    if ok and last_state is False and degraded_start is not None:
        streak=t-degraded_start
        recovered_streaks.append(streak)
        print('BRTI_RECOVERED | degraded_for=%.1fs | value=%.2f | attempts=%d' % (streak,v,attempts), flush=True)
        degraded_start=None
    elif not ok and last_state is not False:
        degraded_start=t
        print('BRTI_DEGRADED_START', flush=True)

    last_state=ok
    total=len(samples)
    good=sum(1 for _,x,_ in samples if x)
    retry_recovered=sum(1 for _,x,a in samples if x and a>1)
    if int(t) % 30 == 0 and total:
        pct=100.0*good/total
        print('BRTI_HEALTH | 5m_samples=%d | available=%.1f%% | retry_recovered=%d | current=%s | attempts=%d' % (
            total,pct,retry_recovered,'OK' if ok else 'DEGRADED',attempts), flush=True)

    time.sleep(max(0.05, POLL-(time.time()-t)))
