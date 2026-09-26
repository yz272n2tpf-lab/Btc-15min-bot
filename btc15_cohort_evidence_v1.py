"""Disk-only cohort evidence reader. No live feeds, no strategy evaluation, NO ORDERS."""
import json
from pathlib import Path

REQUIRED_INFORMATION = {
    'frame_id','anchor_id','ticker','target','native_decision_ts','published_ts','seconds_left',
    'up_bid','up_ask','down_bid','down_ask','probability_up','probability_down','flip_risk_pct',
    'preferred_side','brti_side','brti_agrees','protection_phase','five_minute_caution',
    'three_minute_guard','protection_watch','signal_only','orders'
}

def read_information(path):
    records=[]
    for line in Path(path).read_text().splitlines():
        if not line.strip(): continue
        record=json.loads(line)
        if record.get('schema')!='BTC15_INFORMATION_JOURNAL_V1':
            raise ValueError('Unexpected journal schema')
        frame=record.get('frame')
        if not isinstance(frame,dict) or not REQUIRED_INFORMATION.issubset(frame):
            raise ValueError('Incomplete information frame')
        if record.get('frame_id')!=frame.get('frame_id'):
            raise ValueError('Frame identity mismatch')
        if frame.get('signal_only') is not True or frame.get('orders') is not False:
            raise ValueError('Signal-only invariant failed')
        records.append(frame)
    return records

def contract_information(path,ticker):
    rows=[r for r in read_information(path) if r['ticker']==ticker]
    if not rows: raise ValueError('MISSING_INFORMATION_EVIDENCE')
    rows.sort(key=lambda r:(r['published_ts'],r['frame_id']))
    return rows


def classify_early(rows, ticker):
    contract=[r for r in rows if r.get('contract')==ticker]
    if not contract: return {'status':'MISSING','qualified':[]}
    qualified=[r for r in contract if r.get('provisional_candidate') is True]
    return {'status':'QUALIFIED' if qualified else 'PASS','qualified':qualified}

def classify_scalp(events, ticker, coverage_proven=False):
    contract=[r for r in events if r.get('contract')==ticker]
    if contract: return {'status':'QUALIFIED','events':contract}
    return {'status':'PASS' if coverage_proven else 'MISSING','events':[]}

def classify_final(rows, ticker):
    contract=[r for r in rows if r.get('contract')==ticker]
    if not contract: return {'status':'MISSING','calls':[]}
    calls=[r for r in contract if r.get('final_status')=='FINAL CALL']
    if calls: return {'status':'QUALIFIED','calls':calls}
    if any(r.get('final_status')=='PASS' for r in contract):
        return {'status':'PASS','calls':[]}
    return {'status':'MISSING','calls':[]}
