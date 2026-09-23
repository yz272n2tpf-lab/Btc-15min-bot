"""Past-available forward feature replay. No fitting, labels or production import.

Builds sampled partial BTC candles only from the durable collector's real source
and receipt timestamps. Warm-up and missing inputs stay WAIT. These sampled bars
are not a reconstruction of every exchange trade or completed-candle extrema.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from common_journal import scan
from fair_input_candidate import frame_at_cut, price_at_or_before, utc, OHLCV


def feature_builder(path):
    source=Path(path).read_text()
    nodes=[node for node in ast.walk(ast.parse(source)) if isinstance(node,ast.FunctionDef)
           and node.name=='_fair_build_snapshot']
    if len(nodes)!=1:raise ValueError('Ambiguous frozen feature source')
    env=dict(pd=pd,np=np,_fair_price_at_or_before=price_at_or_before)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<pure feature replay>','exec'),env)
    return env['_fair_build_snapshot']


def features_at(rows, decision, builder):
    cut=utc(decision['observed_utc']);close=utc(decision['close_utc'])
    opened=close-pd.Timedelta(minutes=15)
    if not opened<=cut<close:raise ValueError('Decision outside official contract')
    if decision.get('orders') is not False or decision.get('signal_only') is not True:
        raise ValueError('Unqualified source schema')
    source=utc(pd.Timestamp(decision['brti_source_ts_ms'],unit='ms',tz='UTC'))
    if not 0 <= (cut-source).total_seconds() <= 5:
        return None,'BRTI_SOURCE_NOT_FRESH'
    ticks=[]
    for row in rows:
        if utc(row['observed_utc'])>cut:continue
        if not row.get('btc_source_utc') or not row.get('btc_received_utc'):continue
        received=utc(row['btc_received_utc']);stamp=utc(row['btc_source_utc'])
        if received>cut:continue
        if stamp>received:raise ValueError('Future BTC source at receipt')
        if row['ticker']==decision['ticker'] and float(row['target'])!=float(decision['target']):
            raise ValueError('Fixed target changed within contract')
        ticks.append(dict(source_utc=stamp,observed_utc=received,price=row['btc_price']))
    empty=pd.DataFrame(columns=OHLCV+['source_utc'],index=pd.DatetimeIndex([],tz='UTC'))
    frame=frame_at_cut(empty,pd.DataFrame(ticks,columns=['source_utc','observed_utc','price']),cut)
    result=builder(frame,opened,float(decision['target']),_cut=cut)
    return result,'READY' if result is not None else 'INSUFFICIENT_PAST_AVAILABLE_HISTORY'


def replay(journal, source, start, end, stride_seconds=30):
    damage=[];rows=[];results=[];last={};builder=feature_builder(source)
    for member in scan(journal,damage):
        row=member['record']
        if row.get('record_type')=='SNAPSHOT_INPUT':rows.append(row)
    rows.sort(key=lambda row:utc(row['observed_utc']))
    for decision in rows:
        cut=utc(decision['observed_utc']);ticker=decision['ticker']
        if not utc(start)<=cut<utc(end):continue
        if ticker in last and (cut-last[ticker]).total_seconds()<stride_seconds:continue
        last[ticker]=cut
        try:
            features,status=features_at(rows,decision,builder)
        except ValueError as exc:
            features,status=None,'INVALID_INPUT:'+str(exc)
        results.append(dict(ticker=ticker,observed_utc=cut.isoformat(),status=status,features=features))
    return dict(scope='Forward feature integrity only; not model performance or complete market coverage',
                source_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),
                stride_seconds=stride_seconds,journal_damage=damage,decisions=results,
                fitted=False,production_changed=False,orders=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('journal',type=Path)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--start',required=True)
    parser.add_argument('--end',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=replay(args.journal,args.source,args.start,args.end)
    with args.output.open('x')as stream:json.dump(result,stream,indent=2,allow_nan=False)
    from collections import Counter
    print(json.dumps(dict(decisions=len(result['decisions']),statuses=dict(Counter(x['status']for x in result['decisions'])),orders=False)))
