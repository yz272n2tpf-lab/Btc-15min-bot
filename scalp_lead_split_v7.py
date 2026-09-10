#!/usr/bin/env python3
"""V7 split scalp/reversal research collector. Signal-only. NO ORDERS.

Purpose
-------
Freeze V6 as the benchmark and test the final two-lane architecture:
  1) MOMENTUM_EXPANSION: preserves the proven V6 continuation rules.
  2) ULTRA_CHEAP_REVERSAL: separately studies 3-7c reversals instead of
     blindly lowering the V6 floor.

Both lanes share:
- fresh-primary BRTI only for qualification
- resilient BRTI transport retries/diagnostics
- 3-minute path scoring (burst + expansion)
- common result format for later HOLD/WATCH/TAKE_PROFIT/EXIT work

Production is untouched. This file never places orders.
"""

# Reuse stable V5 market/BTC/Kalshi feature plumbing without starting V5 loop.
_src = open('scalp_lead_shadow_v5.py', 'r', encoding='utf-8').read()
_prefix = _src.split("print('SCALP LEAD SHADOW V5 START", 1)[0]
exec(compile(_prefix, 'scalp_lead_shadow_v5.py', 'exec'), globals())

from brti_resilience_shadow_v2 import BrtiResilienceGuard, qualification_value

HORIZON = 180

# ---------------------------------------------------------------------------
# BRTI transport hardening. IMPORTANT: only fresh primary BRTI is returned to
# features(); diagnostic cache/verifier values can never qualify a signal.
# ---------------------------------------------------------------------------
_brti_guard = BrtiResilienceGuard(retries=4, backoff_s=(0.05, 0.10, 0.20), diagnostic_cache_ttl_s=3.0)

def _primary_brti_once():
    r = requests.get(
        EXT + BRTI_PATH,
        headers=hdr('GET', BRTI_PATH),
        params={'id':'BRTI','maxResolution':'PER_SECOND'},
        timeout=1.5,
    )
    r.raise_for_status()
    return brti_value(r.json())

def brti():
    sample = _brti_guard.fetch(_primary_brti_once)
    return qualification_value(sample)

# ---------------------------------------------------------------------------
# Lane A: preserve V6 momentum/expansion qualification exactly.
# ---------------------------------------------------------------------------
MOM_MIN_ASK = 0.07
MOM_PREF_MAX = 0.30
MOM_MAX_ASK = 0.45
MOM_HIGH_BTC5 = 20.0
MOM_HIGH_BTC15 = 25.0
MOM_HIGH_BRTI5 = 15.0
MOM_HIGH_BRTI15 = 5.0
MOM_HIGH_ACCEL = 10.0
MOM_HIGH_BTC30 = 0.0

# ---------------------------------------------------------------------------
# Lane B: experimental ultra-cheap reversal qualification.
# These are intentionally separate from Lane A so a cheap contract is never
# accepted merely because it is cheap. It must show an actual turn in the
# side-oriented BTC/BRTI impulse while Kalshi has not already repriced it.
# ---------------------------------------------------------------------------
REV_MIN_ASK = 0.03
REV_MAX_ASK = 0.069999
REV_MIN_LEFT = 120.0
REV_BTC5_MIN = 8.0
REV_BTC15_FLOOR = -15.0
REV_ACCEL_MIN = 8.0
REV_BRTI5_MIN = 4.0
REV_BRTI_ACCEL_MIN = 4.0
REV_ASK5_FLOOR = -0.01
REV_ASK5_CEIL = 0.03
REV_ASK15_CEIL = 0.04

CONFIRM_WINDOW = 4.0
CONFIRM_COUNT = 2
confirm = defaultdict(deque)
pending_v7 = []
last_v7 = {}
score_total = defaultdict(lambda: {'n':0,'hit5':0,'hit10':0,'burst10':0,'expand10':0,'hit20':0,'gain_sum':0.0,'adverse_sum':0.0})
score_contract = defaultdict(lambda: {'n':0,'hit5':0,'hit10':0,'burst10':0,'expand10':0,'hit20':0,'gain_sum':0.0,'adverse_sum':0.0})
rejects = defaultdict(int)
last_ticker = None
last_stats_ts = 0.0


def _fresh_brti(f):
    return f.get('brti5') is not None and f.get('brti15') is not None


def momentum_quality(row, side, f):
    ask = row[side.lower() + '_ask']
    if ask is None or ask < MOM_MIN_ASK or ask > MOM_MAX_ASK:
        return False, 'MOM_PRICE'
    if not _fresh_brti(f):
        return False, 'MOM_BRTI_DEGRADED'
    if not f.get('v4') or not f.get('structure_ok'):
        return False, 'MOM_BASE_NOT_READY'
    if ask <= MOM_PREF_MAX:
        return True, 'MOMENTUM_PREFERRED_7_30C'
    strong = (
        f['btc5'] >= MOM_HIGH_BTC5 and
        f['btc15'] >= MOM_HIGH_BTC15 and
        f['brti5'] >= MOM_HIGH_BRTI5 and
        f['brti15'] >= MOM_HIGH_BRTI15 and
        f['accel'] >= MOM_HIGH_ACCEL and
        f['btc30'] is not None and f['btc30'] >= MOM_HIGH_BTC30
    )
    return strong, ('MOMENTUM_HIGH_STRONG' if strong else 'MOM_HIGH_REJECT')


def reversal_quality(row, side, f):
    ask = row[side.lower() + '_ask']
    if ask is None or ask < REV_MIN_ASK or ask > REV_MAX_ASK:
        return False, 'REV_PRICE'
    if row['left'] < REV_MIN_LEFT:
        return False, 'REV_TOO_LATE'
    # Reversal lane is higher risk than momentum, so it requires fresh BRTI.
    if not _fresh_brti(f):
        return False, 'REV_BRTI_DEGRADED'
    b30 = f.get('btc30')
    brti_accel = f['brti5'] - (f['brti15'] / 3.0)
    turning = (
        f['btc5'] >= REV_BTC5_MIN and
        f['btc15'] >= REV_BTC15_FLOOR and
        f['accel'] >= REV_ACCEL_MIN and
        f['brti5'] >= REV_BRTI5_MIN and
        brti_accel >= REV_BRTI_ACCEL_MIN and
        REV_ASK5_FLOOR <= f['ask5'] <= REV_ASK5_CEIL and
        f['ask15'] <= REV_ASK15_CEIL
    )
    if not turning:
        return False, 'REV_TURN_NOT_READY'
    # A negative/flat 30s structure is allowed here by design: this lane is
    # specifically looking for a new short-term turn before the longer window
    # has fully caught up. Log it as EARLY_TURN vs CONFIRMED_TURN for analysis.
    zone = 'REVERSAL_EARLY_TURN_3_7C' if (b30 is None or b30 < 0) else 'REVERSAL_CONFIRMED_TURN_3_7C'
    return True, zone


def confirmed(row, side, lane, ok):
    k = (row['ticker'], side, lane)
    q = confirm[k]
    now = row['ts']
    while q and q[0] < now - CONFIRM_WINDOW:
        q.popleft()
    if not ok:
        q.clear()
        return False
    q.append(now)
    return len(q) >= CONFIRM_COUNT


def add_candidate(row, side, f, lane, zone):
    k = (row['ticker'], side, lane)
    if row['ts'] - last_v7.get(k, 0) < 20:
        return
    last_v7[k] = row['ts']
    p = side.lower(); ask = row[p+'_ask']; bid = row[p+'_bid']
    if bid is None or ask is None:
        return
    pending_v7.append({
        'ticker':row['ticker'],'side':side,'lane':lane,'zone':zone,
        'ts':row['ts'],'left':row['left'],'entry':ask,'max':bid,'min':bid,
        'x5':None,'x10':None,'x20':None,'ask5_ts':None,
        'btc5':f['btc5'],'btc15':f['btc15'],'btc30':f.get('btc30'),
        'accel':f['accel'],'brti5':f.get('brti5'),'brti15':f.get('brti15'),
        'ask5':f['ask5'],'ask15':f['ask15'],
    })
    print('LEAD_V7 CANDIDATE | lane %s | %s | %s | zone %s | ask %.3f | btc5 %+.2f | btc15 %+.2f | btc30 %s | accel %+.2f | brti5 %+.2f | brti15 %+.2f | ask5 %+.3f | ask15 %+.3f | left %.0fs' % (
        lane,row['ticker'],side,zone,ask,f['btc5'],f['btc15'],
        ('N/A' if f.get('btc30') is None else '%+.2f'%f['btc30']),f['accel'],
        f['brti5'],f['brti15'],f['ask5'],f['ask15'],row['left']), flush=True)


def _bump(bucket, e, gain, adverse, t5, t10, t20):
    s=bucket[e['lane']]; s['n']+=1
    if t5 is not None:s['hit5']+=1
    if t10 is not None:
        s['hit10']+=1
        if t10<=30:s['burst10']+=1
        if t10<=120:s['expand10']+=1
    if t20 is not None:s['hit20']+=1
    s['gain_sum']+=gain; s['adverse_sum']+=adverse


def resolve_v7(row):
    done=[]
    for e in pending_v7:
        if e['ticker'] != row['ticker']:
            done.append(e); continue
        p=e['side'].lower(); bid=row[p+'_bid']; ask=row[p+'_ask']
        if bid is not None:
            e['max']=max(e['max'],bid); e['min']=min(e['min'],bid); g=bid-e['entry']
            if g>=.05 and e['x5'] is None:e['x5']=row['ts']
            if g>=.10 and e['x10'] is None:e['x10']=row['ts']
            if g>=.20 and e['x20'] is None:e['x20']=row['ts']
        if ask is not None and ask-e['entry']>=.05 and e['ask5_ts'] is None:e['ask5_ts']=row['ts']
        if row['ts']-e['ts']>=HORIZON or row['left']<=0:done.append(e)
    for e in done:
        if e in pending_v7: pending_v7.remove(e)
        t5=None if e['x5'] is None else round(e['x5']-e['ts'],1)
        t10=None if e['x10'] is None else round(e['x10']-e['ts'],1)
        t20=None if e['x20'] is None else round(e['x20']-e['ts'],1)
        ar=None if e['ask5_ts'] is None else round(e['ask5_ts']-e['ts'],1)
        gain=e['max']-e['entry']; adverse=e['min']-e['entry']
        _bump(score_total,e,gain,adverse,t5,t10,t20); _bump(score_contract,e,gain,adverse,t5,t10,t20)
        style='NO_EXPANSION'
        if t10 is not None and t10<=30:style='BURST'
        elif t10 is not None and t10<=180:style='EXPANSION'
        print('LEAD_V7 RESULT | lane %s | %s | %s | zone %s | style %s | entry %.3f | max_gain %+.3f | adverse %+.3f | to+5c %s | to+10c %s | to+20c %s | reprice+5c %s' % (
            e['lane'],e['ticker'],e['side'],e['zone'],style,e['entry'],gain,adverse,t5,t10,t20,ar), flush=True)


def fmt_lane(s):
    if not s['n']:return 'n=0'
    n=s['n']
    return 'n=%d hit5=%.1f%% hit10=%.1f%% burst10=%.1f%% expand10=%.1f%% hit20=%.1f%% avgGain=%+.3f avgAdv=%+.3f' % (
        n,100*s['hit5']/n,100*s['hit10']/n,100*s['burst10']/n,100*s['expand10']/n,100*s['hit20']/n,s['gain_sum']/n,s['adverse_sum']/n)


def summary(prefix,ticker,bucket):
    print('%s | %s | MOM %s | REV %s | BRTI %s' % (
        prefix,ticker,fmt_lane(bucket['MOMENTUM_EXPANSION']),fmt_lane(bucket['ULTRA_CHEAP_REVERSAL']),_brti_guard.compact_stats()), flush=True)


print('SCALP LEAD SPLIT V7 START | MOMENTUM_EXPANSION + ULTRA_CHEAP_REVERSAL | RESEARCH ONLY | NO ORDERS', flush=True)
while True:
    t=time.time()
    try:
        row=snap()
        if row:
            if last_ticker is not None and row['ticker']!=last_ticker:
                summary('LEAD_V7 CONTRACT_SUMMARY',last_ticker,score_contract)
                summary('LEAD_V7 CUMULATIVE',last_ticker,score_total)
                score_contract.clear(); rejects.clear()
            last_ticker=row['ticker']
            hist.append(row)
            while hist and hist[0]['ts']<row['ts']-KEEP:hist.popleft()
            resolve_v7(row)
            for side in ('UP','DOWN'):
                f=features(row,side)
                if not f:continue
                mok,mzone=momentum_quality(row,side,f)
                if confirmed(row,side,'MOMENTUM_EXPANSION',mok):
                    add_candidate(row,side,f,'MOMENTUM_EXPANSION',mzone)
                elif not mok:rejects[mzone]+=1

                rok,rzone=reversal_quality(row,side,f)
                if confirmed(row,side,'ULTRA_CHEAP_REVERSAL',rok):
                    add_candidate(row,side,f,'ULTRA_CHEAP_REVERSAL',rzone)
                elif not rok:rejects[rzone]+=1

            if row['ts']-last_stats_ts>=300:
                summary('LEAD_V7 MIDCONTRACT',row['ticker'],score_contract)
                print('LEAD_V7 REJECTS | %s' % dict(rejects),flush=True)
                last_stats_ts=row['ts']
            if int(row['ts'])%30==0:
                bv='N/A' if row['brti'] is None else ('%.2f'%row['brti'])
                print('LEAD_V7 HEARTBEAT | %s | %.2fm | BTC %.2f | BRTI %s | UP %.3f | DOWN %.3f | pending %d' % (
                    row['ticker'],row['left']/60,row['btc'],bv,row['up_ask'],row['down_ask'],len(pending_v7)),flush=True)
    except Exception as e:
        print('LEAD_V7 WARNING | %s: %s' % (type(e).__name__,e),flush=True)
    time.sleep(max(.05,POLL-(time.time()-t)))
