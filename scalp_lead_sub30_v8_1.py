#!/usr/bin/env python3
"""V8.1 surgical sub-30 scalp research. SIGNAL ONLY. NO ORDERS.

Protects the validated 30-45c V8 CORE/SURGE gate and changes only sub-30
qualification. 7-15c current CORE is rejected. 3-7c and 15-30c require a
stronger SUB30_STRONG route plus early-enough time remaining.
"""
_src=open('scalp_lead_unified_v8.py','r',encoding='utf-8').read()
# Cut before the self-test definition, not before its call. Splitting on the
# call left the function header/body in the prefix and could strand syntax.
_prefix=_src.split("def _self_test_unified_gate():",1)[0]
exec(compile(_prefix,'scalp_lead_unified_v8.py','exec'),globals())

SUB30_MIN_LEFT=240.0
SUB30_FLOORS={'btc5':30.0,'btc15':40.0,'brti5':25.0,'brti15':20.0,'accel':18.0,'btc30':10.0}
CONFIRM_WINDOW=5.0; CONFIRM_COUNT=3
confirm=defaultdict(deque); pending=[]; last_signal={}; rejects=defaultdict(int)
score_total=defaultdict(lambda:{'n':0,'hit5':0,'hit10':0,'hit20':0,'gain_sum':0.0,'adverse_sum':0.0,'pre10_adverse_sum':0.0})
score_contract=defaultdict(lambda:{'n':0,'hit5':0,'hit10':0,'hit20':0,'gain_sum':0.0,'adverse_sum':0.0,'pre10_adverse_sum':0.0})
last_ticker=None;last_stats_ts=0.0

def v81_quality(row,side,f):
    ask=row[side.lower()+'_ask']
    if ask is None or ask<MIN_ASK or ask>MAX_ASK:return False,'PRICE_OUTSIDE_3_45C',None
    if not _fresh(f):return False,'BRTI_DEGRADED',None
    if not f.get('v4') or not f.get('structure_ok'):return False,'BASE_NOT_READY',None
    zone=_zone(ask)
    if zone=='HIGH_30_45C':
        route,q=evidence_route(f)
        return (route is not None,'PROTECTED_HIGH' if route else 'EVIDENCE_HIGH_30_45C',route)
    if zone=='CHEAP_7_15C':return False,'REJECT_7_15C_CURRENT_GATE',None
    if row['left']<SUB30_MIN_LEFT:return False,'SUB30_TOO_LATE',None
    q=_floor_ratio(f,SUB30_FLOORS)
    if q<1.0:return False,'SUB30_STRONG_NOT_READY_'+zone,None
    return True,'TIGHT_'+zone,'SUB30_STRONG'

def confirmed81(row,side,route,ok):
    k=(row['ticker'],side,route or 'NONE');q=confirm[k];now=row['ts']
    win=4.0 if route in ('CORE','SURGE') else CONFIRM_WINDOW
    need=2 if route in ('CORE','SURGE') else CONFIRM_COUNT
    while q and q[0]<now-win:q.popleft()
    if not ok:q.clear();return False
    q.append(now);return len(q)>=need

def add(row,side,f,label,route):
    k=(row['ticker'],side,label)
    if row['ts']-last_signal.get(k,0)<20:return
    p=side.lower();ask=row[p+'_ask'];bid=row[p+'_bid']
    if ask is None or bid is None:return
    last_signal[k]=row['ts'];q=_floor_ratio(f,SUB30_FLOORS) if route=='SUB30_STRONG' else evidence_route(f)[1]
    pending.append({'ticker':row['ticker'],'side':side,'zone':'UNIFIED_'+_zone(ask),'route':route,'ts':row['ts'],'entry':ask,'max':bid,'min':bid,'pre10_min':bid,'x5':None,'x10':None,'x20':None,'q':q})
    print('V81 CANDIDATE | %s | %s | %s | route %s | ask %.3f | q %.2f | left %.0fs'%(row['ticker'],side,_zone(ask),route,ask,q,row['left']),flush=True)

def resolve81(row):
    done=[]
    for e in pending:
        if e['ticker']!=row['ticker']:done.append(e);continue
        bid=row[e['side'].lower()+'_bid']
        if bid is not None:
            e['max']=max(e['max'],bid);e['min']=min(e['min'],bid);g=bid-e['entry']
            if e['x10'] is None:e['pre10_min']=min(e['pre10_min'],bid)
            if g>=.05 and e['x5'] is None:e['x5']=row['ts']
            if g>=.10 and e['x10'] is None:e['x10']=row['ts']
            if g>=.20 and e['x20'] is None:e['x20']=row['ts']
        if row['ts']-e['ts']>=180 or row['left']<=0:done.append(e)
    for e in done:
        if e in pending:pending.remove(e)
        t=lambda x:None if x is None else round(x-e['ts'],1)
        t5,t10,t20=t(e['x5']),t(e['x10']),t(e['x20']);gain=e['max']-e['entry'];adv=e['min']-e['entry'];pre=e['pre10_min']-e['entry']
        for bucket in (score_total,score_contract):
            s=bucket[e['zone']];s['n']+=1;s['hit5']+=t5 is not None;s['hit10']+=t10 is not None;s['hit20']+=t20 is not None;s['gain_sum']+=gain;s['adverse_sum']+=adv;s['pre10_adverse_sum']+=pre
        print('V81 RESULT | %s | %s | %s | route %s | entry %.3f | max_gain %+.3f | adverse %+.3f | pre10 %+.3f | to5 %s | to10 %s | to20 %s'%(e['ticker'],e['side'],e['zone'],e['route'],e['entry'],gain,adv,pre,t5,t10,t20),flush=True)

def fmt81(s):
    if not s['n']:return 'n=0'
    n=s['n'];return 'n=%d hit5=%.1f%% hit10=%.1f%% hit20=%.1f%% avgGain=%+.3f avgAdv=%+.3f avgPre10=%+.3f'%(n,100*s['hit5']/n,100*s['hit10']/n,100*s['hit20']/n,s['gain_sum']/n,s['adverse_sum']/n,s['pre10_adverse_sum']/n)
def summary81(prefix,ticker,b):
    print('%s | %s | U3_7 %s | C7_15 %s | V15_30 %s | H30_45 %s | BRTI %s'%(prefix,ticker,fmt81(b['UNIFIED_ULTRA_3_7C']),fmt81(b['UNIFIED_CHEAP_7_15C']),fmt81(b['UNIFIED_VALUE_15_30C']),fmt81(b['UNIFIED_HIGH_30_45C']),_brti_guard.compact_stats()),flush=True)

print('SCALP V8.1 START | SURGICAL SUB30 TIGHTEN | 30-45 PROTECTED | 7-15 REJECTED | NO ORDERS',flush=True)
while True:
    t=time.time()
    try:
        row=snap()
        if row:
            resolve81(row)
            if last_ticker is not None and row['ticker']!=last_ticker:
                summary81('V81 CONTRACT',last_ticker,score_contract);summary81('V81 CUMULATIVE',last_ticker,score_total);score_contract.clear();rejects.clear()
            last_ticker=row['ticker'];hist.append(row)
            while hist and hist[0]['ts']<row['ts']-KEEP:hist.popleft()
            for side in ('UP','DOWN'):
                f=features(row,side)
                if not f:continue
                ok,label,route=v81_quality(row,side,f)
                if confirmed81(row,side,route,ok):add(row,side,f,label,route)
                elif not ok:rejects[label]+=1
            if row['ts']-last_stats_ts>=300:
                summary81('V81 MID',row['ticker'],score_contract);print('V81 REJECTS | %s'%dict(rejects),flush=True);last_stats_ts=row['ts']
            if int(row['ts'])%30==0:print('V81 HEARTBEAT | %s | %.2fm | UP %.3f | DOWN %.3f | pending %d'%(row['ticker'],row['left']/60,row['up_ask'],row['down_ask'],len(pending)),flush=True)
    except Exception as e:print('V81 WARNING | %s: %s'%(type(e).__name__,e),flush=True)
    time.sleep(max(.05,POLL-(time.time()-t)))
