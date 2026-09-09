#!/usr/bin/env python3
"""V6 research-only scalp collector. Signal-only. NO ORDERS.

Builds on V5 but adds:
- preferred opportunity zone 0.07-0.30
- stronger proof for 0.31-0.45 entries
- clean-data requirement for V6 qualification (BRTI 5s + 15s present)
- rejection of <=0.02 near-dead contracts
- stronger 30s structure guard on higher-priced entries
- automatic V5-vs-V6 outcome scoring and per-contract summaries

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
score = defaultdict(lambda: {'n':0,'hit5':0,'hit10':0,'fast10':0,'gain_sum':0.0,'adverse_sum':0.0})
last_ticker = None

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
    pending.append({'ticker':row['ticker'],'side':side,'grade':grade,'zone':zone,'ts':row['ts'],'entry':ask,'max':bid,'min':bid,'x5':None,'x10':None,'ask5_ts':None})
    def fmt(v): return 'N/A' if v is None else ('%+.2f' % v)
    print('LEAD_V6 CANDIDATE | %s | %s | %s | zone %s | ask %.3f | btc5 %+.2f | btc15 %+.2f | btc30 %s | accel %+.2f | brti5 %s | brti15 %s | ask5 %+.3f | ask15 %+.3f | left %.0fs' % (
        grade,row['ticker'],side,zone,ask,f['btc5'],f['btc15'],fmt(f['btc30']),f['accel'],fmt(f['brti5']),fmt(f['brti15']),f['ask5'],f['ask15'],row['left']), flush=True)

def score_result(e, gain, adverse, t5, t10):
    s = score[e['grade']]
    s['n'] += 1
    if t5 is not None: s['hit5'] += 1
    if t10 is not None:
        s['hit10'] += 1
        if t10 <= 30.0: s['fast10'] += 1
    s['gain_sum'] += gain
    s['adverse_sum'] += adverse

def print_score(prefix='LEAD_V6 SCORE'):
    for grade in ('V5_BASELINE','V6_QUALIFIED'):
        s = score[grade]
        if not s['n']:
            print('%s | %s | n 0' % (prefix, grade), flush=True)
            continue
        n = s['n']
        print('%s | %s | n %d | hit5 %.1f%% | hit10 %.1f%% | fast10<=30s %.1f%% | avg_gain %+.3f | avg_adverse %+.3f' % (
            prefix, grade, n, 100*s['hit5']/n, 100*s['hit10']/n, 100*s['fast10']/n,
            s['gain_sum']/n, s['adverse_sum']/n), flush=True)

def resolve_v6(row):
    done=[]
    for e in pending:
        if e['ticker'] != row['ticker']:
            done.append(e); continue
        p=e['side'].lower(); bid=row[p+'_bid']; ask=row[p+'_ask']
        if bid is not None:
            e['max']=max(e['max'],bid); e['min']=min(e['min'],bid); g=bid-e['entry']
            if g>=.05 and e['x5'] is None: e['x5']=row['ts']
            if g>=.10 and e['x10'] is None: e['x10']=row['ts']
        if ask is not None and ask-e['entry']>=.05 and e['ask5_ts'] is None: e['ask5_ts']=row['ts']
        if row['ts']-e['ts']>=HORIZON or row['left']<=0: done.append(e)
    for e in done:
        if e in pending: pending.remove(e)
        t5=None if e['x5'] is None else round(e['x5']-e['ts'],1)
        t10=None if e['x10'] is None else round(e['x10']-e['ts'],1)
        ar=None if e['ask5_ts'] is None else round(e['ask5_ts']-e['ts'],1)
        gain=e['max']-e['entry']; adverse=e['min']-e['entry']
        score_result(e,gain,adverse,t5,t10)
        print('LEAD_V6 RESULT | %s | %s | %s | zone %s | entry %.3f | max_exec_gain %+.3f | adverse %+.3f | hit10 %s | to_exec+5c %s | to_exec+10c %s | kalshi_reprice+5c %s' % (
            e['grade'],e['ticker'],e['side'],e.get('zone','N/A'),e['entry'],gain,adverse,e['x10'] is not None,t5,t10,ar), flush=True)

print('SCALP LEAD SHADOW V6 START | V5 baseline + price-zone/data-quality filter + autoscore | NO ORDERS', flush=True)
while True:
    t = time.time()
    try:
        row = snap()
        if row:
            if last_ticker is not None and row['ticker'] != last_ticker:
                print_score('LEAD_V6 CONTRACT_SUMMARY')
            last_ticker = row['ticker']
            hist.append(row)
            while hist and hist[0]['ts'] < row['ts'] - KEEP:
                hist.popleft()
            resolve_v6(row)
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
