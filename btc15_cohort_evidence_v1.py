"""Disk-only cohort evidence reader. No live feeds, no strategy evaluation, NO ORDERS."""
import csv
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


def complete_contract_scorecard(ticker, information_rows, final_rows, early_rows, scalp_events,
                                scalp_coverage_proven=False):
    info=[r for r in information_rows if r.get('ticker')==ticker]
    final=classify_final(final_rows,ticker)
    early=classify_early(early_rows,ticker)
    scalp=classify_scalp(scalp_events,ticker,scalp_coverage_proven)
    missing=[]
    if not info: missing.append('INFORMATION')
    for name,value in (('FINAL',final),('EARLY',early),('SCALP',scalp)):
        if value['status']=='MISSING': missing.append(name)
    return {'ticker':ticker,'status':'COMPLETE' if not missing else 'INCOMPLETE',
            'missing':missing,'information':info,'final':final,'early':early,'scalp':scalp}


def classify_settlement(rows, ticker):
    contract=[r for r in rows if r.get('contract')==ticker]
    complete=[r for r in contract
              if str(r.get('final60_complete')).lower() in ('true','1')
              and int(float(r.get('final60_count',0)))==60
              and r.get('final60_side') in ('UP','DOWN')
              and r.get('final60_average') not in (None,'')]
    return {'status':'COMPLETE' if complete else 'MISSING',
            'settlement':complete[-1] if complete else None}

def classify_profit_protection(rows, ticker, applicable):
    contract=[r for r in rows if r.get('contract')==ticker]
    if contract: return {'status':'RECORDED','events':contract}
    return {'status':'NOT_APPLICABLE' if applicable is False else 'MISSING','events':[]}

def full_contract_scorecard(ticker, information_rows, final_rows, early_rows, scalp_events,
                            settlement_rows, profit_rows, scalp_coverage_proven=False,
                            profit_applicable=None):
    base=complete_contract_scorecard(ticker,information_rows,final_rows,early_rows,scalp_events,
                                     scalp_coverage_proven)
    settlement=classify_settlement(settlement_rows,ticker)
    profit=classify_profit_protection(profit_rows,ticker,profit_applicable)
    missing=list(base['missing'])
    if settlement['status']=='MISSING': missing.append('SETTLEMENT')
    if profit['status']=='MISSING': missing.append('PROFIT_PROTECTION')
    base.update(status='COMPLETE' if not missing else 'INCOMPLETE',missing=missing,
                settlement=settlement,profit_protection=profit)
    return base


PRODUCTION_EVIDENCE_FILES = {
    'final': 'kalshi_two_output_live_log_v4_13.csv',
    'early': 'kalshi_early_conf_shadow_v1_2.csv',
    'scalp_coverage': 'kalshi_scalp_shadow_snapshots_v1.csv',
    'scalp_events': 'kalshi_true_scalp_forward_shadow_v1.csv',
    'profit': 'kalshi_profit_protection_forward_shadow_v1.csv',
    'settlement': 'kalshi_direct_brti_parity_v1.csv',
    'information': 'btc15_information_frames_v1.jsonl',
}

def _csv_rows(path):
    with Path(path).open(newline='') as f:
        return list(csv.DictReader(f))

def _truth(v):
    return str(v).strip().lower() in ('true','1','yes')

def production_contract_scorecard(data_dir, ticker, target=None):
    """Score only deployed-writer schemas; historical filenames are never discovered."""
    root=Path(data_dir)
    info=contract_information(root/PRODUCTION_EVIDENCE_FILES['information'],ticker)
    final_rows=_csv_rows(root/PRODUCTION_EVIDENCE_FILES['final'])
    early_rows=_csv_rows(root/PRODUCTION_EVIDENCE_FILES['early'])
    coverage_rows=_csv_rows(root/PRODUCTION_EVIDENCE_FILES['scalp_coverage'])
    scalp_rows=_csv_rows(root/PRODUCTION_EVIDENCE_FILES['scalp_events'])
    profit_rows=_csv_rows(root/PRODUCTION_EVIDENCE_FILES['profit'])
    settlement_rows=_csv_rows(root/PRODUCTION_EVIDENCE_FILES['settlement'])

    final=classify_final(final_rows,ticker)
    early_contract=[r for r in early_rows if r.get('contract')==ticker]
    if not early_contract:
        early={'status':'MISSING','qualified':[]}
    else:
        qualified=[r for r in early_contract if _truth(r.get('provisional_candidate'))]
        early={'status':'QUALIFIED' if qualified else 'PASS','qualified':qualified}

    coverage=[r for r in coverage_rows if r.get('contract')==ticker]
    scalp_contract=[r for r in scalp_rows if r.get('contract')==ticker]
    scalp={'status':'QUALIFIED','events':scalp_contract} if scalp_contract else (
        {'status':'PASS','events':[]} if coverage else {'status':'MISSING','events':[]}
    )
    profit_contract=[r for r in profit_rows if r.get('contract')==ticker]
    if scalp['status']=='QUALIFIED':
        profit={'status':'RECORDED','events':profit_contract} if profit_contract else {'status':'MISSING','events':[]}
    else:
        profit={'status':'NOT_APPLICABLE','events':[]}

    settlements=[r for r in settlement_rows if r.get('contract')==ticker and
                 _truth(r.get('final60_complete')) and int(float(r.get('final60_count') or 0))==60]
    if target is not None:
        settlements=[r for r in settlements if r.get('target') not in (None,'') and
                     abs(float(r['target'])-float(target)) < 1e-6]
    settlement={'status':'COMPLETE','settlement':settlements[-1]} if settlements else {'status':'MISSING','settlement':None}

    missing=[]
    for name,value in (('FINAL',final),('EARLY',early),('SCALP',scalp),
                       ('PROFIT_PROTECTION',profit),('SETTLEMENT',settlement)):
        if value['status']=='MISSING': missing.append(name)
    if not info: missing.append('INFORMATION')
    return {'ticker':ticker,'status':'COMPLETE' if not missing else 'INCOMPLETE',
            'missing':missing,'information':info,'final':final,'early':early,
            'scalp':scalp,'profit_protection':profit,'settlement':settlement}


def read_native_cohort(path, ticker):
    rows=[]
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        row=json.loads(line)
        if row.get('schema')!='BTC15_COHORT_NATIVE_V1':
            raise ValueError('Unexpected native cohort schema')
        if row.get('signal_only') is not True or row.get('orders') is not False:
            raise ValueError('Native cohort invariant failed')
        if row.get('contract')==ticker:
            rows.append(row)
    if not rows:
        raise ValueError('MISSING_NATIVE_COHORT_EVIDENCE')
    rows.sort(key=lambda r:r['timestamp_utc'])
    return rows
