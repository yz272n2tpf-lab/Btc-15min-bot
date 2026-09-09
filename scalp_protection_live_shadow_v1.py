#!/usr/bin/env python3
"""Live V6 scalp protection shadow V1.

Research-only / signal-only. NO ORDERS.

Runs independently beside scalp_lead_shadow_v6.py. It reuses the tested V5 market
plumbing, applies the same V6 qualification rules, records each qualified trade
path for up to 3 minutes, and scores HOLD / WATCH / TAKE_PROFIT / EXIT without
changing V6 entry behavior.
"""

from collections import defaultdict, deque
from scalp_trade_path_shadow_v1 import PathPoint, score_path, compact_report

# Reuse V5 plumbing without entering its main loop.
_src = open('scalp_lead_shadow_v5.py', 'r', encoding='utf-8').read()
_prefix = _src.split("print('SCALP LEAD SHADOW V5 START", 1)[0]
exec(compile(_prefix, 'scalp_lead_shadow_v5.py', 'exec'), globals())

# Match V6 research rules exactly. These are shadow research thresholds only.
V6_MIN_ASK = 0.07
V6_PREFERRED_MAX = 0.30
V6_MAX_ASK = 0.45
V6_CONFIRM_WINDOW = 4.0
V6_CONFIRM_COUNT = 2
V6_HIGH_BTC5 = 20.0
V6_HIGH_BTC15 = 25.0
V6_HIGH_BRTI5 = 15.0
V6_HIGH_BRTI15 = 5.0
V6_HIGH_ACCEL = 10.0
V6_HIGH_BTC30 = 0.0
HORIZON = 180.0

# Same resilient BRTI transport behavior as V6; never substitutes stale data.
def brti():
    for attempt in range(3):
        try:
            r=requests.get(EXT+BRTI_PATH, headers=hdr('GET', BRTI_PATH), params={'id':'BRTI','maxResolution':'PER_SECOND'}, timeout=1.5)
            r.raise_for_status()
            v=brti_value(r.json())
            if v is not None:
                return v
        except Exception:
            pass
        if attempt < 2:
            time.sleep(0.08)
    return None

proto = defaultdict(deque)
active = []
last_signal = {}
contract_stats = defaultdict(lambda: {'started':0,'done':0,'burst':0,'expansion':0,'noexp':0,'take':0,'exit':0,'max_gain':0.0,'giveback':0.0,'upside_left':0.0})
last_ticker = None


def quality(row, side, f):
    ask = row[side.lower() + '_ask']
    if ask is None or ask <= 0.02 or ask < V6_MIN_ASK or ask > V6_MAX_ASK:
        return False, 'PRICE_REJECT'
    if f.get('brti5') is None or f.get('brti15') is None:
        return False, 'DATA_DEGRADED'
    if not f.get('v4') or not f.get('structure_ok'):
        return False, 'BASE_NOT_READY'
    if ask <= V6_PREFERRED_MAX:
        return True, 'PREFERRED_7_30C'
    strong = (
        f['btc5'] >= V6_HIGH_BTC5 and
        f['btc15'] >= V6_HIGH_BTC15 and
        f['brti5'] >= V6_HIGH_BRTI5 and
        f['brti15'] >= V6_HIGH_BRTI15 and
        f['accel'] >= V6_HIGH_ACCEL and
        f['btc30'] is not None and f['btc30'] >= V6_HIGH_BTC30
    )
    return strong, ('HIGH_PRICE_STRONG' if strong else 'HIGH_PRICE_REJECT')


def confirmed(row, side, f):
    ok, zone = quality(row, side, f)
    k = (row['ticker'], side)
    q = proto[k]
    now = row['ts']
    while q and q[0] < now - V6_CONFIRM_WINDOW:
        q.popleft()
    if not ok:
        q.clear()
        return False, zone
    q.append(now)
    return len(q) >= V6_CONFIRM_COUNT, zone


def start_trade(row, side, f, zone):
    k=(row['ticker'], side)
    if row['ts'] - last_signal.get(k, 0) < 20:
        return
    last_signal[k] = row['ts']
    p=side.lower(); ask=row[p+'_ask']; bid=row[p+'_bid']
    if ask is None or bid is None:
        return
    e={
        'ticker':row['ticker'],'side':side,'zone':zone,'entry':ask,'ts':row['ts'],
        'points':[PathPoint(0.0,row['left'],bid,f.get('btc5'),f.get('btc15'),f.get('brti5'),f.get('brti15'))]
    }
    active.append(e)
    contract_stats[row['ticker']]['started'] += 1
    print('SCALP_PROTECT START | %s | %s | zone %s | entry %.3f | left %.0fs' % (row['ticker'],side,zone,ask,row['left']), flush=True)


def finalize(e, why):
    pts=e['points']
    if not pts:
        return
    r=score_path(e['entry'], pts)
    s=contract_stats[e['ticker']]
    s['done'] += 1
    s['max_gain'] += r.max_gain
    if r.path_style == 'BURST': s['burst'] += 1
    elif r.path_style == 'EXPANSION': s['expansion'] += 1
    else: s['noexp'] += 1
    if r.first_take_profit is not None: s['take'] += 1
    if r.first_exit is not None: s['exit'] += 1
    if r.giveback_from_peak_at_decision is not None: s['giveback'] += r.giveback_from_peak_at_decision
    if r.remaining_upside_after_decision is not None: s['upside_left'] += r.remaining_upside_after_decision
    print('SCALP_PROTECT RESULT | %s | %s | %s | %s | %s' % (e['ticker'],e['side'],e['zone'],why,compact_report(r)), flush=True)


def update_active(row):
    done=[]
    for e in active:
        if e['ticker'] != row['ticker']:
            done.append((e,'ROLLOVER')); continue
        p=e['side'].lower(); bid=row[p+'_bid']
        if bid is None:
            continue
        f=features(row,e['side'])
        if f:
            e['points'].append(PathPoint(
                row['ts']-e['ts'],row['left'],bid,
                f.get('btc5'),f.get('btc15'),f.get('brti5'),f.get('brti15')
            ))
        if row['ts']-e['ts'] >= HORIZON or row['left'] <= 0:
            done.append((e,'HORIZON'))
    for e,why in done:
        if e in active: active.remove(e)
        finalize(e,why)


def print_contract_summary(ticker):
    s=contract_stats[ticker]
    n=s['done']
    if not s['started']:
        print('SCALP_PROTECT SUMMARY | %s | started=0' % ticker, flush=True); return
    avg_gain=s['max_gain']/n if n else 0.0
    avg_give=s['giveback']/max(1,s['take']+s['exit'])
    avg_left=s['upside_left']/max(1,s['take']+s['exit'])
    print('SCALP_PROTECT SUMMARY | %s | started=%d done=%d burst=%d expansion=%d noexp=%d take=%d exit=%d avgMaxGain=%+.3f avgGiveback=%+.3f avgUpsideLeft=%+.3f' % (
        ticker,s['started'],n,s['burst'],s['expansion'],s['noexp'],s['take'],s['exit'],avg_gain,avg_give,avg_left), flush=True)


print('SCALP PROTECTION LIVE SHADOW V1 START | V6-matched entries + HOLD/WATCH/TAKE_PROFIT/EXIT path scoring | NO ORDERS', flush=True)
while True:
    t=time.time()
    try:
        row=snap()
        if row:
            if last_ticker is not None and row['ticker'] != last_ticker:
                print_contract_summary(last_ticker)
            last_ticker=row['ticker']
            hist.append(row)
            while hist and hist[0]['ts'] < row['ts'] - KEEP:
                hist.popleft()
            update_active(row)
            for side in ('UP','DOWN'):
                f=features(row,side)
                if not f or not f['broad']:
                    continue
                ok,zone=confirmed(row,side,f)
                if ok:
                    start_trade(row,side,f,zone)
    except Exception as exc:
        print('SCALP_PROTECT WARNING | %s: %s' % (type(exc).__name__,exc), flush=True)
    time.sleep(max(.05, POLL-(time.time()-t)))
