#!/usr/bin/env python3
"""V4 research-only scalp lead-time collector. Signal-only. NO ORDERS.

Runs BROAD + V3_QUALIFIED + V4_QUALIFIED labels in parallel. V4 is deliberately
stricter: stronger 5s/15s BTC persistence, stronger BRTI confirmation, minimum
entry price, and a late-contract guardrail. This is a shadow experiment only.
"""
import os,re,time,base64
from collections import deque
from datetime import datetime,timezone
import requests
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding

POLL=1.0; KEEP=180; HORIZON=90; MAX_ASK=.45
BTC5_MIN=4.0; BTC15_MIN=8.0; MAX_ASK5=.03
V3_BTC5=6.0; V3_BTC15=10.0; V3_BRTI5=4.0; V3_MAX_ASK5=.01; V3_MAX_ASK15=.03; V3_MIN_LEFT=45.0
V4_BTC5=10.0; V4_BTC15=15.0; V4_BRTI5=8.0; V4_MIN_ACCEL=4.0
V4_MAX_ASK5=.005; V4_MAX_ASK15=.015; V4_MIN_LEFT=120.0; V4_MIN_ASK=.03
KEY_ID=os.environ['KALSHI_KEY_ID'].strip()
KEY=serialization.load_pem_private_key(base64.b64decode(os.environ['KALSHI_PRIVATE_KEY_B64'].strip()),password=None)
MARKET='https://api.elections.kalshi.com'; EXT='https://external-api.kalshi.com'
BRTI_PATH='/trade-api/v2/cfbenchmarks/values'; CB='https://api.exchange.coinbase.com/products/BTC-USD/ticker'
hist=deque(); pending=[]; last={}

def hdr(method,path):
    ts=str(int(time.time()*1000)); msg=ts+method.upper()+path
    sig=KEY.sign(msg.encode(),padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.DIGEST_LENGTH),hashes.SHA256())
    return {'KALSHI-ACCESS-KEY':KEY_ID,'KALSHI-ACCESS-SIGNATURE':base64.b64encode(sig).decode(),'KALSHI-ACCESS-TIMESTAMP':ts}

def dt(v):
    try:return datetime.fromisoformat(str(v).replace('Z','+00:00'))
    except:return None

def n(v):
    try:return float(v)
    except:return None

def market():
    p='/trade-api/v2/markets'; r=requests.get(MARKET+p,headers=hdr('GET',p),params={'status':'open','series_ticker':'KXBTC15M','limit':1000},timeout=7); r.raise_for_status(); now=datetime.now(timezone.utc); out=[]
    for m in r.json().get('markets',[]):
        op,cl=dt(m.get('open_time')),dt(m.get('close_time'))
        if op and cl and op<=now<cl and str(m.get('ticker','')).startswith('KXBTC15M'):out.append(m)
    return min(out,key=lambda x:dt(x.get('close_time'))) if out else None

def target(m):
    for k in ('floor_strike','functional_strike'):
        v=n(m.get(k))
        if v is not None:return v
    text=' '.join(str(m.get(k) or '') for k in ('yes_sub_title','title','subtitle'))
    q=re.search(r'Target\s*Price\s*:\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)',text,re.I)
    return float(q.group(1).replace(',','')) if q else None

def brti_value(obj):
    vals=[]
    def walk(x):
        if isinstance(x,dict):
            if 'value' in x:
                v=n(x.get('value'))
                if v is not None and 1000<v<1000000:vals.append(v)
            for y in x.values():walk(y)
        elif isinstance(x,list):
            for y in x:walk(y)
    walk(obj); return vals[-1] if vals else None

def brti():
    try:
        r=requests.get(EXT+BRTI_PATH,headers=hdr('GET',BRTI_PATH),params={'id':'BRTI','maxResolution':'PER_SECOND'},timeout=5); r.raise_for_status(); return brti_value(r.json())
    except:return None

def snap():
    m=market()
    if not m:return None
    now=datetime.now(timezone.utc); cl=dt(m.get('close_time'))
    ub,ua,db,da=[n(m.get(k)) for k in ('yes_bid_dollars','yes_ask_dollars','no_bid_dollars','no_ask_dollars')]
    if None in (ub,ua,db,da):return None
    c=requests.get(CB,timeout=5); c.raise_for_status()
    return {'ts':time.time(),'ticker':str(m.get('ticker')),'left':max(0,(cl-now).total_seconds()),'target':target(m),'btc':float(c.json()['price']),'brti':brti(),'up_bid':ub,'up_ask':ua,'down_bid':db,'down_ask':da}

def ago(row,sec):
    want=row['ts']-sec
    for x in reversed(hist):
        if x['ticker']==row['ticker'] and x['ts']<=want:return x
    return None

def d(row,side,field,sec):
    old=ago(row,sec)
    if not old:return None
    s=1 if side=='UP' else -1
    if field=='btc':return (row['btc']-old['btc'])*s
    if field=='brti':
        if row['brti'] is None or old['brti'] is None:return None
        return (row['brti']-old['brti'])*s
    return row[side.lower()+'_ask']-old[side.lower()+'_ask']

def features(row,side):
    ask=row[side.lower()+'_ask']
    if ask is None or ask>MAX_ASK:return None
    b5,b15=d(row,side,'btc',5),d(row,side,'btc',15)
    a5,a15=d(row,side,'ask',5),d(row,side,'ask',15)
    r5=d(row,side,'brti',5)
    if None in (b5,b15,a5,a15):return None
    accel=b5-(b15/3.0)
    broad=(b5>=BTC5_MIN or b15>=BTC15_MIN) and (r5 is None or r5>0) and a5<=MAX_ASK5
    v3=(broad and row['left']>=V3_MIN_LEFT and b5>=V3_BTC5 and b15>=V3_BTC15 and (r5 is None or r5>=V3_BRTI5) and a5<=V3_MAX_ASK5 and a15<=V3_MAX_ASK15 and accel>0)
    v4=(v3 and row['left']>=V4_MIN_LEFT and ask>=V4_MIN_ASK and b5>=V4_BTC5 and b15>=V4_BTC15 and (r5 is not None and r5>=V4_BRTI5) and accel>=V4_MIN_ACCEL and a5<=V4_MAX_ASK5 and a15<=V4_MAX_ASK15)
    if not broad:return None
    return {'btc5':b5,'btc15':b15,'brti5':r5,'ask5':a5,'ask15':a15,'accel':accel,'v3':v3,'v4':v4}

def add(row,side,f,grade):
    k=(row['ticker'],side,grade)
    if row['ts']-last.get(k,0)<20:return
    last[k]=row['ts']; p=side.lower(); ask=row[p+'_ask']; bid=row[p+'_bid']
    pending.append({'ticker':row['ticker'],'side':side,'grade':grade,'ts':row['ts'],'entry':ask,'max':bid,'min':bid,'x5':None,'x10':None,'ask5_ts':None})
    r5='N/A' if f['brti5'] is None else ('%+.2f'%f['brti5'])
    print('LEAD_V4 CANDIDATE | %s | %s | %s | ask %.3f | btc5 %+.2f | btc15 %+.2f | accel %+.2f | brti5 %s | ask5 %+.3f | ask15 %+.3f | left %.0fs'%(grade,row['ticker'],side,ask,f['btc5'],f['btc15'],f['accel'],r5,f['ask5'],f['ask15'],row['left']),flush=True)

def resolve(row):
    done=[]
    for e in pending:
        if e['ticker']!=row['ticker']:done.append(e);continue
        p=e['side'].lower(); bid=row[p+'_bid']; ask=row[p+'_ask']
        if bid is not None:
            e['max']=max(e['max'],bid); e['min']=min(e['min'],bid); g=bid-e['entry']
            if g>=.05 and e['x5'] is None:e['x5']=row['ts']
            if g>=.10 and e['x10'] is None:e['x10']=row['ts']
        if ask is not None and ask-e['entry']>=.05 and e['ask5_ts'] is None:e['ask5_ts']=row['ts']
        if row['ts']-e['ts']>=HORIZON or row['left']<=0:done.append(e)
    for e in done:
        if e in pending:pending.remove(e)
        t5=None if e['x5'] is None else round(e['x5']-e['ts'],1); t10=None if e['x10'] is None else round(e['x10']-e['ts'],1); ar=None if e['ask5_ts'] is None else round(e['ask5_ts']-e['ts'],1)
        print('LEAD_V4 RESULT | %s | %s | %s | entry %.3f | max_exec_gain %+.3f | adverse %+.3f | hit10 %s | to_exec+5c %s | to_exec+10c %s | kalshi_reprice+5c %s'%(e['grade'],e['ticker'],e['side'],e['entry'],e['max']-e['entry'],e['min']-e['entry'],e['x10'] is not None,t5,t10,ar),flush=True)

print('SCALP LEAD SHADOW V4 START | broad + v3 + v4 parallel research | NO ORDERS',flush=True)
while True:
    t=time.time()
    try:
        row=snap()
        if row:
            hist.append(row)
            while hist and hist[0]['ts']<row['ts']-KEEP:hist.popleft()
            resolve(row)
            for side in ('UP','DOWN'):
                f=features(row,side)
                if f:
                    add(row,side,f,'BROAD')
                    if f['v3']:add(row,side,f,'V3_QUALIFIED')
                    if f['v4']:add(row,side,f,'V4_QUALIFIED')
            if int(row['ts'])%30==0:
                bv='N/A' if row['brti'] is None else ('%.2f'%row['brti'])
                print('LEAD_V4 HEARTBEAT | %s | %.2fm | BTC %.2f | BRTI %s | UP %.3f | DOWN %.3f | pending %d'%(row['ticker'],row['left']/60,row['btc'],bv,row['up_ask'],row['down_ask'],len(pending)),flush=True)
    except Exception as e:print('LEAD_V4 WARNING | %s: %s'%(type(e).__name__,e),flush=True)
    time.sleep(max(.05,POLL-(time.time()-t)))
