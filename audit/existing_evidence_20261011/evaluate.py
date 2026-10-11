"""Question-specific, descriptive evaluation of recovered evidence.

No fitting, threshold selection, orders, runtime import or network. Observed
decisions, partial numeric counterfactuals and quote scenarios stay separate.
Labels are used only after first-observation selection, never for entry timing.
"""
from __future__ import annotations
import csv, gzip, hashlib, json, math, re, statistics, tarfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

VARIANTS=('CURRENT_75_50','FIXED_50','FIXED_40','FIXED_30','FIXED_20','FIXED_10','NO_FIXED')
def epoch(x):
    if isinstance(x,(int,float)):return float(x)
    return datetime.fromisoformat(x.replace('Z','+00:00')).timestamp()
def num(x):
    try:
        v=float(x);return v if math.isfinite(v) else None
    except (TypeError,ValueError):return None
def truth(x):return x is True or str(x).lower() in ('true','1')
def wilson(k,n):
    if not n:return None
    z=1.959963984540054;p=k/n;d=1+z*z/n
    c=(p+z*z/(2*n))/d;w=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,c-w),min(1,c+w)]
def stats(rs):
    labeled=[r for r in rs if r.get('correct') is not None];n=len(labeled);k=sum(r['correct'] for r in labeled)
    ps=[r['p'] for r in labeled if r.get('p') is not None]
    return dict(selected_contracts=len(rs),labeled_contracts=n,correct=k,incorrect=n-k,
                accuracy=k/n if n else None,false_rate=(n-k)/n if n else None,
                wilson95=wilson(k,n),mean_p=statistics.mean(ps) if ps else None,
                brier=statistics.mean((r['p']-r['correct'])**2 for r in labeled if r.get('p') is not None) if ps else None,
                mean_seconds_left=statistics.mean(r['left'] for r in rs) if rs else None,
                median_seconds_left=statistics.median(r['left'] for r in rs) if rs else None)
def unique_rows(rows,keys):
    """Conflicting identity keys are excluded completely, never first-wins."""
    seen={};conflicts=set();duplicates=0
    for r in rows:
        k=tuple(r[x] for x in keys)
        if k in seen:
            if seen[k]!=r:conflicts.add(k)
            else:duplicates+=1
        else:seen[k]=r
    return [r for k,r in seen.items() if k not in conflicts],dict(duplicates=duplicates,conflicting_keys=len(conflicts))
def first_per_contract(rows,predicate):
    selected={}
    for r in sorted(rows,key=lambda r:r['time']):
        if predicate(r):selected.setdefault(r['contract'],r)
    return list(selected.values())
def distance(v,left):
    return (75 if left>360 else 50) if v=='CURRENT_75_50' else (0 if v=='NO_FIXED' else float(v.split('_')[1]))
def policy_table(rows,base_predicate):
    selected={v:first_per_contract(rows,lambda r:base_predicate(r) and abs(r['gap'])>=distance(v,r['left'])) for v in VARIANTS}
    base={r['contract']:r for r in selected['CURRENT_75_50']};out={}
    for v,rs in selected.items():
        added=[r for r in rs if r['contract'] not in base]
        deltas=[r['left']-base[r['contract']]['left'] for r in rs if r['contract'] in base]
        out[v]=dict(**stats(rs),additional=stats(added),by_side={s:stats([r for r in rs if r['side']==s]) for s in ('UP','DOWN')},
                    mean_earlier_seconds_common=statistics.mean(deltas) if deltas else None,records=rs)
    return out
def gate_diagnostics(rows,base_predicate):
    high=[r for r in rows if r['p']>=.90 and 0<r['left']<=480]
    short=[r for r in high if abs(r['gap'])<distance('CURRENT_75_50',r['left'])]
    sole=[r for r in short if base_predicate(r)]
    return dict(high_confidence_rows=len(high),high_confidence_contracts=len({r['contract']for r in high}),
        high_confidence_below_distance_rows=len(short),high_confidence_below_distance_contracts=len({r['contract']for r in short}),
        distance_only_blocked_visible_predicates_rows=len(sole),distance_only_blocked_contracts=len({r['contract']for r in sole}),
        volatility5_observation_range=[min(v),max(v)]if(v:=[r['vol5']for r in rows if r.get('vol5')is not None])else None)
def fee_scenario(p):return math.ceil((.07*p*(1-p)-1e-12)*100)/100
def usable_quote_observation(r,side,target):
    if r.get('target')!=target:return False
    bid=num(r.get(side.lower()+'_bid'));ask=num(r.get(side.lower()+'_ask'))
    if bid is None or ask is None or not 0<=bid<=ask<=1:return False
    b=r.get('brti') or {}
    if b.get('direct_brti_ready') is False:return False
    if b.get('brti_timestamp_utc'):
        age=epoch(r['timestamp_utc'])-epoch(b['brti_timestamp_utc'])
        if not 0<=age<=5:return False
    return True
def fixed_horizon_quote(seq, start, horizon, remaining, side, target):
    """First sampled BID at the specified horizon, never the future maximum.

    Ten-second tolerance/continuity is inherited from the archived analysis.
    This yields a quote observation, never proof of an executable fill.
    """
    if remaining<=horizon:return None
    path=sorted((x for x in seq if epoch(x['timestamp_utc'])>=start),key=lambda x:epoch(x['timestamp_utc']))
    later=next((x for x in path if epoch(x['timestamp_utc'])>=start+horizon),None)
    if later is None or epoch(later['timestamp_utc'])>start+horizon+10:return None
    prefix=[x for x in path if epoch(x['timestamp_utc'])<=epoch(later['timestamp_utc'])]
    if not prefix or epoch(prefix[0]['timestamp_utc'])!=start:return None
    if any(epoch(b['timestamp_utc'])-epoch(a['timestamp_utc'])>10 for a,b in zip(prefix,prefix[1:])):return None
    if not all(usable_quote_observation(x,side,target)for x in prefix):return None
    return later
def catalog_item(cat,suffix,sha_prefix=None):
    candidates=[x for x in cat if x['name'].endswith(suffix) and (sha_prefix is None or x['sha256'].startswith(sha_prefix))]
    if len(candidates)!=1:raise ValueError((suffix,len(candidates)))
    return candidates[0]

def main(w):
    root=w/'repo';out=root/'audit/existing_evidence_20261011';cache=w/'evidence-corpus'
    cat=json.loads((out/'corpus_inventory.json').read_text())['files'];result={}
    def rows(suffix,prefix=None):return list(csv.DictReader((cache/catalog_item(cat,suffix,prefix)['sha256']).open()))
    # Exact previous inventory, with per-dataset missing-field/capability accounting.
    old=json.loads((root/'audit/opportunity_integrity_20261011/final_distance_results.json').read_text())['inventory']['files']
    original=[];all_ids=set();obskeys=set()
    for x in old:
        p=root/x['file'];raw=list(csv.DictReader(p.open()));c=next(r for r in cat if r['sha256']==x['sha256']);cols=set(c['columns'])
        kind='derived research / selected calls'
        if 'official_result' in cols or x['file']=='subminute_official_truth_cache.csv':kind='outcomes'
        if x['file'].startswith(('kalshi_two_output_live_log','kalshi_early_conf_shadow')) or x['file'] in ['kalshi_live_fair_value_shadow_log.csv','kalshi_direct_brti_parity_v1.csv','kalshi_subminute_unified_v1_1.csv','overnight.csv','x.csv']:kind='recorded observations'
        if x['file']=='union_optimizer_processed_snapshot_cache.csv':kind='recomputed historical features/predictions'
        all_ids.update(c['contract_ids'])
        for r in raw:
            contract=r.get('contract')or r.get('ticker');t=r.get('timestamp_utc')or r.get('snapshot_utc')or r.get('call_time')
            if contract and t:obskeys.add((contract,t))
        original.append(dict(file=x['file'],sha256=x['sha256'],rows=c['rows'],unique_exact_rows=c['exact_unique_rows'],contracts=c['contracts'],kind=kind,
            has_timestamp=bool(c['time_ranges']),has_ask=bool(cols&{'preferred_ask','side_ask','up_ask','ask','preferred_kalshi_ask'}),
            has_bid=bool(cols&{'side_bid','up_bid','yes_bid','preferred_bid','bid'}),has_model_probability=bool(cols&{'fair_up','preferred_fair','fair_preferred','side_fair','initial_fair'}),
            has_range_ratio='dist_over_range5'in cols,has_brti=bool(cols&{'direct_brti','brti_value','brti_side'}),
            missing_native='native epoch/sequence, causal receipts, full book/feature/model binding',
            appropriate_use='descriptive counts/labels; selection-specific accuracy' if kind!='recorded observations' else 'timestamped observation/quote-path diagnostics; partial numeric policy screen',
            prohibited_claim='current native full replay or executable fills',time_ranges=c['time_ranges']))
    (out/'original_92_reconciliation.json').write_text(json.dumps(original,indent=2))
    result['old92']=dict(files=len(old),rows=sum(x['rows'] for x in original),distinct_contract_ids=len(all_ids),
        distinct_contract_time_keys=len(obskeys),note='Keys span differing schemas and selected/recomputed sources, NOT an independent evaluation sample.')

    # First locks from an unchanged read-only observer; exact published records.
    live=json.loads((out/'final_forward_state.json').read_text())['live'];locks=[]
    for r in live['settled_records']:
        locks.append(dict(contract=r['contract'],time=epoch(r['observed_at_utc']),side=r['side'],p=r['fair'],left=r['seconds_left'],ask=r['preferred_ask'],
                          correct=r['side']==r['official_side'],label=r['official_side'],raw_ready=r['raw_final_ready']))
    locks,dedup=unique_rows(locks,['contract'])
    result['final_observed']=dict(**stats(locks),dedup=dedup,first_utc=min(r['observed_at_utc'] for r in live['settled_records']),last_utc=max(r['observed_at_utc'] for r in live['settled_records']),
        observed_coverage_universe=live['observed_contracts'],ready_now=sum(r['raw_ready'] for r in locks),
        by_side={s:stats([r for r in locks if r['side']==s])for s in ('UP','DOWN')},
        by_day={d:stats([r for r in locks if datetime.fromtimestamp(r['time'],timezone.utc).date().isoformat()==d]) for d in sorted({datetime.fromtimestamp(r['time'],timezone.utc).date().isoformat() for r in locks})},
        by_remaining={b:stats([r for r in locks if lo<r['left']<=hi])for b,lo,hi in [('0-60',0,60),('60-180',60,180),('180-360',180,360),('360-480',360,480)]},
        mean_ask=statistics.mean(r['ask'] for r in locks),label_basis='Stored official-side labels in observer; not independent newly fetched settlement receipts')
    # Older selected-call CSV is its own already-opened historical cohort.
    fresh=[]
    for r in csv.DictReader((root/'fresh_oos_locked_final_calls.csv').open()):
        fresh.append(dict(contract=r['ticker'],left=float(r['remaining'])*60,p=float(r['preferred_fair']),correct=truth(r['correct'])))
    result['final_older_selected']=stats(fresh)

    # Real rounded model prints from Oct 8. This is ONLY a partial visible screen:
    # range5, source receipts, exact p and actual accept/reject identity are absent.
    review=json.loads((w/'recovered-selected/BTC15_FINAL_review_evidence_20261009/review.json').read_text());logrows=[]
    for r in review['all_observations']:
        logrows.append(dict(contract=r['contract'],time=epoch(r['log_time']),side=r['side'],p=r['confidence_percent']/100,left=r['minutes_left']*60,gap=r['btc_gap'],
            brti_gap=r['brti_gap'],brti_side=r['brti_side'],brti_age=r['brti_age'],brti_ready=r['brti_ready'],correct=r['correct']))
    logrows,d=unique_rows(logrows,['contract','time'])
    pred=lambda r: r['p']>.90 and 0<r['left']<=480 and r['gap']*(1 if r['side']=='UP'else -1)>0 and r['brti_side']==r['side'] and abs(r['brti_gap'])>11 and r['brti_ready'] and 0<=r['brti_age']<=5
    result['final_oct8_partial']=dict(rows=len(logrows),contracts=len({r['contract'] for r in logrows}),dedup=d,
        rounded_90_boundary_rows_excluded=sum(r['p']==.90 for r in logrows),table=policy_table(logrows,pred),
        status='PARTIAL_VISIBLE_PREDICATES_NOT_QUALIFIED_LOCKS',missing=['native range ratio','exact probabilities','full source qualification','complete issued/rejected history'],
        diagnostics=gate_diagnostics(logrows,pred))

    # Recorded common-journal MAIN states. Official archived receipts permit
    # exact target/contract/window binding on the Sep24 cohort. Restrict this
    # comparison to that cohort; do not cherry-pick labels from known winners.
    labels={};label_failures=[]
    with tarfile.open(next((w/'recovered-git').rglob('JOINT_LABELS_20260924.tar.gz'))) as t:
        for member in t:
            if member.isfile() and member.name.endswith('.json'):
                payload=json.load(t.extractfile(member));market=payload.get('market')
                if not isinstance(market,dict):label_failures.append(member.name);continue
                if market['status']=='finalized' and market['result'] in ('yes','no'):labels[market['ticker']]=market
    srows=[];reject=Counter();raw_count=0;observed_contracts=set()
    for line in (w/'recovered_main_states.jsonl').open():
        item=json.loads(line);s=item['state'];c=s['contract']
        if c not in labels:continue
        raw_count+=1;observed_contracts.add(c);m=s.get('market',{});f=s['final'];official=labels[c]
        source=s.get('source_timestamp_utc');received=item.get('recorded_at')
        if not source or received is None:reject['missing_observation_or_source_time']+=1;continue
        at=epoch(received);src=epoch(source);closed=epoch(official['close_time']);opened=epoch(official['open_time'])
        if not(opened<=src<=at<closed) or m.get('target')!=official['floor_strike']:reject['binding_or_clock']+=1;continue
        if not all(s.get('health',{}).get(x) is True for x in ['source_fresh','brti_fresh','paired_quotes','market_open']):reject['known_unhealthy']+=1;continue
        if f.get('source')!='FROZEN_V4_6_FINAL':reject['wrong_final_schema']+=1;continue
        fields=[num(f.get('confidence')),num(m.get('btc_gap')),num(m.get('dist_over_range5')),num(m.get('brti_gap'))]
        if any(x is None for x in fields):reject['missing_numeric_predicate']+=1;continue
        p,gap,ratio,bgap=fields;side=f.get('side')
        if side not in ('UP','DOWN'):reject['side']+=1;continue
        # One original feature observation per contract/source timestamp. Later
        # presentation refreshes do not count as independent decisions.
        srows.append(dict(contract=c,time=src,side=side,p=p,left=closed-src,gap=gap,ratio=ratio,
            brti_gap=bgap,brti_side=m.get('brti_side'),brti_ready=m.get('direct_brti_authority_ready'),
            vol5=num(m.get('vol5')),target=m['target'],correct=(side==('UP'if official['result']=='yes'else'DOWN'))))
    srows,d=unique_rows(srows,['contract','time'])
    pred=lambda r:r['p']>=.90 and 0<r['left']<=480 and r['ratio']>=1 and r['gap']*(1 if r['side']=='UP'else -1)>0 and r['brti_side']==r['side'] and abs(r['brti_gap'])>11 and r['brti_ready'] is True
    result['final_sep24_recorded_numeric']=dict(raw_state_rows=raw_count,observed_contracts=len(observed_contracts),usable_unique_observations=len(srows),usable_contracts=len({r['contract']for r in srows}),
        dedup=d,rejected=dict(reject),official_receipt_contracts=len(labels),failed_label_receipts=label_failures,table=policy_table(srows,pred),
        status='RECORDED_NUMERIC_ABLATION_WITH_KNOWN_HEALTH_FILTER_NOT_NATIVE_REPLAY',
        missing=['exact executable quote source/receipt sequence','complete native acceptance history','per-observation current model binding','untouched evaluation'],
        diagnostics=gate_diagnostics(srows,pred))

    # Same-loop EARLY/BRTI join diagnostics. No nearest future row, interpolation,
    # or missing receipt is manufactured. A source timestamp after the loop label
    # cannot be called available at that label even if the producer later read it.
    conf=list(csv.DictReader((root/'kalshi_early_conf_shadow_v1_2.csv').open()));brti=list(csv.DictReader((root/'kalshi_direct_brti_parity_v1.csv').open()))
    index=defaultdict(list)
    for r in brti:index[(r['contract'],r['timestamp_utc'],r['target'])].append(r)
    joined=[];future=missing=ambig=0
    for r in conf:
        xs=index.get((r['contract'],r['timestamp_utc'],r['target']),[])
        if len(xs)!=1:
            if xs:ambig+=1
            else:missing+=1
            continue
        b=xs[0]
        if not b.get('brti_timestamp_utc'):continue
        if epoch(b['brti_timestamp_utc'])>epoch(r['timestamp_utc']):future+=1;continue
        if truth(b['direct_brti_ready']) and 0<=epoch(r['timestamp_utc'])-epoch(b['brti_timestamp_utc'])<=5:joined.append((r,b))
    result['early_brti_join']=dict(early_rows=len(conf),brti_rows=len(brti),exact_loop_matches=len(conf)-missing-ambig,missing=missing,ambiguous=ambig,
        source_after_loop_label=future,source_time_sane_ready_rows=len(joined),source_time_sane_contracts=len({r['contract'] for r,b in joined}),
        original_quote_receipt_and_executable_book_proven=False,note='Same loop labels support alignment diagnostics, not proof of acquisition/decision timing.')

    # Recovered EARLY cohort: verify frozen entry identities directly against raw
    # lines; outcomes remain outside first-affordable selection.
    cohort=cache/catalog_item(cat,'btc15_cohort_native_v1_20260928.jsonl')['sha256']
    raw=[json.loads(s) for s in cohort.open()];ordinary=[(i+1,r) for i,r in enumerate(raw) if isinstance(r.get('early'),dict) and r.get('timestamp_utc')]
    origins=list(csv.DictReader((w/'recovered-selected/BTC15_EARLY_Value_Entry_Evidence/first_affordable_events_NOT_TRADES.csv').open()))
    paths=defaultdict(list)
    for i,r in ordinary:
        paths[r['contract']].append(r)
    for rs in paths.values():rs.sort(key=lambda r:epoch(r['timestamp_utc']))
    verified=0;horizon={h:[] for h in (240,300,360,420)};sustained=[];short=[]
    for o in origins:
        line=int(o['line']);r=raw[line-1];side=o['side'];ask=float(o['ask']);t=epoch(o['timestamp_utc']);left=float(o['seconds_left']);spread=float(o['spread'])
        assert r['contract']==o['contract'] and r['timestamp_utc']==o['timestamp_utc'] and abs(r[side.lower()+'_ask']-ask)<1e-12
        verified+=1
        seq=[x for x in paths[o['contract']] if epoch(x['timestamp_utc'])>=t]
        for h in horizon:
            later=fixed_horizon_quote(seq,t,h,left,side,r['target'])
            if later is None:continue
            bid=later[side.lower()+'_bid'];net=bid-ask-fee_scenario(ask)-fee_scenario(bid)-spread
            horizon[h].append(dict(contract=o['contract'],side=side,ask=ask,bid=bid,net_scenario_cents=net*100,positive=net>1e-9,source_time=o['timestamp_utc'],exit_observation=later['timestamp_utc']))
        if left>=420:
            segment=[x for x in seq if 240<=epoch(x['timestamp_utc'])-t<=430]
            prefix=[x for x in seq if epoch(x['timestamp_utc'])-t<=430]
            complete=segment and epoch(segment[0]['timestamp_utc'])<=t+250 and epoch(segment[-1]['timestamp_utc'])>=t+420 and all(epoch(b['timestamp_utc'])-epoch(a['timestamp_utc'])<=10 for a,b in zip(prefix,prefix[1:]))
            if complete and all(usable_quote_observation(x,side,r['target'])for x in prefix):
                nets=[x[side.lower()+'_bid']-ask-fee_scenario(ask)-fee_scenario(x[side.lower()+'_bid'])-spread for x in segment]
                sustained.append(dict(contract=o['contract'],all_observed_positive=all(n>1e-9 for n in nets),observations=len(nets),minimum_net_cents=min(nets)*100))
        if left<=30:short.append(dict(contract=o['contract'],side=side,ask=ask,left=left))
    comparison=list(csv.DictReader((w/'recovered-selected/BTC15_EARLY_Value_Entry_Evidence/candidate_comparison.csv').open()))
    result['early_cohort']=dict(raw_rows=len(raw),ordinary_rows=len(ordinary),ordinary_contracts=len(paths),verified_origins=verified,
        origins_correct=sum(truth(o['correct']) for o in origins),origin_contracts=len({o['contract'] for o in origins}),
        profile_702_qualified_entries=0,profile_reason='No approved opportunity profile; no recorded future-BID estimator/horizon/reserve binding. Synthetic-only mechanics are not historical validation.',
        horizon_scenarios={str(h):dict(n=len(rs),positive=sum(r['positive']for r in rs),mean_net_cents=statistics.mean(r['net_scenario_cents']for r in rs) if rs else None,records=rs)for h,rs in horizon.items()},
        sustained_4_to_7=dict(n=len(sustained),all_observed_positive=sum(r['all_observed_positive']for r in sustained),records=sustained),
        first_affordable_last30=short,frozen_comparison=[r for r in comparison if r['partition']=='all'],
        status='OBSERVED_QUOTE_SCENARIOS_NOT_TRADES',fee_basis='one-contract 7% p(1-p), cents rounded up each leg, plus original spread reserve; historical fee/depth/slippage unverified')
    accounting=rows('official_contract_accounting.csv');official_ids={x['contract']for x in accounting if truth(x['settled'])}
    partial=[]
    for line,r in ordinary:
        if r['contract'] not in official_ids:continue
        b=r.get('brti') or {};n=num(b.get('final60_count'));avg=num(b.get('final60_average'));left=num(r.get('seconds_left'))
        if n is None or avg is None or left is None or not(0<left<=60 and 0<n<60):continue
        if n>math.floor(60-left)+1:continue
        if not usable_quote_observation(r,'UP',r['target']):continue
        brti_value=num(b.get('direct_brti'))
        if brti_value is None:continue
        hurdle=(60*r['target']-n*avg)/(60-n)
        side=r['early'].get('preferred_side');sign=1 if side=='UP'else -1
        partial.append(dict(contract=r['contract'],time=r['timestamp_utc'],side=side,n=n,average=avg,target=r['target'],latest=brti_value,hurdle=hurdle,left=left,
                            latest_supports=sign*(brti_value-r['target'])>0,hurdle_challenges=sign*(brti_value-hurdle)<0))
    result['settlement_context']=dict(partial_rows=len(partial),contracts=len({r['contract']for r in partial}),
        latest_support_but_hurdle_challenges_rows=sum(r['latest_supports']and r['hurdle_challenges']for r in partial),
        latest_support_but_hurdle_challenges_contracts=len({r['contract']for r in partial if r['latest_supports']and r['hurdle_challenges']}),
        settlement_aware_lock_accuracy=None,reason='Recorded aggregate can support diagnostic hurdle arithmetic. Per-second causal sample identity and a validated remaining-path distribution are absent; no replacement lock model scored.',
        examples=[r for r in partial if r['latest_supports']and r['hurdle_challenges']][:3])

    # Historical live-observer EARLY first entries, completion paths and outcomes.
    eventlogs=[json.loads((out/f'logs/events-{i}.json').read_text())['deploy'] for i in range(4)]
    entries={};complete={};settled={};excluded=0
    for r in eventlogs[0]:
        m=re.search(r'ENTRY \| (KXBTC15M-\S+) \| (UP|DOWN) \| ask=([\d.]+) \| fair=([\d.]+) edge=([-\d.]+) \| left=([\d.]+)m',r['message'])
        if not m:excluded+=1;continue
        entries.setdefault(m[1],dict(contract=m[1],time=r['timestamp'],side=m[2],ask=float(m[3]),p=float(m[4]),left=float(m[6])*60))
    for r in eventlogs[1]:
        m=re.search(r'COMPLETE \| (KXBTC15M-\S+) \| side=(UP|DOWN) \| entry=([\d.]+) \| MFE=([-\d.e]+) \| MAE=([-\d.e]+) \| \+10c=(True|False) \| FINAL=(\S+)',r['message'])
        if m:complete[m[1]]=dict(mfe=float(m[4]),mae=float(m[5]),target10=m[6]=='True',final=m[7])
    for r in eventlogs[2]:
        m=re.search(r'SETTLED \| (KXBTC15M-\S+) \| early=(UP|DOWN) \| official=(UP|DOWN)',r['message'])
        if m:settled[m[1]]=m[3]
    ers=[]
    for c,r in entries.items():ers.append(dict(**r,correct=r['side']==settled[c] if c in settled else None,**complete.get(c,{})))
    result['early_forward_observer']=dict(**stats(ers),excluded_startup_test_rows=excluded,completed=len(complete),
        entries_with_4_to_7_minutes=sum(240<=r['left']<=420 for r in ers),last30=sum(r['left']<=30 for r in ers),
        observed_positive_mfe=sum(r.get('mfe',0)>0 for r in ers),observed_plus10=sum(r.get('target10',False) for r in ers),
        mean_ask=statistics.mean(r['ask'] for r in ers),records=ers,
        warning='First observer eligibility per contract, not evidence of current native issued BUY, fills, or profit. MFE maxima do not specify a causal exit.')

    # October existing origin-linked summaries: do not manufacture event sequences.
    a=list(csv.DictReader((w/'recovered-library/BTC15_origin_linked_reentry_audit.csv').open()));b=list(csv.DictReader((w/'recovered-library/BTC15_reentry_readiness_runs.csv').open()))
    follow=list(csv.DictReader((w/'recovered-library/BTC15_directional_EXIT_followthrough_20261010.csv').open()));impact=list(csv.DictReader((w/'recovered-library/BTC15_EXIT_policy_historical_impact_20261010.csv').open()))
    result['lifecycle_summaries']=dict(origin_rows=len(a),unique_origins=len({r['origin_id']for r in a}),contracts=len({r['contract']for r in a}),
        with_exit=sum(truth(r['has_exit'])for r in a),post_exit_decisions=sum(int(r['post_exit_decisions'])for r in a),
        post_exit_ready_rows=sum(int(r['post_exit_ready'])for r in a),origins_with_post_exit_ready=sum(int(r['post_exit_ready'])>0 for r in a),
        runs_audit_origins=len(b),origins_with_run30=sum(int(r['runs_ge30s'])>0 for r in b),runs_ge30=sum(int(r['runs_ge30s'])for r in b),
        runs_start_5m=sum(int(r['runs_start_5m_plus'])for r in b),runs_start_8m=sum(int(r['runs_start_8m_plus'])for r in b),
        old_exit_followthrough_origins=len(follow),later_thesis_invalidations=sum(truth(r['later_thesis_invalidation'])for r in impact),
        later_last_bid_above_old=sum(float(r['last_observed_bid'])>float(r['old_bid'])for r in follow if r['last_observed_bid']),
        status='SAVED_DERIVED_SUMMARIES_NO_FULL_CURRENT_NATIVE_LIFECYCLE_REPLAY')
    scalp=rows('results/immutable_signal_audit.csv')
    result['scalp_recovered']=dict(origins=len(scalp),unique_signal_ids=len({r['signal_id']for r in scalp}),contracts=len({r['contract']for r in scalp}),
        cohorts={c:dict(origins=sum(r['cohort']==c for r in scalp),contracts=len({r['contract']for r in scalp if r['cohort']==c}),
            complete_paths=sum(r['cohort']==c and truth(r['complete'])for r in scalp))for c in sorted({r['cohort']for r in scalp})},
        first=min(r['origin_timestamp']for r in scalp),last=max(r['origin_timestamp']for r in scalp),
        status='HISTORICAL_NATIVE_AND_GENERALIZED_SHADOW_COHORTS_SEPARATE_NOT_CURRENT_V81_VALIDATION',
        original_source_quote_paths=len(rows('results/quote_path_audit.csv')),native_recorded_protective_exits=len(rows('results/native_profit_shadow_audit.csv')))
    saved=json.loads(next((w/'recovered-library').rglob('detailed_validation.json')).read_text())
    gates=saved['locked_gate_diagnosis']
    result['saved_pr36_validation']=dict(window=saved['window'],contracts=len(saved['frame_stats']),
        input_frames=saved['unique_source_snapshots'],qualified_distinct_frames=saved['unique_source_qualified_snapshots'],
        qualification=gates,final_distance_only_failures=gates['final']['patterns'].get('gap',0),
        early_lifecycle_evaluable=saved['early_final_lifecycle_evaluable'],
        status='SAVED_PRIOR_CAUSAL_VALIDATION_SUMMARY_NOT_NEW_RAW_FRAME_REPLAY',
        missing='The summary itself omits raw bytes; those exact feature/common ranges were subsequently recovered and checked separately in recovered_export_results.json.')
    (out/'analysis_results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:{kk:vv for kk,vv in v.items() if kk not in ['records','table','horizon_scenarios','frozen_comparison','by_day']} for k,v in result.items()},indent=2))

if __name__=='__main__':
    import sys
    main(Path(sys.argv[1]))
