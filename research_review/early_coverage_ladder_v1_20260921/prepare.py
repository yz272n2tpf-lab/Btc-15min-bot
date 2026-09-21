#!/usr/bin/env python3
"""Read only pinned historical files. Network is restricted to allowlisted old market GETs."""
import argparse, concurrent.futures, hashlib, json, math, re, subprocess, time, urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = '13c8988fed8c97479203910f5620df64826246f3'
FREEZE = '34edb8c30e34f9614bfb44e21b078c764bcda0a9'
CUTOFF = pd.Timestamp('2026-09-07T00:00:00Z')
SOURCES = ['union_optimizer_processed_snapshot_cache.csv', 'brti_calibration_results.csv',
 'kalshi_scalp_shadow_snapshots_v1.csv','kalshi_early_conf_shadow_v1.csv',
 'kalshi_early_conf_shadow_v1_1.csv','kalshi_early_conf_shadow_v1_2.csv',
 'kalshi_direct_brti_parity_v1.csv','kalshi_subminute_unified_v1_1.csv',
 'subminute_official_truth_cache.csv','kalshi_official_settlement_check.csv',
 'subminute_early_dataset_v1.csv']

def close_time(ticker):
    m = re.fullmatch(r'KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-\d{2}', ticker)
    if not m: raise ValueError('Invalid contract: '+str(ticker))
    yy,mm,dd,h,mn=m.groups()
    months='JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC'.split()
    return pd.Timestamp(year=2000+int(yy),month=months.index(mm)+1,day=int(dd),
        hour=int(h),minute=int(mn),tz=ZoneInfo('America/New_York')).tz_convert('UTC')

def read(name):
    d=pd.read_csv(ROOT/name,low_memory=False)
    d['source_row']=np.arange(2,len(d)+2)
    return d

def inventory():
    files=[]; tickers=set()
    for name in SOURCES:
        p=ROOT/name
        pinned=subprocess.check_output(['git','show',BASE+':'+name],cwd=ROOT)
        if hashlib.sha256(pinned).digest()!=hashlib.sha256(p.read_bytes()).digest():
            raise ValueError('Source differs from pinned commit: '+name)
        d=read(name); k='contract' if 'contract' in d else 'ticker'
        ts='timestamp_utc' if 'timestamp_utc' in d else 'snapshot_utc' if 'snapshot_utc' in d else None
        item={'path':name,'source_commit':BASE,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
              'bytes':p.stat().st_size,'rows':len(d),'contracts':d[k].nunique()}
        if ts: item.update(first_timestamp=str(d[ts].min()),last_timestamp=str(d[ts].max()))
        files.append(item)
        if name in [SOURCES[0],SOURCES[2],SOURCES[7]]: tickers.update(d[k])
    assert all(close_time(t)<CUTOFF for t in tickers)
    result={'base_commit':BASE,'preregistration_commit':FREEZE,'cutoff_exclusive':str(CUTOFF),
            'files':files,'official_allowlist':sorted(tickers,key=close_time)}
    (HERE/'source_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def fetch_labels(tickers):
    out=HERE/'official';out.mkdir(exist_ok=True)
    def one(ticker):
        assert close_time(ticker)<CUTOFF
        p=out/(ticker+'.json')
        if p.exists(): return ticker,'cached'
        url='https://api.elections.kalshi.com/trade-api/v2/markets/'+ticker
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url,timeout=20) as r: obj=json.load(r)
                m=obj['market']
                assert m['ticker']==ticker
                assert pd.Timestamp(m['close_time'])==close_time(ticker)
                assert m['status'] in ['settled','finalized'] and m['result'] in ['yes','no']
                receipt={'url':url,'retrieved_utc':pd.Timestamp.now(tz='UTC').isoformat(),'response':obj}
                p.write_text(json.dumps(receipt,sort_keys=True)+'\n')
                return ticker,'ok'
            except Exception as e:
                error=type(e).__name__+': '+str(e)
                if attempt<2:time.sleep(0.25*(attempt+1))
        return ticker,error
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        result=list(pool.map(one,tickers))
    (HERE/'label_retrieval.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Historical official labels',len(result),'unavailable',sum(s not in ['ok','cached'] for _,s in result),flush=True)

def truth(tickers):
    archive={}; conflicts=[]
    for name,k in [(SOURCES[1],'ticker'),(SOURCES[8],'contract'),(SOURCES[9],'ticker')]:
        for r in read(name).to_dict('records'):
            if r[k] not in tickers or str(r.get('result')).lower() not in ['yes','no']:continue
            v=str(r['result']).lower()
            if r[k] in archive and archive[r[k]][0]!=v:conflicts.append({'contract':r[k],'kind':'archive_disagreement'})
            archive[r[k]]=(v,name)
    rows=[]
    for t in tickers:
        p=HERE/'official'/(t+'.json');target=None
        if p.exists():
            m=json.loads(p.read_text())['response']['market'];v=m['result'];src='official/'+p.name
            target=m.get('floor_strike')
            if t in archive and archive[t][0]!=v:conflicts.append({'contract':t,'kind':'official_archive_disagreement'})
        elif t in archive:v,src=archive[t]
        else:v=None;src='UNRESOLVED'
        rows.append({'contract':t,'official_side':{'yes':'UP','no':'DOWN'}.get(v),
                     'truth_source':src,'official_target':target})
    (HERE/'label_conflicts.json').write_text(json.dumps(conflicts,indent=2)+'\n')
    return pd.DataFrame(rows)

def backward_join(left,right,prefix):
    """Never access future rows. Contract+target identity is enforced after asof."""
    parts=[]
    valuecols=[c for c in right if c not in ['contract','timestamp','source_row']]
    for contract,g in left.groupby('contract',sort=False):
        h=right[right.contract==contract].sort_values('timestamp').drop_duplicates('timestamp',keep='last')
        g=g.sort_values('timestamp')
        if h.empty:
            for c in valuecols:g[prefix+c]=np.nan
            g[prefix+'lag']=np.nan
        else:
            h=h.drop(columns=['contract','source_row'],errors='ignore').rename(columns={c:prefix+c for c in valuecols})
            h=h.rename(columns={'timestamp':prefix+'timestamp'})
            g=pd.merge_asof(g,h,left_on='timestamp',right_on=prefix+'timestamp',direction='backward',tolerance=pd.Timedelta(seconds=5))
            lag=(g.timestamp-g[prefix+'timestamp']).dt.total_seconds()
            bad=(g.target-g[prefix+'target']).abs()>0.01
            if bad.any():
                for c in valuecols:
                    g[prefix+c]=g[prefix+c].where(~bad)
            g[prefix+'lag']=lag.where(~bad)
        parts.append(g)
    return pd.concat(parts,ignore_index=True)

def bools(x):return x.astype(str).str.lower().isin(['true','1','1.0'])

def raw_wide():
    d=read(SOURCES[2]);d['timestamp']=pd.to_datetime(d.timestamp_utc,utc=True)
    conf=pd.concat([read(n) for n in SOURCES[3:6]],ignore_index=True)
    conf['timestamp']=pd.to_datetime(conf.timestamp_utc,utc=True)
    conf=conf[['contract','timestamp','target','preferred_side','preferred_fair','edge']]
    d=backward_join(d,conf,'conf_')
    b=read(SOURCES[6]);b['timestamp']=pd.to_datetime(b.timestamp_utc,utc=True)
    b=b[['contract','timestamp','target','brti_gap_to_target','brti_age_seconds','direct_brti_ready']]
    d=backward_join(d,b,'b_')
    frames=[]
    for side,sign,key in [('UP',1,'up'),('DOWN',-1,'down')]:
        q=pd.DataFrame({'contract':d.contract,'timestamp':d.timestamp,'side':side,
          'ask':d[key+'_ask'],'bid':d[key+'_bid'],'gap':sign*d.btc_gap,
          'price':d.btc_price,'target':d.target,'remaining':d.seconds_left/60,
          'preferred':d.conf_preferred_side,'preferred_fair':d.conf_preferred_fair,
          'edge':d.conf_edge,'fair':np.where(d.conf_preferred_side==side,d.conf_preferred_fair,1-d.conf_preferred_fair),
          'brti_gap':sign*d.b_brti_gap_to_target,'brti_age':d.b_brti_age_seconds+d.b_lag,
          'brti_ready':bools(d.b_direct_brti_ready),'source':SOURCES[2],'source_row':d.source_row})
        frames.append(q)
    return pd.concat(frames,ignore_index=True)

def raw_unified():
    d=read(SOURCES[7])
    return pd.DataFrame({'contract':d.contract,'timestamp':pd.to_datetime(d.timestamp_utc,utc=True),
      'side':d.side,'ask':d.side_ask,'bid':d.side_bid,'gap':d.btc_gap_side,'price':d.btc_price,
      'target':d.target,'remaining':d.minutes_left,'preferred':d.preferred_fair_side,
      'preferred_fair':d.preferred_fair,'edge':d.preferred_edge,'fair':d.side_fair,
      'brti_gap':d.brti_gap_side,'brti_age':d.brti_age_seconds,'brti_ready':bools(d.brti_ready),
      'source':SOURCES[7],'source_row':d.source_row})

def raw_sigma(g):
    t=g.timestamp.astype('int64').to_numpy()/1e9;p=g.price.to_numpy();result=np.full(len(g),np.nan)
    for i in range(len(g)):
        j=np.searchsorted(t,t[i]-120,side='left');ts=t[j:i+1];ps=p[j:i+1]
        if len(ts)<10 or ts[-1]-ts[0]<90 or np.diff(ts).max()>15 or not np.isfinite(ps).all():continue
        span=(ts[-1]-ts[0])/60
        result[i]=max(10,math.sqrt(np.sum(np.diff(ps)**2)/span),(ps.max()-ps.min())/math.sqrt(span))
    return result

def histories(d):
    parts=[]
    for _,g in d.groupby(['contract','side'],sort=False):
        g=g.sort_values('timestamp').copy();g['sigma']=raw_sigma(g)
        times=g.timestamp.astype('int64').to_numpy()/1e9
        for horizon in [15,30]:
            ids=np.searchsorted(times,times-horizon,side='right')-1
            ok=(ids>=0)&((times-horizon-times[np.maximum(ids,0)])<=5)
            for c in ['fair','ask']:
                a=g[c].to_numpy();prior=np.where(ok,a[np.maximum(ids,0)],np.nan)
                g[f'{c}_delta{horizon}']=a-prior
        parts.append(g)
    return pd.concat(parts,ignore_index=True)

def august():
    d=read(SOURCES[0]);parts=[]
    for side,sign,key in [('UP',1,'yes'),('DOWN',-1,'no')]:
        target=d.dist_target/d.dist_target_pct;price=target+d.dist_target
        sigma=np.maximum.reduce([np.full(len(d),10.),(price*d.vol5).to_numpy(),(d.range5/np.sqrt(5)).to_numpy()])
        q=pd.DataFrame({'contract':d.ticker,'timestamp':pd.to_datetime(d.snapshot_utc,utc=True),
          'side':side,'ask':d[key+'_ask'],'bid':d[key+'_bid'],'gap':sign*d.dist_target,
          'price':price,'target':target,'remaining':d.remaining,'preferred':d.preferred_side,
          'preferred_fair':d.preferred_fair,'edge':d.edge,'fair':d['fair_up' if side=='UP' else 'fair_down'],
          'sigma':sigma,'source':SOURCES[0],'source_row':d.source_row,'cohort':'august_replay'})
        parts.append(q)
    return pd.concat(parts,ignore_index=True)

def prepare():
    manifest=inventory();labels=truth(manifest['official_allowlist'])
    r=pd.concat([raw_wide(),raw_unified()],ignore_index=True)
    r=r.sort_values(['contract','side','timestamp','source','source_row']).drop_duplicates(['contract','side','timestamp'],keep='first')
    r=histories(r);r['cohort']='september_observed'
    d=pd.concat([august(),r],ignore_index=True)
    for c in ['ask','bid','gap','price','target','remaining','preferred_fair','edge','fair','sigma','brti_gap','brti_age','fair_delta15','fair_delta30','ask_delta30']:
        d[c]=pd.to_numeric(d[c],errors='coerce')
    d['close']=d.contract.map(close_time)
    assert d.close.max()<CUTOFF
    assert (d.timestamp<d.close).all()
    d['clock_error_seconds']=((d.close-d.timestamp).dt.total_seconds()-60*d.remaining).abs()
    d['valid_clock']=(d.clock_error_seconds<=2)
    d['valid_quote']=d.ask.between(0.0000001,1)&d.bid.between(0,1)&(d.bid<=d.ask)
    d['quote_fair_valid']=d.fair.between(0,1)&d.preferred_fair.between(.5,1)
    d['row_id']=d.source+':'+d.source_row.astype(str)+':'+d.side
    assert not d.row_id.duplicated().any()
    d.to_csv(HERE/'features.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    labels.to_csv(HERE/'labels.csv',index=False)
    quality=[]
    for cohort,g in d.groupby('cohort'):
        quality.append({'cohort':cohort,'rows':len(g),'contracts':g.contract.nunique(),
          'bad_clock_rows':int((~g.valid_clock).sum()),'bad_quote_rows':int((~g.valid_quote).sum()),
          'nonmissing_sigma':int(g.sigma.notna().sum()),'nonmissing_fair':int(g.fair.notna().sum()),
          'nonmissing_brti':int(g.brti_gap.notna().sum())})
    (HERE/'data_quality.json').write_text(json.dumps(quality,indent=2)+'\n')
    print('Features prepared',len(d),'rows; labels',labels.official_side.notna().sum(),'/',len(labels),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--fetch-labels',action='store_true');args=ap.parse_args()
    m=inventory()
    if args.fetch_labels:fetch_labels(m['official_allowlist'])
    else:prepare()
