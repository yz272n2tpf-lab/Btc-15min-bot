#!/usr/bin/env python3
"""Offline-only scoring of the preregistered tournament. No network or production imports."""
import json, math
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PRIORITY={'T1':0,'A':1,'B':2,'C':3}
LADDERS={'L1':['T1','A','B'],'L2':['T1','B','C'],'L3':['T1','A','C']}

def masks(d):
    valid=d.valid_clock&d.valid_quote
    t1=valid&(d.side==d.preferred)&d.preferred_fair.between(.75,1)&(d.ask<=.45)&(d.edge>=.08)&d.remaining.between(2,10)&(d.gap.abs()>=25)
    common=valid&(d.ask<=.5)&((d.ask-d.bid)<=.05+1e-12)&d.remaining.between(4,10)
    z=d.gap/(d.sigma*np.sqrt(d.remaining.clip(lower=.0001)))
    a=common&(d.gap>0)&(z>=1.5)
    b=common&(d.gap>=25)&(d.brti_gap>=25)&((d.brti_gap-d.gap).abs()<=15)&(d.brti_ready==True)&d.brti_age.between(0,2)
    c=common&(d.side==d.preferred)&d.fair.between(.75,1)&(d.fair_delta30>=.10)&(d.fair_delta15>=0)&(d.ask_delta30<=0)&(d.gap>0)
    return {'T1':t1,'A':a,'B':b,'C':c}

def first_calls(d):
    if d.empty:return d.copy()
    # This function is used within one family. Opposite-side ties are ambiguous.
    bad=d.groupby(['contract','timestamp']).side.nunique()
    ambiguous=set(bad[bad>1].index)
    if ambiguous:d=d.loc[[ (r.contract,r.timestamp) not in ambiguous for r in d.itertuples()]]
    return d.sort_values(['timestamp','row_id']).drop_duplicates('contract',keep='first').copy()

def causal_union(parts):
    d=pd.concat(parts,ignore_index=True)
    if d.empty:return d
    d['priority']=d.family.map(PRIORITY)
    return d.sort_values(['timestamp','priority','row_id']).drop_duplicates('contract',keep='first').copy()

def attributed(parts):
    seen=set();out=[]
    for p in parts:
        q=p[~p.contract.isin(seen)].copy();out.append(q);seen.update(p.contract)
    return out

def wilson(w,n):
    if not n:return [None,None]
    z=1.959963984540054;p=w/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den;delta=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [mid-delta,mid+delta]

def stats(d,denom):
    n=len(d);settled=d.official_side.notna();ns=int(settled.sum());wins=int((d.loc[settled,'side']==d.loc[settled,'official_side']).sum())
    def avg(c):return float(d[c].mean()) if n else None
    def med(c):return float(d[c].median()) if n else None
    bands={'ideal25_35':d.ask.between(.25,.35),'le40':d.ask<=.40,'le50':d.ask<=.50}
    s={'calls':n,'denominator':denom,'coverage':n/denom if denom else None,'settled':ns,'correct':wins,
       'wrong':ns-wins,'unresolved':n-ns,'accuracy':wins/ns if ns else None,'wilson95':wilson(wins,ns),
       'ask_mean_c':100*avg('ask') if n else None,'ask_median_c':100*med('ask') if n else None,
       'minutes_mean':avg('remaining'),'minutes_median':med('remaining')}
    for key,mask in bands.items():s[key+'_count']=int(mask.sum());s[key+'_rate']=float(mask.mean()) if n else None
    for side in ['UP','DOWN']:
        q=d[d.side==side];valid=q.official_side.notna();k=int(valid.sum());w=int((q.loc[valid,'official_side']==side).sum())
        s[side+'_calls']=len(q);s[side+'_correct']=w;s[side+'_settled']=k;s[side+'_accuracy']=w/k if k else None
    return s

def detailed(d,membership):
    s=stats(d,len(membership))
    for half in [1,2]:
        ids=set(membership.loc[membership.half==half,'contract'])
        s['half'+str(half)]=stats(d[d.contract.isin(ids)],len(ids))
    s['sources']={src:stats(d[d.source==src],len(membership)) for src in sorted(d.source.unique())}
    return s

def tier_gate(s):
    def ge(key,x):return s[key] is not None and s[key]>=x
    return bool(ge('calls',30) and ge('accuracy',.93) and s['wilson95'][0]>=.85 and
        all(s['half'+str(h)]['calls']>=10 and (s['half'+str(h)]['accuracy'] or 0)>=.90 for h in [1,2]) and
        s['UP_calls']>0 and s['DOWN_calls']>0 and s['unresolved']==0 and s['le50_rate']==1 and
        s['ask_mean_c']<=40 and s['minutes_mean']>=6)

def ladder_gate(s,increments):
    return bool(s['calls']>=100 and (s['coverage'] or 0)>=.70 and (s['accuracy'] or 0)>=.93 and
        all(s['half'+str(h)]['calls']>=40 and (s['half'+str(h)]['accuracy'] or 0)>=.90 for h in [1,2]) and
        s['UP_calls']>=10 and s['DOWN_calls']>=10 and s['unresolved']==0 and s['le50_rate']==1 and
        s['ask_mean_c']<=40 and s['minutes_mean']>=6 and all(tier_gate(x) for x in increments))

def oracle(d,membership,minimum):
    d=d[d.contract.isin(membership.contract)&d.valid_clock&d.valid_quote&d.remaining.between(minimum,10)&(d.ask<=.50)]
    affordable=set(d.contract);winners=set(d.loc[d.side==d.official_side,'contract'])
    unresolved=set(d.loc[d.official_side.isna(),'contract'])
    n=len(membership);ceiling=min(len(affordable),math.floor((len(winners)+len(unresolved))/.93+1e-12))
    return {'minimum_minutes':minimum,'denominator':n,'any_affordable_contracts':len(affordable),
        'winner_affordable_contracts':len(winners),'unresolved_affordable_contracts':len(unresolved),
        'perfect_accuracy_oracle_coverage':len(winners)/n if n else None,
        'max_calls_at_93pct_accuracy':ceiling,'max_coverage_at_93pct_accuracy':ceiling/n if n else None,
        'winner_contracts':sorted(winners),'affordable_contracts':sorted(affordable)}

def main():
    d=pd.read_csv(HERE/'features.csv.gz',low_memory=False)
    d['timestamp']=pd.to_datetime(d.timestamp,utc=True,format='mixed');d['close']=pd.to_datetime(d.close,utc=True,format='mixed')
    labels=pd.read_csv(HERE/'labels.csv');assert not labels.contract.duplicated().any()
    d=d.merge(labels,on='contract',how='left',validate='many_to_one')
    all_metrics=[];all_calls=[];memberships=[];result={}
    for cohort,g in d.groupby('cohort'):
        eligible=g[g.valid_clock&g.valid_quote&g.remaining.between(2,10)]
        mem=eligible[['contract','close']].drop_duplicates().sort_values('close').reset_index(drop=True)
        mem['half']=np.where(np.arange(len(mem))<len(mem)//2,1,2);mem['cohort']=cohort;memberships.append(mem)
        g=g[g.contract.isin(mem.contract)].copy()
        families={}
        for family,mask in masks(g).items():
            q=first_calls(g[mask]);q['family']=family;families[family]=q
        report={'observed_contracts':d[d.cohort==cohort].contract.nunique(),'eligible_contracts':len(mem),
                'families':{},'ladders':{},'oracle':{}}
        def add(name,frame,kind):
            summary=detailed(frame,mem)
            all_metrics.append({'cohort':cohort,'name':name,'kind':kind,**summary})
            if len(frame):
                q=frame.copy();q['policy']=name;q['kind']=kind;all_calls.append(q)
            return summary
        for family,q in families.items():
            report['families'][family]=add('family_'+family,q,'standalone')
            if family!='T1':
                inc=q[~q.contract.isin(families['T1'].contract)]
                s=add('increment_'+family+'_beyond_T1',inc,'incremental');s['eligible_for_validation']=tier_gate(s)
                report['families'][family]['incremental_beyond_T1']=s
        for name,order in LADDERS.items():
            parts=[families[x] for x in order];increments=attributed(parts);item={'order':order,'prefixes':{},'increments':{}}
            for i,q in enumerate(increments):
                s=add(name+'_tier'+str(i+1)+'_increment',q,'incremental')
                if i:s['eligible_for_validation']=tier_gate(s)
                item['increments']['tier'+str(i+1)]=s
            for i in [1,2,3]:
                attr=pd.concat(increments[:i],ignore_index=True);causal=causal_union(parts[:i])
                assert set(attr.contract)==set(causal.contract) and not causal.contract.duplicated().any()
                sa=add(name+'_prefix'+str(i)+'_attribution',attr,'retrospective_attribution')
                sc=add(name+'_prefix'+str(i)+'_causal',causal,'causal')
                pre=causal[causal.contract.isin(parts[0].contract)&(causal.family!='T1')]
                ref=parts[0].set_index('contract').side
                sc['preempted_T1_contracts']=len(pre)
                sc['preempted_T1_side_disagreements']=int((pre.side!=pre.contract.map(ref)).sum())
                item['prefixes'][str(i)]={'attribution':sa,'causal':sc}
            item['eligible_for_validation']=ladder_gate(item['prefixes']['3']['causal'],[item['increments']['tier2'],item['increments']['tier3']])
            report['ladders'][name]=item
        report['all_family_envelope']=add('all_family_envelope',causal_union(list(families.values())),'diagnostic')
        for minimum in [2,4]:report['oracle'][str(minimum)]=oracle(g,mem,minimum)
        report['decision']='CANDIDATE FOR FUTURE VALIDATION' if any(x['eligible_for_validation'] for x in report['ladders'].values()) else 'NO STABLE HIGH-COVERAGE EARLY LADDER'
        result[cohort]=report
    pd.concat(memberships).to_csv(HERE/'membership.csv',index=False)
    calls=pd.concat(all_calls,ignore_index=True)
    cols=['cohort','policy','kind','family','contract','timestamp','side','ask','remaining','gap','sigma',
          'preferred_fair','edge','brti_gap','brti_age','fair_delta15','fair_delta30','ask_delta30','official_side',
          'truth_source','source','source_row','row_id','target','official_target']
    calls[cols].to_csv(HERE/'per_call.csv',index=False)
    flat=[]
    for row in all_metrics:
        q={k:v for k,v in row.items() if k not in ['sources','half1','half2','wilson95']}
        q['wilson95_low'],q['wilson95_high']=row['wilson95']
        for half in [1,2]:
            for k,v in row['half'+str(half)].items():
                if k!='wilson95':q[f'half{half}_{k}']=v
        flat.append(q)
    pd.DataFrame(flat).to_csv(HERE/'metrics.csv',index=False)
    (HERE/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    for cohort,r in result.items():
        print(cohort,r['eligible_contracts'],'eligible;',r['decision'])
        for f,s in r['families'].items():print(f,'calls',s['calls'],'accuracy',s['accuracy'],'coverage',s['coverage'])
        for name,x in r['ladders'].items():
            s=x['prefixes']['3']['causal'];print(name,'causal',s['calls'],s['accuracy'],s['coverage'])
        print('Oracle ceilings',{k:v['max_coverage_at_93pct_accuracy'] for k,v in r['oracle'].items()})

if __name__=='__main__':main()
