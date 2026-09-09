#!/usr/bin/env python3
"""V6 research-only scalp collector. Signal-only. NO ORDERS.

Builds on V5 but adds:
- preferred opportunity zone 0.07-0.30
- stronger proof for 0.31-0.45 entries
- clean-data requirement for V6 qualification (BRTI 5s + 15s present)
- rejection of <=0.02 near-dead contracts
- stronger 30s structure guard on higher-priced entries

V5 remains the baseline. Production is untouched.
"""

# Reuse the tested V5 plumbing without starting its main loop.
_src = open('scalp_lead_shadow_v5.py', 'r', encoding='utf-8').read()
_prefix = _src.split("print('SCALP LEAD SHADOW V5 START", 1)[0]
exec(compile(_prefix, 'scalp_lead_shadow_v5.py', 'exec'), globals())

V6_MIN_ASK = 0.07
V6_PREFERRED_MAX = 0.30
V6_MAX_ASK = 0.45
V6_CONFIRM_WINDOW = 4.0
V6_CONFIRM_COUNT = 2

# Extra proof required above the preferred 7c-30c opportunity zone.
V6_HIGH_BTC5 = 20.0
V6_HIGH_BTC15 = 25.0
V6_HIGH_BRTI5 = 15.0
V6_HIGH_BRTI15 = 5.0
V6_HIGH_ACCEL = 10.0
V6_HIGH_BTC30 = 0.0

v6_proto = defaultdict(deque)

def v6_quality(row, side, f):
    ask = row[side.lower() + '_ask']
    if ask is None or ask <= 0.02 or ask < V6_MIN_ASK or ask > V6_MAX_ASK:
        return False, 'PRICE_REJECT'

    # V6 only qualifies on clean BRTI confirmation. Missing data can still be
    # observed by V5 baseline, but it cannot become a V6-qualified signal.
    if f.get('brti5') is None or f.get('brti15') is None:
        return False, 'DATA_DEGRADED'

    if not f.get('v4') or not f.get('structure_ok'):
        return False, 'BASE_NOT_READY'

    if ask <= V6_PREFERRED_MAX:
        return True, 'PREFERRED_7_30C'

    strong_high = (
        f['btc5'] >= V6_HIGH_BTC5 and
        f['btc15'] >= V6_HIGH_BTC15 and
        f['brti5'] >= V6_HIGH_BRTI5 and
        f['brti15'] >= V6_HIGH_BRTI15 and
        f['accel'] >= V6_HIGH_ACCEL and
        f['btc30'] is not None and f['btc30'] >= V6_HIGH_BTC30
    )
    return strong_high, ('HIGH_PRICE_STRONG' if strong_high else 'HIGH_PRICE_REJECT')

def v6_confirm(row, side, f):
    ok, zone = v6_quality(row, side, f)
    k = (row['ticker'], side)
    q = v6_proto[k]
    now = row['ts']
    while q and q[0] < now - V6_CONFIRM_WINDOW:
        q.popleft()

    # Never let stale good confirmations survive a degraded/rejected sample.
    # This guarantees the current sample itself must be valid for qualification.
    if not ok:
        q.clear()
        return False, zone

    q.append(now)
    return len(q) >= V6_CONFIRM_COUNT, zone

def add_v6(row, side, f, grade, zone):
    k = (row['ticker'], side, grade)
    if row['ts'] - last.get(k, 0) < 20:
        return
    last[k] = row['ts']
    p = side.lower(); ask = row[p + '_ask']; bid = row[p + '_bid']
    pending.append({'ticker':row['ticker'],'side':side,'grade':grade,'ts':row['ts'],'entry':ask,'max':bid,'min':bid,'x5':None,'x10':None,'ask5_ts':None})
    def fmt(v): return 'N/A' if v is None else ('%+.2f' % v)
    print('LEAD_V6 CANDIDATE | %s | %s | %s | zone %s | ask %.3f | btc5 %+.2f | btc15 %+.2f | btc30 %s | accel %+.2f | brti5 %s | brti15 %s | ask5 %+.3f | ask15 %+.3f | left %.0fs' % (
        grade,row['ticker'],side,zone,ask,f['btc5'],f['btc15'],fmt(f['btc30']),f['accel'],fmt(f['brti5']),fmt(f['brti15']),f['ask5'],f['ask15'],row['left']), flush=True)

print('SCALP LEAD SHADOW V6 START | V5 baseline + price-zone/data-quality filter | NO ORDERS', flush=True)
while True:
    t = time.time()
    try:
        row = snap()
        if row:
            hist.append(row)
            while hist and hist[0]['ts'] < row['ts'] - KEEP:
                hist.popleft()
            resolve(row)
            for side in ('UP','DOWN'):
                f = features(row, side)
                if not f or not f['broad']:
                    continue

                # Preserve V5 qualification as the direct baseline.
                if proto_confirm(row, side, f):
                    add_v6(row, side, f, 'V5_BASELINE', 'V5_RULES')

                ok, zone = v6_confirm(row, side, f)
                if ok:
                    add_v6(row, side, f, 'V6_QUALIFIED', zone)

            if int(row['ts']) % 30 == 0:
                bv = 'N/A' if row['brti'] is None else ('%.2f' % row['brti'])
                print('LEAD_V6 HEARTBEAT | %s | %.2fm | BTC %.2f | BRTI %s | UP %.3f | DOWN %.3f | pending %d' % (
                    row['ticker'],row['left']/60,row['btc'],bv,row['up_ask'],row['down_ask'],len(pending)), flush=True)
    except Exception as e:
        print('LEAD_V6 WARNING | %s: %s' % (type(e).__name__, e), flush=True)
    time.sleep(max(.05, POLL - (time.time() - t)))
