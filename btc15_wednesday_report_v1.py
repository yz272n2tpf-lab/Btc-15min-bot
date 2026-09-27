#!/usr/bin/env python3
"""Frozen prospective cohort report. Disk-only; no network, no strategy evaluation, NO ORDERS."""
import argparse,json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from btc15_cohort_evidence_v1 import _truth,score_native_paths,score_native_settlement

SCHEMA='BTC15_COHORT_NATIVE_V1'
START_UTC='2026-09-27T13:45:00Z'

def dt(s):
    return datetime.fromisoformat(str(s).replace('Z','+00:00')).astimezone(timezone.utc)

def read_window(path,start,end):
    out=[]
    for line in Path(path).read_text().splitlines():
        if not line.strip(): continue
        r=json.loads(line)
        if r.get('schema')!=SCHEMA: raise ValueError('Unexpected native cohort schema')
        if r.get('signal_only') is not True or r.get('orders') is not False:
            raise ValueError('Signal-only invariant failed')
        t=dt(r['timestamp_utc'])
        if start<=t<end: out.append(r)
    return out

def report(path,start,end):
    rows=read_window(path,start,end); by=defaultdict(list)
    for r in rows: by[r.get('contract')].append(r)
    contracts=[]
    for ticker,rs in sorted(by.items()):
        if not ticker: continue
        rs.sort(key=lambda r:r['timestamp_utc'])
        p=score_native_paths(rs); settlement=score_native_settlement(rs)
        final_calls=p['final_calls']; settled=settlement['settlement']
        actual=settled.get('final60_side') if settled else None
        final_side=final_calls[0].get('final_side') if final_calls else None
        early=p['early_qualified']
        # Native rows preserve contemporaneous asks in early evidence when available.
        early_asks=[]
        for e in early:
            for k in ('entry_ask','ask','preferred_ask'):
                try:
                    v=float(e.get(k))
                    if v>1: v/=100.0
                    early_asks.append(v);break
                except (TypeError,ValueError): pass
        contracts.append(dict(ticker=ticker,rows=len(rs),actual=actual,
          settlement=settlement['status'],final_status=p['final_status'],final_side=final_side,
          final_correct=(final_side==actual) if final_side and actual else None,
          early_status=p['early_status'],early_count=len(early),early_asks=early_asks,
          scalp_status=p['scalp_status'],profit_status=p['profit_status'],
          five_minute_rows=sum(float(r.get('seconds_left') or 9999)<=300 for r in rs if r.get('final_status')!='CLOSEOUT_ONLY'),
          three_minute_rows=sum(float(r.get('seconds_left') or 9999)<=180 for r in rs if r.get('final_status')!='CLOSEOUT_ONLY')))
    q=[c for c in contracts if c['final_status']=='QUALIFIED' and c['final_correct'] is not None]
    asks=[a for c in contracts for a in c['early_asks']]
    complete=[c for c in contracts if c['settlement']=='COMPLETE']
    return dict(schema='BTC15_WEDNESDAY_REPORT_V1',start_utc=start.isoformat(),end_utc=end.isoformat(),
      contract_count=len(contracts),settlement_complete=len(complete),
      evidence_complete_pct=(100*len(complete)/len(contracts) if contracts else None),
      final_qualified=len(q),final_wins=sum(c['final_correct'] for c in q),
      final_losses=sum(not c['final_correct'] for c in q),
      final_accuracy_pct=(100*sum(c['final_correct'] for c in q)/len(q) if q else None),
      final_pass=sum(c['final_status']=='PASS' for c in contracts),
      early_qualified=sum(c['early_status']=='QUALIFIED' for c in contracts),
      early_entry_count=len(asks),early_le_50=sum(a<=.50 for a in asks),
      early_ideal_25_35=sum(.25<=a<=.35 for a in asks),
      scalp_qualified=sum(c['scalp_status']=='QUALIFIED' for c in contracts),
      profit_recorded=sum(c['profit_status']=='RECORDED' for c in contracts),
      five_minute_rows=sum(c['five_minute_rows'] for c in contracts),three_minute_rows=sum(c['three_minute_rows'] for c in contracts),
      signal_only_violations=0,orders=0,contracts=contracts)

def comparison(ground_zero,full_run):
    keys=('contract_count','settlement_complete','evidence_complete_pct','final_qualified','final_wins','final_losses','final_accuracy_pct','final_pass','early_qualified','early_entry_count','early_le_50','early_ideal_25_35','scalp_qualified','profit_recorded','five_minute_rows','three_minute_rows','signal_only_violations','orders')
    return {k:{'ground_zero':ground_zero.get(k),'full_run':full_run.get(k)} for k in keys}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('journal');ap.add_argument('--start',default=START_UTC);ap.add_argument('--end',required=True)
    a=ap.parse_args(); full=report(a.journal,dt(a.start),dt(a.end)); print(json.dumps(full,indent=2,sort_keys=True))
if __name__=='__main__': main()
