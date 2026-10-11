"""Offline evaluation of hash-verified existing export ranges; no orders."""
import hashlib,json
from collections import Counter
from pathlib import Path
from audit.existing_evidence_20261011.evaluate import epoch,policy_table,unique_rows,gate_diagnostics

def check_managed_publication(selected,origin):
    s=selected['state'];q=s['path']['last_quote']
    assert q['ticker']==origin['contract']==s['contract']
    assert q['epoch']==origin['entry_provenance']['quote']['epoch']
    assert origin['side']=='UP' and q['up_bid']==s['executable_current_bid']
    assert q['source_ts_ms']/1000<=q['validated_at_ms']/1000<=s['published_ts']<=s['journal_committed_ts']
    assert 0<=s['published_ts']-q['source_ts_ms']/1000<=5
    assert epoch(selected['received'])<s['expires_at']
    assert s['orders']is False and s['signal_only']is True
    return q

def main(w):
    out=w/'repo/audit/existing_evidence_20261011';results={}
    frames=[json.loads(l)for l in(w/'recovered-feature-frames/pr36_frames.jsonl').open()]
    index={(r['ticker'],epoch(r['decision_utc'])):r for r in frames}
    assert len(index)==len(frames)==668
    for r in frames:
        assert epoch(r['btc_source_utc'])<=epoch(r['btc_observed_utc'])<=epoch(r['decision_utc'])
        assert r['signal_only'] is True and r['orders'] is False
    labels={r['contract']:r['official_side']for r in json.loads((out/'final_forward_state.json').read_text())['live']['settled_records']}
    rows=[];rejected=Counter();seen=[]
    for line in(w/'recovered-common/pr36/records.jsonl').open():
        r=json.loads(line)
        for source in r.get('sources',[]):
            if source['service']!='main' or 'state'not in source:continue
            s=source['state'];key=(s.get('contract'),epoch(s['source_timestamp_utc']))
            f=index.get(key)
            if f is None:rejected['outside_exact_feature_binding']+=1;continue
            m=s['market'];g=s['final'];seen.append(key)
            assert f['target']==m['target'] and f['btc_price']==m['btc_price']
            assert f['features']['dist_over_range5']==m['dist_over_range5']
            assert f['features']['dist_target']==m['btc_gap']
            if not all(s['health'].get(x)is True for x in ['source_fresh','paired_quotes','brti_fresh','market_open']):
                rejected['known_unhealthy_at_observer_receipt']+=1;continue
            assert epoch(f['decision_utc'])<=epoch(source['response_received_utc'])
            side=g['side'];c=f['ticker']
            rows.append(dict(contract=c,time=key[1],left=f['features']['remaining']*60,
                p=g['confidence'],side=side,gap=m['btc_gap'],ratio=m['dist_over_range5'],vol5=m['vol5'],
                brti_authority=m['direct_brti_authority_ready'],brti_agrees=m['direct_brti_agrees'],
                target_agrees=g['conditions']['preferred_matches_target'],raw_ready=g['ready'],
                correct=side==labels[c]if c in labels else None,feature_weights=f['weights_sha256']))
    rows,d=unique_rows(rows,['contract','time'])
    pred=lambda r: r['p']>=.90 and 0<r['left']<=480 and r['ratio']>=1 and r['brti_authority'] and r['brti_agrees'] and r['target_agrees']
    results['pr36']=dict(input_frames=668,contracts=len({r['ticker']for r in frames}),matched_distinct_feature_frames=len(set(seen)),
        health_filtered_distinct_observations=len(rows),dedup=d,rejected=dict(rejected),
        raw_ready_observations=sum(r['raw_ready']for r in rows),table=policy_table(rows,pred),diagnostics=gate_diagnostics(rows,pred),
        status='RECOVERED_ORIGINAL_FEATURE_BINDING_AND_RECORDED_NUMERIC_GATES_NOT_FULL_NATIVE_BOOK_REPLAY',
        prior_strict_qualification_count=645,
        qualification_note='Current count uses recorded health and exact feature binding; it is not the prior report strict qualification classifier. Neither count supplies missing original executable-book receipts.',
        label_basis='Stored observer official-side outcome for selected contract; no labels influence selection')
    (out/'pr36_bound_numeric_frames.json').write_text(json.dumps(rows,indent=2))

    incident=[json.loads(l)for l in(w/'recovered-common/incident/records.jsonl').open()]
    projections=[];selected={};main_near=[];origin_id='04c02740ab1490770137fc9a53868a5e31b71c56cce6f377b1ef248af4e124c7'
    keep=['build','schema','contract','target','status','reason','guidance','published_ts','expires_at','journal_committed_ts',
        'origin','terminal','input_provenance','executable_current_bid','path','context','economics','trailing_trigger_bid','orders','signal_only']
    for r in incident:
        for source in r['sources']:
            s=source.get('state',{});service=source['service']
            if service=='main' and '2026-10-11T14:29:28'<=r['recorded_utc']<'2026-10-11T14:29:34':
                main_near.append(dict(observed=r['recorded_utc'],received=source.get('response_received_utc'),state={k:v for k,v in s.items()if k!='chart'}))
            if service!='v81':continue
            origin=s.get('origin')or{};path=s.get('path')or{};quote=path.get('last_quote')or(s.get('input_provenance')or{}).get('quote')or{}
            p=dict(observed=r['recorded_utc'],received=source.get('response_received_utc'),contract=s.get('contract'),origin=origin.get('origin_id'),
                publication=s.get('published_ts'),expires=s.get('expires_at'),status=s.get('status'),guidance=s.get('guidance'),
                reason=s.get('reason'),bid=s.get('executable_current_bid'),quote=quote,path_missing=path.get('missing'),
                journal_committed=s.get('journal_committed_ts'),path_samples=path.get('samples'),giveback=path.get('giveback'),mfe=path.get('mfe'))
            projections.append(p)
            if origin.get('origin_id')!=origin_id:continue
            tags=[]
            if s.get('guidance')=='ENTER':tags.append('entry')
            if s.get('guidance')=='PROTECT':tags.append('first_protect')
            if quote.get('up_bid')==.70:tags.append('bid70')
            if s.get('executable_current_bid')==.84:tags.append('peak84')
            if s.get('guidance')=='EXIT':tags.append('exit79')
            for tag in tags:
                if tag not in selected:selected[tag]=dict(observed=r['recorded_utc'],received=source.get('response_received_utc'),state={k:s.get(k)for k in keep})
    assert set(selected)=={'entry','first_protect','bid70','peak84','exit79'}
    entry=selected['entry']['state'];o=entry['origin'];q=o['entry_provenance']['quote']
    assert q['ticker']==o['contract']==entry['contract'] and q['up_ask']==o['original_ask']==.60 and q['up_bid']==.59
    assert q['source_ts_ms']/1000<=q['validated_at_ms']/1000<=o['decision_ts']<=o['signal_ts']<=entry['journal_committed_ts']
    checks=[]
    for name in ['first_protect','bid70','peak84','exit79']:
        s=selected[name]['state'];q=check_managed_publication(selected[name],o)
        checks.append(dict(event=name,bid=q['up_bid'],source_ms=q['source_ts_ms'],sequence=q['sequence'],published=s['published_ts'],
            quote_age_at_publication_ms=s['published_ts']*1000-q['source_ts_ms'],observed=selected[name]['observed']))
    terminal=selected['exit79']['state']['terminal']
    assert terminal['reason']=='ARM5_GIVEBACK4' and terminal['path']['giveback']>=.04
    assert terminal['realized_profit']is None and terminal['manual_fill']is None
    outages=[r for r in projections if r['origin']==origin_id and r['status']=='UNAVAILABLE']
    results['incident']=dict(common_observations=len(incident),contracts=sorted({p['contract']for p in projections if p['contract']}),
        selected_source_checks=checks,entry_quote_age_at_decision_ms=o['decision_ts']*1000-o['entry_provenance']['quote']['source_ts_ms'],
        entry_quote_age_at_signal_ms=o['signal_ts']*1000-o['entry_provenance']['quote']['source_ts_ms'],
        entry_source_ms=o['entry_provenance']['quote']['source_ts_ms'],entry_decision=o['decision_ts'],entry_publication=o['signal_ts'],
        entry_journal_committed=entry['journal_committed_ts'],entry_observed=selected['entry']['observed'],
        outages=outages,complete_path=terminal['complete_path'],exit_reason=terminal['reason'],
        exit_net_scenario=terminal['economics']['net_liquidation_scenario'],exit_net_after_reserve=terminal['economics']['net_after_execution_reserve'],
        realized_profit=None,manual_fill=None,early_native_origin_frame_recovered=False,
        early_price_corroborated_by_main_observation=True,full_exchange_depth_or_execution_acknowledgment=False)
    (out/'incident_selected_publications.json').write_text(json.dumps(selected,indent=2))
    (out/'incident_scalp_quote_path.json').write_text(json.dumps(projections,indent=2))
    (out/'incident_main_near_early.json').write_text(json.dumps(main_near,indent=2))
    (out/'recovered_export_results.json').write_text(json.dumps(results,indent=2))
    print(json.dumps({k:({a:b for a,b in v.items()if a!='table'})for k,v in results.items()},indent=2))

if __name__=='__main__':
    import sys
    main(Path(sys.argv[1]))
