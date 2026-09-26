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
