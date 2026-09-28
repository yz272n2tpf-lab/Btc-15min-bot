"""Offline fitted-candidate connection to existing three-family numeric gates.

No published signal, model selection, live threshold change or order capability.
The candidate's input/model revision differs explicitly from the incumbent.
"""
import math
import numpy as np
import pandas as pd
from fair_input_candidate import utc


def gates(row, up_fair, down_fair):
    data=row['inputs'];features=row['features'];now=utc(row['observed_utc'])
    side='UP' if up_fair>=down_fair else 'DOWN'
    fair=max(up_fair,down_fair);ask=float(data[side.lower()+'_ask']);edge=fair-ask
    left=(utc(data['close_utc'])-now).total_seconds()/60
    btc_gap=float(data['btc_price'])-float(data['target'])
    brti_gap=float(data['brti_value'])-float(data['target'])
    age=(now-pd.Timestamp(data['brti_source_ts_ms'],unit='ms',tz='UTC')).total_seconds()
    quotes=[float(data[name])for name in ('up_bid','up_ask','down_bid','down_ask')]
    values=[float(data[name])for name in ('btc_price','brti_value','target')]
    if (not all(math.isfinite(v) and 0<=v<=1 for v in quotes)
            or not all(math.isfinite(v) and v>0 for v in values)
            or quotes[0]>quotes[1] or quotes[2]>quotes[3]):
        raise ValueError('Invalid quote/source values')
    source_ok=(0<=age<=5 and 0<left<=15 and data['quote_transport']=='timestamped_contiguous_ws'
               and utc(data['quote_validation_utc'])==now)
    btc_side='UP' if btc_gap>=0 else 'DOWN'
    brti_side='UP' if brti_gap>0 else ('DOWN' if brti_gap<0 else 'FLAT')
    required_gap=75. if left>6 else 50.
    raw=dict(
        early=ask<=.45 and fair>=.75 and edge>=.08 and 2<=left<=10 and abs(btc_gap)>=25,
        final=side==btc_side and left<=8 and fair>=.90 and abs(btc_gap)>=required_gap
              and features['dist_over_range5']>=1 and abs(brti_gap)>11 and side==brti_side,
        scalp=ask<=.70 and fair>=.52 and edge>=0 and 3<=left<=10 and abs(btc_gap)>=50)
    return dict(side=side,fair=fair,entry_ask=ask,edge=edge,minutes_left=left,
                raw_gates={k:bool(v)for k,v in raw.items()},
                input_qualified=bool(source_ok),qualified_input_gates={k:bool(v and source_ok)for k,v in raw.items()},
                actual_main_publication_verified=False,orders=False)


def predict(forest,sigmoid,feature_names,rows):
    ready=[r for r in rows if r['status']=='READY']
    if not ready:return []
    data=pd.DataFrame([r['features']for r in ready])[feature_names]
    if not np.isfinite(data.to_numpy()).all():raise ValueError('Nonfinite forward features')
    raw=forest.predict_proba(data)[:,1]
    flips=np.clip(sigmoid.predict_proba(raw.reshape(-1,1))[:,1],.001,.999)
    output=[]
    for row,flip in zip(ready,flips):
        up=1-float(flip) if row['features']['current_side']==1 else float(flip)
        output.append(dict(ticker=row['ticker'],observed_utc=row['observed_utc'],
                           up_fair=up,down_fair=1-up,**gates(row,up,1-up)))
    return output
