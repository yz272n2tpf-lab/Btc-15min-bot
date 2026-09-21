#!/usr/bin/env python3
"""One preregistered hypothesis per lane. Offline only; no network/order code."""
from __future__ import annotations
import argparse, csv, hashlib, json, math
from bisect import bisect_left, bisect_right
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

EPS = 1e-9
CLEAN_BOUNDARY = '2026-09-20T19:05:17.147189+00:00'
EXPECTED = {
    'kalshi_scalp_shadow_snapshots_v1.csv': 'd7c2dd36a5e0be197f5304fff0117f6fe340924e2436c60daf70806d84b00c4b',
    'kalshi_early_conf_shadow_v1_2.csv': 'b49b55215a0ae1704cdea1f9aaf1f5db2edcab72eaf3576d68fbae3aa77a43a2',
    'subminute_official_truth_cache.csv': '50915c34044658c0a9871c04a57290bb3e7987ef8414aa51cc48ef79f927fab7',
    'scalp_move_shadow_v1_events.csv': '47148d03418810fb96985d8f5db9e5f062d963b42fac8cfd062599118d43c437',
}

def num(x):
    try:
        v=float(x)
        return v if math.isfinite(v) else None
    except (ValueError,TypeError): return None

def epoch(s): return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def iso(t): return datetime.fromtimestamp(t, timezone.utc).isoformat()
def valid_quote(b,a): return b is not None and a is not None and 0 <= b <= a <= 1 and a > 0
def av(xs): return mean(xs) if xs else None
def med(xs): return median(xs) if xs else None
def rate(a,b): return a/b if b else None

def read_source(root,name):
    # Exact allowlist: changing a file or adding an input requires a new preregistration.
    assert name in EXPECTED
    raw=(root/'sources'/name).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==EXPECTED[name], 'Source fingerprint mismatch: '+name
    rows=list(csv.DictReader(raw.decode('utf-8').splitlines()))
    for r in rows:
        assert None not in r and None not in r.values(), 'Malformed CSV'
        if r.get('timestamp_utc'):
            r['_t']=epoch(r['timestamp_utc'])
            assert r['_t'] < epoch(CLEAN_BOUNDARY), 'Validation boundary violation'
    return rows, {'file':name,'bytes':len(raw),'sha256':EXPECTED[name],'rows':len(rows)}

def groups(rows):
    by=defaultdict(list)
    for r in rows: by[r['contract']].append(r)
    for rs in by.values(): rs.sort(key=lambda r:r['_t'])
    return by

def chronological_blocks(contracts,by):
    ordered=sorted(contracts,key=lambda c:by[c][0]['_t'])
    n=len(ordered)
    return {c:min(2,i*3//n) for i,c in enumerate(ordered)}

def measure(entry_time,ask,bid,points):
    """Later executable BID only. Entry spread affects MAE, never future MFE/hits."""
    p=sorted([(t,b) for t,b in points if t>entry_time and b is not None and 0<=b<=1])
    out={'future_points':len(p),'mfe_c':None,'mae_c':100*(bid-ask),
         'armed':False,'exit_time':None,'exit_gain_c':None,'exit_peak_c':None,
         'pre_exit_mfe_c':None,'last_time':p[-1][0] if p else None}
    for v in (5,10,15,20): out[f'hit{v}']=False; out[f't{v}_sec']=None
    peak=bid-ask
    before_exit=[]
    for t,b in p:
        g=b-ask
        out['mfe_c']=100*g if out['mfe_c'] is None else max(out['mfe_c'],100*g)
        out['mae_c']=min(out['mae_c'],100*g)
        for v in (5,10,15,20):
            if not out[f'hit{v}'] and g >= v/100-EPS:
                out[f'hit{v}']=True; out[f't{v}_sec']=t-entry_time
        if out['exit_time'] is None:
            peak=max(peak,g); before_exit.append(g)
            if peak>=.05-EPS: out['armed']=True
            if out['armed'] and peak-g>=.04-EPS:
                out['exit_time']=t;out['exit_gain_c']=100*g;out['exit_peak_c']=100*peak
    out['pre_exit_mfe_c']=100*max(before_exit) if before_exit else None
    return out

def continuous(t0,points,tend,limit=10):
    ts=sorted(set(t for t,_ in points if t0<t<=tend))
    if not ts or ts[-1] < tend-limit-EPS: return False
    seq=[t0]+ts+[tend]
    return all(0<=b-a<=limit+EPS for a,b in zip(seq,seq[1:]))

def early_signals(rows):
    """Feature-only online state. No outcome/settlement fields accessed."""
    states={};history=[];signals=[];previous=None
    for i,r in enumerate(rows):
        t=r['_t'];p=num(r['btc_price']);left=num(r['seconds_left'])
        if previous is not None and t-previous>10: states={};history=[]
        previous=t
        history=[x for x in history if x['_t']>=t-30]
        hits=[]
        for side,s in [('UP',1),('DOWN',-1)]:
            if p is None or left is None or not 360<=left<=660:
                states.pop(side,None);continue
            x=s*p;a=num(r[side.lower()+'_ask']);b=num(r[side.lower()+'_bid'])
            st=states.get(side)
            if st and (t-st['start']>30 or x<st['level']-EPS):
                states.pop(side);st=None
            if st:
                if x>st['peak']+EPS:
                    if st['pulled']:
                        if valid_quote(b,a) and a<=.50+EPS and st['ask'] is not None and a<=st['ask']+.02+EPS:
                            hits.append({'side':side,'time':t,'row_index':i,'ask':a,'bid':b,'seconds_left':left,
                                'episode_start':st['start'],'breakout_level_signed':st['level'],'previous_peak_signed':st['peak'],
                                'episode_start_ask':st['ask'],'btc15_side':s*(num(r.get('btc_move_15s')) or 0),
                                'retest_time':st['retest_time']})
                        states.pop(side);st=None
                    else: st['peak']=x
                elif x<st['peak']-EPS:
                    st['pulled']=True
                    if st.get('retest_time') is None: st['retest_time']=t
            # Re-arm only when no existing episode; uses pre-row history.
            if st is None and history and t-history[0]['_t']>=25-EPS:
                prior=[s*num(h['btc_price']) for h in history if num(h['btc_price']) is not None]
                m=num(r.get('btc_move_15s'))
                if prior and m is not None and s*m>=8-EPS and x>max(prior)+EPS:
                    states[side]={'start':t,'level':max(prior),'peak':x,'ask':a,'pulled':False,'retest_time':None}
        if hits:
            hits.sort(key=lambda h:(-h['btc15_side'],0 if h['side']=='UP' else 1))
            signals.append(hits[0]);break
        history.append(r)
    return signals

def reference_signals(rows):
    for i,r in enumerate(rows):
        vals=[num(r.get(k)) for k in ['preferred_ask','preferred_fair','edge','seconds_left','btc_gap']]
        if any(v is None for v in vals):continue
        a,f,e,left,g=vals
        if 0<a<=.45+EPS and f>=.75-EPS and e>=.08-EPS and 120<=left<=600 and abs(g)>=25-EPS and r['preferred_side'] in ('UP','DOWN'):
            return {'contract':r['contract'],'time':r['_t'],'side':r['preferred_side'],'ask':a,'seconds_left':left}
    return None

def summary(recs,denom):
    complete=[r for r in recs if r['complete']]
    s={'calls':len(recs),'complete_calls':len(complete),'incomplete_calls':len(recs)-len(complete),
       'entry_contracts':len({r['contract'] for r in recs}),'coverage':rate(len({r['contract'] for r in recs}),denom),
       'denominator_contracts':denom,'avg_ask_c':av([100*r['ask'] for r in recs]),
       'median_ask_c':med([100*r['ask'] for r in recs]),
       'ideal_25_35_count':sum(.25-EPS<=r['ask']<=.35+EPS for r in recs),
       'le35_count':sum(r['ask']<=.35+EPS for r in recs),'le50_count':sum(r['ask']<=.50+EPS for r in recs),
       'avg_minutes_left':av([r['seconds_left']/60 for r in recs]),'median_minutes_left':med([r['seconds_left']/60 for r in recs]),
       'side_counts':dict(Counter(r['side'] for r in recs)),
       'complete_side_counts':dict(Counter(r['side'] for r in complete)),
       'mean_mfe_c':av([r['path']['mfe_c'] for r in complete if r['path']['mfe_c'] is not None]),
       'median_mfe_c':med([r['path']['mfe_c'] for r in complete if r['path']['mfe_c'] is not None]),
       'mean_mae_c':av([r['path']['mae_c'] for r in complete]),'median_mae_c':med([r['path']['mae_c'] for r in complete]),
       'worst_mae_c':min([r['path']['mae_c'] for r in complete],default=None),
       'observed_exits':sum(r['path']['exit_time'] is not None for r in recs),
       'exit_only_mean_gross_c':av([r['path']['exit_gain_c'] for r in recs if r['path']['exit_time'] is not None]),
       'armed_no_exit':sum(r['path']['armed'] and r['path']['exit_time'] is None for r in recs),
       'completed_never_armed':sum(not r['path']['armed'] for r in complete),
       'mean_entry_delay_sec':av([r.get('entry_delay_sec',0) for r in recs])}
    for v in (5,10,15,20):
        s[f'hit{v}_n']=sum(r['path'][f'hit{v}'] for r in complete)
        s[f'hit{v}_rate']=rate(s[f'hit{v}_n'],len(complete))
        hit_times=[r['path'][f't{v}_sec'] for r in complete if r['path'][f't{v}_sec'] is not None]
        s[f't{v}_median_sec']=med(hit_times);s[f't{v}_mean_sec']=av(hit_times)
    return s

def score_early(snapshots,early_rows,truth_rows):
    by=groups(snapshots);ref_by=groups(early_rows)
    eligible={c for c,rs in by.items() if max(float(r['seconds_left']) for r in rs)>=660 and min(float(r['seconds_left']) for r in rs)<=360}
    blocks=chronological_blocks(eligible,by)
    truth={r['contract']:r['result'] for r in truth_rows}
    refs={c:q for c,rs in ref_by.items() if (q:=reference_signals(rs))}
    entries=[];excluded=[];delayed=[]
    for c,rs in by.items():
        sigs=early_signals(rs)
        if not sigs:continue
        q=sigs[0];q.update(contract=c,block=blocks.get(c),entry_delay_sec=q['time']-q['episode_start'])
        side=q['side'].lower();t=q['time']
        pts=[(r['_t'],num(r[side+'_bid'])) for r in rs if r['_t']>t and valid_quote(num(r[side+'_bid']),num(r[side+'_ask']))]
        p120=[(tt,b) for tt,b in pts if tt<=t+120+EPS]
        q['path']=measure(t,q['ask'],q['bid'],p120)
        q['complete']=continuous(t,pts,t+120) and any(t+120<=tt<=t+130 for tt,_ in pts)
        q['remaining_path']=measure(t,q['ask'],q['bid'],pts)
        q['remaining_path_complete']=float(rs[-1]['seconds_left'])<=10 and continuous(t,pts,rs[-1]['_t'])
        q['settlement_secondary']=None if c not in truth else int((truth[c]=='yes')==(q['side']=='UP'))
        if c in refs:q['protected_reference']={**refs[c],'lead_seconds':refs[c]['time']-t}
        (entries if c in eligible else excluded).append(q)
        # Fixed one-observation reaction sensitivity. It does not change the causal signal.
        if c in eligible and q['row_index']+1<len(rs):
            nx=rs[q['row_index']+1];a=num(nx[side+'_ask']);b=num(nx[side+'_bid']);nt=nx['_t'];left=num(nx['seconds_left'])
            if nt-t<=10 and valid_quote(b,a) and a<=.5+EPS and a<=q['episode_start_ask']+.02+EPS and 360<=left<=660:
                pp=[(tt,bb) for tt,bb in pts if nt<tt<=nt+120+EPS]
                z={k:q[k] for k in ('contract','side','block')};z.update(time=nt,ask=a,bid=b,seconds_left=left,entry_delay_sec=nt-t,
                    path=measure(nt,a,b,pp),complete=continuous(nt,pts,nt+120) and any(nt+120<=tt<=nt+130 for tt,_ in pts))
                delayed.append(z)
    s=summary(entries,len(eligible));bs=[summary([r for r in entries if r['block']==k],sum(v==k for v in blocks.values())) for k in range(3)]
    gates={'complete_calls_ge20':s['complete_calls']>=20,'coverage_ge40pct':(s['coverage'] or 0)>=.40,
           'hit5_ge90pct':(s['hit5_rate'] or 0)>=.90,'hit10_ge80pct':(s['hit10_rate'] or 0)>=.80,
           'both_sides_ge5_complete':all(s['complete_side_counts'].get(side,0)>=5 for side in ('UP','DOWN')),
           'mean_and_median_ask_le40c':s['avg_ask_c'] is not None and s['avg_ask_c']<=40+EPS and s['median_ask_c']<=40+EPS,
           'all_ask_le50c':s['le50_count']==s['calls'],'mean_minutes_ge7':(s['avg_minutes_left'] or 0)>=7,
           'each_third_ge5_complete_and_hit10_ge70pct':all(b['complete_calls']>=5 and (b['hit10_rate'] or 0)>=.7 for b in bs)}
    both=[r for r in entries if 'protected_reference' in r]
    common=set(by)&set(ref_by)
    secondary=[r['settlement_secondary'] for r in entries if r['settlement_secondary'] is not None]
    rem=[{**r,'path':r['remaining_path'],'complete':r['remaining_path_complete']} for r in entries]
    report={'decision':'FROZEN DEVELOPMENT CANDIDATE' if all(gates.values()) else 'NO STABLE CANDIDATE',
            'hypothesis':'BREAKOUT_RETEST_RECLAIM_V1','source_contracts':len(by),'eligible_contracts':len(eligible),
            'ineligible_contracts':sorted(set(by)-eligible),'summary_120s':s,'chronological_thirds':bs,'gates':gates,
            'remaining_contract_path':summary(rem,len(eligible)), 'one_observation_delay':summary(delayed,len(eligible)),
            'protected_reference':{'reference_source_contracts':len(ref_by),'reference_calls':len(refs),'common_source_contracts':len(common),
              'reference_calls_on_common_contracts':sum(c in common for c in refs),
              'common_called_contracts':len(both),'earlier_than_reference':sum(r['protected_reference']['lead_seconds']>0 for r in both),
              'same_side_common_calls':sum(r['side']==r['protected_reference']['side'] for r in both),
              'median_lead_sec_common_calls':med([r['protected_reference']['lead_seconds'] for r in both]),
              'incremental_calls_in_shared_source_contracts':sum(r['contract'] in common and r['contract'] not in refs for r in entries)},
            'settlement_secondary':{'matched_calls':len(secondary),'same_side':sum(secondary),'same_side_rate':av(secondary),'unmatched_calls':len(entries)-len(secondary)},
            'excluded_contract_calls':len(excluded)}
    return report,entries,excluded,{'eligible':sorted(eligible),'all':sorted(by),'reference_all':sorted(ref_by),'truth_all':sorted(truth)}

def scalp_qualified(r):
    left=num(r.get('seconds_left'));m=num(r.get('btc30'))
    return r.get('side') in ('UP','DOWN') and left is not None and left>=120 and m is not None and m>=15-EPS

def movement_path(c,prs,res):
    t=c['_t'];a=num(c['entry_ask']);b=num(c['entry_bid'])
    if not valid_quote(b,a):return None,False,None
    end=res['_t'] if res else float('inf')
    pts=[(r['_t'],num(r['current_bid'])) for r in prs if t<r['_t']<=end and valid_quote(num(r['current_bid']),num(r['current_ask']))]
    out=measure(t,a,b,pts)
    complete=res is not None and continuous(t,pts,end)
    terminal=out['exit_time']
    if terminal is None and complete and not out['armed']:terminal=end
    return out,complete,terminal

def build_serial(candidates,paths,results):
    by=groups(candidates);opps=[]
    for contract,cs in by.items():
        after=-float('inf');idx=0
        for c in cs:
            if c['_t']<=after or not scalp_qualified(c):continue
            k=(contract,c['candidate_id']);p=paths.get(k,[]);res=results.get(k)
            out,complete,terminal=movement_path(c,p,res)
            idx+=1
            status='MISSING_PATH_BLOCKING'
            if out is not None:
                if out['exit_time'] is not None:status='EXIT'
                elif complete and not out['armed']:status='ENDED_UNARMED'
                elif out['armed']:status='ARMED_NO_EXIT_BLOCKING'
                else:status='INCOMPLETE_BLOCKING'
            opps.append({'contract':contract,'candidate_id':c['candidate_id'],'opportunity_index':idx,'candidate':c,'paths':p,'result':res,
                         'path':out,'complete':complete,'terminal':terminal,'status':status})
            if terminal is None:break
            after=terminal
    return opps

def value_entry(o):
    c=o['candidate'];t0=c['_t']
    first={'_t':t0,'current_ask':c['entry_ask'],'current_bid':c['entry_bid'],'seconds_left':c['seconds_left']}
    end=o['result']['_t'] if o['result'] else float('inf')
    for r in [first]+o['paths']:
        t=r['_t'];a=num(r.get('current_ask'));b=num(r.get('current_bid'))
        if t<t0 or t>min(t0+30,end):continue
        if valid_quote(b,a) and a<=.50+EPS:
            pts=[(p['_t'],num(p['current_bid'])) for p in o['paths'] if t<p['_t']<=end and valid_quote(num(p['current_bid']),num(p['current_ask']))]
            out=measure(t,a,b,pts);complete=o['result'] is not None and continuous(t,pts,end)
            term=out['exit_time']
            if term is None and complete and not out['armed']:term=end
            return {'contract':o['contract'],'candidate_id':o['candidate_id'],'opportunity_index':o['opportunity_index'],
                'time':t,'side':c['side'],'ask':a,'bid':b,'seconds_left':num(c['seconds_left'])-(t-t0),
                'entry_delay_sec':t-t0,'path':out,'complete':complete,'terminal':term,'source_movement_status':o['status']}
    return None

def scalp_lane(opps,supported_only,blocks):
    entries=[];reasons=Counter();busy={};audit=[]
    for o in sorted(opps,key=lambda o:o['candidate']['_t']):
        c=o['candidate'];t=c['_t'];contract=o['contract'];s=1 if c['side']=='UP' else -1
        btc=num(c.get('btc'));target=num(c.get('target'));gap=None if btc is None or target is None else s*(btc-target)
        if supported_only and (gap is None or gap<=0):reasons['ordinary_watch_tier']+=1;continue
        q=value_entry(o)
        if q is None:reasons['no_value_in_30s']+=1;continue
        # Compatibility rule: never overlap actionable positions, including delayed-value entries.
        if q['time']<=busy.get(contract,-float('inf')):reasons['prior_value_management_blocking']+=1;continue
        q.update(target_gap_side=gap,block=blocks[contract]);entries.append(q)
        busy[contract]=q['terminal'] if q['terminal'] is not None else float('inf')
    return entries,dict(reasons)

def score_scalp(rows):
    by=groups(rows);last=max(r['_t'] for r in rows)
    eligible={c for c,rs in by.items() if max(num(r['seconds_left']) or 0 for r in rs)>=780 and epoch(rs[0]['contract_close_utc'])<=last}
    blocks=chronological_blocks(eligible,by)
    candidates=[];paths=defaultdict(list);results={};keys=set();repeats=0
    for r in rows:
        k=(r['contract'],r['candidate_id']);typ=r['record_type']
        if typ=='CANDIDATE':
            assert k not in keys,'Duplicate CANDIDATE key'
            keys.add(k);candidates.append(r)
        elif typ=='PATH':paths[k].append(r)
        elif typ=='RESULT':
            assert k not in results,'Duplicate RESULT key'
            results[k]=r
    assert set(paths)<=keys and set(results)<=keys,'Orphan PATH/RESULT'
    for k,ps in paths.items():
        ps.sort(key=lambda r:r['_t'])
        assert len({p['_t'] for p in ps})==len(ps),'Duplicate path timestamp'
    opps=build_serial([c for c in candidates if c['contract'] in eligible],paths,results)
    control,cr=scalp_lane(opps,False,blocks);candidate,qr=scalp_lane(opps,True,blocks)
    cs=summary(control,len(eligible));qs=summary(candidate,len(eligible))
    key=lambda r:(r['contract'],r['candidate_id'])
    ci={key(r) for r in control};qi={key(r) for r in candidate}
    winners={key(r) for r in control if r['complete'] and r['path']['hit10']}
    opportunity_ret=rate(len(ci&qi),len(ci));win_ret=rate(len(winners&qi),len(winners))
    lift=None if cs['hit10_rate'] is None or qs['hit10_rate'] is None else qs['hit10_rate']-cs['hit10_rate']
    thirds=[{'control':summary([r for r in control if r['block']==b],sum(v==b for v in blocks.values())),
             'candidate':summary([r for r in candidate if r['block']==b],sum(v==b for v in blocks.values()))} for b in range(3)]
    gates={'control_complete_ge30':cs['complete_calls']>=30,'control_contracts_ge15':cs['entry_contracts']>=15,
           'opportunity_id_retention_ge80pct':(opportunity_ret or 0)>=.8,'winner_id_retention_ge90pct':(win_ret or 0)>=.9,
           'complete_count_retention_ge80pct':qs['complete_calls']>=.8*cs['complete_calls'],
           'hit10_lift_ge5pp':lift is not None and lift>=.05,
           'every_third_nonnegative_lift_and_ge5_candidate':all(t['candidate']['complete_calls']>=5 and t['candidate']['hit10_rate'] is not None and t['control']['hit10_rate'] is not None and t['candidate']['hit10_rate']>=t['control']['hit10_rate'] for t in thirds)}
    audit=[{k:o[k] for k in ('contract','candidate_id','opportunity_index','status','terminal','complete')} for o in opps]
    report={'decision':'FROZEN DEVELOPMENT CANDIDATE' if all(gates.values()) else 'NO STABLE CANDIDATE',
            'hypothesis':'TARGET_SUPPORTED_QUALITY_TIER_V1','observed_contracts':len(by),'eligible_contracts':len(eligible),
            'ineligible_contracts':sorted(set(by)-eligible),'original_candidates':len(candidates),'serial_opportunities':len(opps),
            'serial_states':dict(Counter(o['status'] for o in opps)),'serial_contracts':len({o['contract'] for o in opps}),
            'max_serial_opportunities_per_contract':max(Counter(o['contract'] for o in opps).values(),default=0),
            'control':cs,'candidate':qs,'control_nonentries':cr,'candidate_nonentries':qr,'chronological_thirds':thirds,
            'opportunity_id_retention':opportunity_ret,'winner_id_retention':win_ret,'control_winner_ids':len(winners),
            'retained_winner_ids':len(winners&qi),'retained_opportunity_ids':len(ci&qi),'incremental_candidate_ids':len(qi-ci),
            'hit10_lift':lift,'gates':gates,
            'entry_price_bands':{band:summary([r for r in control if lo-EPS<=r['ask']<=hi+EPS],len(eligible)) for band,lo,hi in [('under25',0,.24999),('25to35',.25,.35),('over35to50',.35001,.50)]}}
    return report,control,candidate,audit,{'eligible':sorted(eligible),'all':sorted(by)}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args();root=args.root;out=root/'results';out.mkdir(exist_ok=True)
    loaded={};inventory=[]
    for name in EXPECTED:
        rs,inv=read_source(root,name);loaded[name]=rs;inventory.append(inv)
    er,ee,ex,em=score_early(loaded['kalshi_scalp_shadow_snapshots_v1.csv'],loaded['kalshi_early_conf_shadow_v1_2.csv'],loaded['subminute_official_truth_cache.csv'])
    sr,sc,sq,sa,sm=score_scalp(loaded['scalp_move_shadow_v1_events.csv'])
    report={'mode':'DEVELOPMENT ONLY / SIGNAL ONLY / NO ORDERS','early':er,'scalp':sr,'source_inventory':inventory,
            'clean_window_read':False,'validation_eligibility':'PROVISIONAL; full prior-development membership unavailable',
            'preregistration_sha256':hashlib.sha256((root/'PREREGISTRATION.md').read_bytes()).hexdigest(),
            'replay_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    for name,data in [('report.json',report),('early_entries.json',ee),('early_incomplete_contract_entries.json',ex),('scalp_control_entries.json',sc),('scalp_candidate_entries.json',sq),('scalp_serial_audit.json',sa),('membership.json',{'early':em,'scalp':sm,'union_inspected_contracts':sorted(set(em['all']+em['reference_all']+em['truth_all']+sm['all']))})]:
        (out/name).write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2,sort_keys=True,allow_nan=False))

if __name__=='__main__': main()
