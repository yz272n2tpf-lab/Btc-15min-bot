#!/usr/bin/env python3
"""Unified V8 scalp/expansion research collector. Signal-only. NO ORDERS.

Mission: one UP/DOWN expansion engine across 3c-45c. Price alone never lowers
qualification quality. BRTI transport remains the frozen V7 implementation.
The failed V7 standalone ultra-cheap reversal lane is intentionally excluded.
"""
_src = open('scalp_lead_shadow_v5.py','r',encoding='utf-8').read()
_prefix = _src.split("print('SCALP LEAD SHADOW V5 START",1)[0]
exec(compile(_prefix,'scalp_lead_shadow_v5.py','exec'),globals())
from brti_resilience_shadow_v2 import BrtiResilienceGuard, qualification_value

HORIZON=180
_brti_guard=BrtiResilienceGuard(retries=4,backoff_s=(0.05,0.10,0.20),diagnostic_cache_ttl_s=3.0)
def _primary_brti_once():
    r=requests.get(EXT+BRTI_PATH,headers=hdr('GET',BRTI_PATH),params={'id':'BRTI','maxResolution':'PER_SECOND'},timeout=1.5)
    r.raise_for_status(); return brti_value(r.json())
def brti(): return qualification_value(_brti_guard.fetch(_primary_brti_once))

MIN_ASK=0.03; MAX_ASK=0.45
# Quality floors by price zone. Cheap is NOT easier; the lowest zone requires
# the strongest emerging-expansion evidence because false turns are expensive.
ZONES=(
    (0.07,'ULTRA_3_7C',24.0,24.0,18.0,12.0,12.0,0.0),
    (0.15,'CHEAP_7_15C',20.0,22.0,15.0,8.0,10.0,0.0),
    (0.30,'VALUE_15_30C',18.0,22.0,14.0,7.0,9.0,0.0),
    (0.451,'HIGH_30_45C',20.0,25.0,15.0,5.0,10.0,0.0),
)
CONFIRM_WINDOW=4.0; CONFIRM_COUNT=2
confirm=defaultdict(deque); pending=[]; last_signal={}; rejects=defaultdict(int)
score_total=defaultdict(lambda:{'n':0,'hit5':0,'hit10':0,'burst10':0,'expand10':0,'hit20':0,'gain_sum':0.0,'adverse_sum':0.0})
score_contract=defaultdict(lambda:{'n':0,'hit5':0,'hit10':0,'burst10':0,'expand10':0,'hit20':0,'gain_sum':0.0,'adverse_sum':0.0})
last_ticker=None; last_stats_ts=0.0

def _fresh(f): return f.get('brti5') is not None and f.get('brti15') is not None
def _zone(ask):
    for ceiling,name,b5,b15,r5,r15,acc,b30 in ZONES:
        if ask<ceiling:return name,b5,b15,r5,r15,acc,b30
    return None

def unified_quality(row,side,f):
    ask=row[side.lower()+'_ask']
    if ask is None or ask<MIN_ASK or ask>MAX_ASK:return False,'PRICE_OUTSIDE_3_45C'
    if not _fresh(f):return False,'BRTI_DEGRADED'
    if not f.get('v4') or not f.get('structure_ok'):return False,'BASE_NOT_READY'
    z=_zone(ask)
    if not z:return False,'ZONE_MISSING'
    name,b5,b15,r5,r15,acc,b30=z
    strong=(f['btc5']>=b5 and f['btc15']>=b15 and f['brti5']>=r5 and f['brti15']>=r15 and f['accel']>=acc and f.get('btc30') is not None and f['btc30']>=b30)
    if not strong:return False,'EVIDENCE_'+name
    return True,'UNIFIED_'+name

def confirmed(row,side,ok):
    k=(row['ticker'],side); q=confirm[k]; now=row['ts']
    while q and q[0]<now-CONFIRM_WINDOW:q.popleft()
    if not ok:q.clear(); return False
    q.append(now); return len(q)>=CONFIRM_COUNT

def add_candidate(row,side,f,zone):
    k=(row['ticker'],side)
    if row['ts']-last_signal.get(k,0)<20:return
    p=side.lower(); ask=row[p+'_ask']; bid=row[p+'_bid']
    if ask is None or bid is None:return
    last_signal[k]=row['ts']
    pending.append({'ticker':row['ticker'],'side':side,'zone':zone,'ts':row['ts'],'left':row['left'],'entry':ask,'max':bid,'min':bid,'x5':None,'x10':None,'x20':None,'btc5':f['btc5'],'btc15':f['btc15'],'btc30':f.get('btc30'),'accel':f['accel'],'brti5':f['brti5'],'brti15':f['brti15']})
    print('UNIFIED_V8 CANDIDATE | %s | %s | zone %s | ask %.3f | btc5 %+.2f | btc15 %+.2f | btc30 %+.2f | accel %+.2f | brti5 %+.2f | brti15 %+.2f | left %.0fs'%(row['ticker'],side,zone,ask,f['btc5'],f['btc15'],f['btc30'],f['accel'],f['brti5'],f['brti15'],row['left']),flush=True)

def _bump(bucket,e,gain,adv,t5,t10,t20):
    s=bucket[e['zone']]; s['n']+=1
    if t5 is not None:s['hit5']+=1
    if t10 is not None:
        s['hit10']+=1
        if t10<=30:s['burst10']+=1
        if t10<=120:s['expand10']+=1
    if t20 is not None:s['hit20']+=1
    s['gain_sum']+=gain;s['adverse_sum']+=adv

def resolve(row):
    done=[]
    for e in pending:
        if e['ticker']!=row['ticker']:done.append(e);continue
        bid=row[e['side'].lower()+'_bid']
        if bid is not None:
            e['max']=max(e['max'],bid);e['min']=min(e['min'],bid);g=bid-e['entry']
            if g>=.05 and e['x5'] is None:e['x5']=row['ts']
            if g>=.10 and e['x10'] is None:e['x10']=row['ts']
            if g>=.20 and e['x20'] is None:e['x20']=row['ts']
        if row['ts']-e['ts']>=HORIZON or row['left']<=0:done.append(e)
    for e in done:
        if e in pending:pending.remove(e)
        ts=lambda x:None if x is None else round(x-e['ts'],1)
        t5,t10,t20=ts(e['x5']),ts(e['x10']),ts(e['x20']);gain=e['max']-e['entry'];adv=e['min']-e['entry']
        _bump(score_total,e,gain,adv,t5,t10,t20);_bump(score_contract,e,gain,adv,t5,t10,t20)
        style='BURST' if t10 is not None and t10<=30 else ('EXPANSION' if t10 is not None else 'NO_EXPANSION')
        print('UNIFIED_V8 RESULT | %s | %s | zone %s | style %s | entry %.3f | max_gain %+.3f | adverse %+.3f | to+5c %s | to+10c %s | to+20c %s'%(e['ticker'],e['side'],e['zone'],style,e['entry'],gain,adv,t5,t10,t20),flush=True)

def fmt(s):
    if not s['n']:return 'n=0'
    n=s['n'];return 'n=%d hit5=%.1f%% hit10=%.1f%% burst10=%.1f%% expand10=%.1f%% hit20=%.1f%% avgGain=%+.3f avgAdv=%+.3f'%(n,100*s['hit5']/n,100*s['hit10']/n,100*s['burst10']/n,100*s['expand10']/n,100*s['hit20']/n,s['gain_sum']/n,s['adverse_sum']/n)
def summary(prefix,ticker,bucket):
    parts=['%s=%s'%(z,fmt(bucket['UNIFIED_'+z])) for _,z,*_ in ZONES]
    print('%s | %s | %s | BRTI %s'%(prefix,ticker,' | '.join(parts),_brti_guard.compact_stats()),flush=True)

print('UNIFIED SCALP V8 START | 3-45C QUALITY-FIRST EXPANSION | RESEARCH ONLY | NO ORDERS',flush=True)
while True:
    t=time.time()
    try:
        row=snap()
        if row:
            if last_ticker is not None and row['ticker']!=last_ticker:
                summary('UNIFIED_V8 CONTRACT_SUMMARY',last_ticker,score_contract);summary('UNIFIED_V8 CUMULATIVE',last_ticker,score_total);score_contract.clear();rejects.clear()
            last_ticker=row['ticker'];hist.append(row)
            while hist and hist[0]['ts']<row['ts']-KEEP:hist.popleft()
            resolve(row)
            for side in ('UP','DOWN'):
                f=features(row,side)
                if not f:continue
                ok,zone=unified_quality(row,side,f)
                if confirmed(row,side,ok):add_candidate(row,side,f,zone)
                elif not ok:rejects[zone]+=1
            if row['ts']-last_stats_ts>=300:
                summary('UNIFIED_V8 MIDCONTRACT',row['ticker'],score_contract);print('UNIFIED_V8 REJECTS | %s'%dict(rejects),flush=True);last_stats_ts=row['ts']
            if int(row['ts'])%30==0:
                bv='N/A' if row['brti'] is None else '%.2f'%row['brti']
                print('UNIFIED_V8 HEARTBEAT | %s | %.2fm | BTC %.2f | BRTI %s | UP %.3f | DOWN %.3f | pending %d'%(row['ticker'],row['left']/60,row['btc'],bv,row['up_ask'],row['down_ask'],len(pending)),flush=True)
    except Exception as e:print('UNIFIED_V8 WARNING | %s: %s'%(type(e).__name__,e),flush=True)
    time.sleep(max(.05,POLL-(time.time()-t)))
