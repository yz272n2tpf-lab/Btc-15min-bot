#!/usr/bin/env python3
"""Rate-limit-aware BRTI probe. Research only. NO ORDERS.

Purpose: find a sustainable request cadence for the Kalshi BRTI endpoint without
rapid retries that amplify HTTP 429 responses.
"""
import os,time,base64,argparse
from collections import Counter
from statistics import mean,median
import requests
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding

EXT='https://external-api.kalshi.com'
PATH='/trade-api/v2/cfbenchmarks/values'

def load_auth():
    kid=os.environ['KALSHI_KEY_ID'].strip()
    key=serialization.load_pem_private_key(base64.b64decode(os.environ['KALSHI_PRIVATE_KEY_B64'].strip()),password=None)
    return kid,key

def hdr(kid,key):
    ts=str(int(time.time()*1000)); msg=ts+'GET'+PATH
    sig=key.sign(msg.encode(),padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.DIGEST_LENGTH),hashes.SHA256())
    return {'KALSHI-ACCESS-KEY':kid,'KALSHI-ACCESS-SIGNATURE':base64.b64encode(sig).decode(),'KALSHI-ACCESS-TIMESTAMP':ts}

def parse_value(obj):
    vals=[]
    def walk(x):
        if isinstance(x,dict):
            if 'value' in x:
                try:
                    v=float(x.get('value'))
                    if 1000<v<1_000_000: vals.append(v)
                except: pass
            for y in x.values(): walk(y)
        elif isinstance(x,list):
            for y in x: walk(y)
    walk(obj); return vals[-1] if vals else None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--seconds',type=int,default=180); ap.add_argument('--interval',type=float,default=2.25); ap.add_argument('--timeout',type=float,default=1.5)
    a=ap.parse_args(); kid,key=load_auth(); s=requests.Session(); status=Counter(); lat=[]; valid=0; invalid=0; started=time.time(); end=started+a.seconds
    while time.time()<end:
        t0=time.monotonic()
        try:
            r=s.get(EXT+PATH,headers=hdr(kid,key),params={'id':'BRTI','maxResolution':'PER_SECOND'},timeout=a.timeout)
            lat.append((time.monotonic()-t0)*1000); status[str(r.status_code)]+=1
            if r.status_code==200:
                v=parse_value(r.json())
                if v is None: invalid+=1
                else: valid+=1
        except requests.Timeout: status['TIMEOUT']+=1
        except requests.ConnectionError: status['CONNECTION']+=1
        except Exception: status['OTHER']+=1
        elapsed=time.monotonic()-t0; sleep_for=a.interval-elapsed
        if sleep_for>0: time.sleep(sleep_for)
    total=sum(status.values()) or 1; ordered=sorted(lat); p95=ordered[min(len(ordered)-1,int(.95*(len(ordered)-1)))] if ordered else 0
    print('BRTI_RATE_PROBE_RESULT')
    print(f'duration_s={time.time()-started:.1f} interval_s={a.interval:.2f}')
    print(f'requests={sum(status.values())} statuses={dict(status)}')
    print(f'valid={valid} valid_rate={100*valid/total:.2f}% invalid_payloads={invalid}')
    if lat: print(f'latency_ms_mean={mean(lat):.1f} median={median(lat):.1f} p95={p95:.1f} max={max(lat):.1f}')

if __name__=='__main__': main()
