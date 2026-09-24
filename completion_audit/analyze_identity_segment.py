"""Read-only development analysis; preserve the frozen calendar and runtime split.

No tuning, promotion, filled-trade inference, or holdout outcome access.
"""
import argparse
from collections import Counter, defaultdict
from datetime import timedelta
import hashlib
import json
from pathlib import Path
from common_journal import scan
from cohort_registry import identity, registry, utc
from summarize_passive_acceptance import analyze, summary
from btc15_qualified_forward_observer_v1 import observation


def load_segment(path, manifest, start, end):
    frozen = dict(manifest)
    if identity({k: v for k, v in frozen.items() if k != 'canonical_content_sha256_excluding_this_field'}) != frozen['canonical_content_sha256_excluding_this_field']:
        raise ValueError('Frozen manifest identity mismatch')
    development = next(w for w in manifest['windows'] if w['role'] == 'development_tuning')
    if not utc(development['start_utc']) <= start < end <= utc(development['end_utc']):
        raise ValueError('This tool may only open development observations')
    records, inputs, damage = [], [], []
    for member in scan(path, damage):
        row = member['record']
        if row.get('run_id') != manifest['revisions']['clean']['run_id']:
            raise ValueError('Mixed collector run identities')
        if row.get('record_type') == 'SNAPSHOT_INPUT':
            if start <= utc(row['observed_utc']) < end:
                inputs.append(row)
        elif row.get('record_type') == 'OBSERVATION':
            for source in row['sources']:
                began = utc(source['request_started_utc'])
                if not start <= began < end:
                    continue
                state = source.get('state')
                if isinstance(state, dict):
                    state.pop('chart', None)  # Derived view only; original journal intact.
                records.append(dict(source, service='scalp' if source['service'] == 'serial' else source['service'],
                                    start_epoch=began.timestamp()))
    if damage:
        raise ValueError('Journal CRC/member damage: ' + json.dumps(damage))
    return records, inputs


def assess(records, inputs, markets, start, end):
    report = analyze(records, start, end, markets, qualification_time='response_received')
    window = dict(start_utc=start.isoformat(), end_utc=end.isoformat(), role='development_tuning')
    report['universe_registry'] = registry(window, markets, [r.get('state', {}).get('contract') for r in records if isinstance(r.get('state'), dict)])
    report['services'] = {}
    for service in ('main', 'owner', 'v81', 'scalp'):
        rows = [r for r in records if r['service'] == service]
        clocks = sorted(utc(r['request_started_utc']) for r in rows)
        gaps = [(b-a).total_seconds() for a, b in zip(clocks, clocks[1:])]
        report['services'][service] = dict(samples=len(rows), first_request=clocks[0].isoformat() if clocks else None,
            last_request=clocks[-1].isoformat() if clocks else None, request_gap_seconds=summary(gaps),
            http_failures=sum(r.get('http_status') != 200 for r in rows),
            missing_state=sum(not isinstance(r.get('state'), dict) for r in rows),
            gaps_over_1_5s=[dict(start=a.isoformat(), end=b.isoformat(), seconds=(b-a).total_seconds())
                           for a,b in zip(clocks, clocks[1:]) if (b-a).total_seconds() > 1.5])
    contracts = []
    for market in markets:
        opened, closed = utc(market['open_time']), utc(market['close_time'])
        if not start <= opened < end:
            continue
        ticker = market['ticker']
        source = [r for r in records if r['service'] == 'main' and opened <= utc(r['request_started_utc']) < closed]
        exact = [r for r in source if isinstance(r.get('state'), dict) and r['state'].get('contract') == ticker]
        qualified = [r for r in exact if (lambda o: o['usable_frame'] and o['brti_fresh'])(observation(r['state'], utc(r['response_received_utc'])))]
        clean = [r for r in inputs if r['ticker'] == ticker and opened <= utc(r['observed_utc']) < closed]
        targets = sorted({r['state']['market']['target'] for r in exact if r['state'].get('market', {}).get('target') is not None})
        contracts.append(dict(ticker=ticker, open_utc=market['open_time'], close_utc=market['close_time'], official_target=market.get('floor_strike'),
            observed_targets=targets, target_matches=targets == [market.get('floor_strike')], observations=len(source), exact_ticker_observations=len(exact),
            qualified_samples=len(qualified), first_qualified_seconds=(utc(qualified[0]['response_received_utc'])-opened).total_seconds() if qualified else None,
            qualified_final60_samples=sum(utc(r['response_received_utc']) >= closed-timedelta(seconds=60) for r in qualified),
            clean_input_samples=len(clean), clean_target_mismatches=sum(r['target'] != market.get('floor_strike') for r in clean),
            clean_input_max_gap_seconds=max(((utc(b['observed_utc'])-utc(a['observed_utc'])).total_seconds() for a,b in zip(clean,clean[1:])),default=None),
            clean_source_violations=sum(not (r.get('signal_only') is True and r.get('orders') is False and r.get('quote_transport') == 'timestamped_contiguous_ws' and 0 <= utc(r['observed_utc']).timestamp()-r['brti_source_ts_ms']/1000 <= 5) for r in clean),
            official_result=market.get('result'), expiration_value=market.get('expiration_value')))
    report['contract_evidence'] = contracts
    # Main's legacy summary path allows old cached BRTI. Preserve it explicitly
    # as descriptive telemetry, then report independent qualified book paths.
    for lane, metrics in report['lanes'].items():
        for call in metrics['calls']:
            call['cached_main_bid_path_unqualified_for_execution'] = call.pop('sampled_bid_path')
            began = utc(call['observed_utc'])
            close = utc(next(m['close_time'] for m in markets if m['ticker'] == call['contract']))
            deadline = min(close, began+timedelta(seconds=300)) if lane == 'scalp' else close
            eligible = [r for r in inputs if r['ticker'] == call['contract'] and began <= utc(r['observed_utc']) < deadline
                and r.get('signal_only') is True and r.get('orders') is False
                and r.get('quote_transport') == 'timestamped_contiguous_ws'
                and r.get('quote_validation_utc') == r.get('observed_utc')
                and 0 <= utc(r['observed_utc']).timestamp()-r['brti_source_ts_ms']/1000 <= 5]
            values = [r[call['side'].lower()+'_bid']-call['entry_ask'] for r in eligible]
            call['sampled_bid_path'] = dict(sample_count=len(eligible), observed_mfe=max(values,default=None),
                observed_mae=min(values,default=None), first_quote_utc=eligible[0]['observed_utc'] if eligible else None,
                max_observed_gap_seconds=max(((utc(b['observed_utc'])-utc(a['observed_utc'])).total_seconds() for a,b in zip(eligible,eligible[1:])),default=None),
                horizon_end_utc=deadline.isoformat(), complete_path=False, realized_profit=False,
                source='Independent timestamped clean collector, BRTI <=5s',
                entry_ask_confirmed_at_first_quote=(eligible[0][call['side'].lower()+'_ask'] <= call['entry_ask'] if eligible else False),
                entry_to_first_quote_seconds=(utc(eligible[0]['observed_utc'])-began).total_seconds() if eligible else None,
                entry_and_exit_fill_not_proven=True)
    owner_states, recoveries = Counter(), []
    prior = None
    for r in records:
        if r['service'] != 'owner' or not isinstance(r.get('state'), dict):continue
        d=r['state'];owner_states[d.get('status')] += 1
        current = (d.get('status'), d.get('clean_for_qualification'), d.get('upstream_errors'))
        if current != prior:
            recoveries.append(dict(observed_utc=r['response_received_utc'], status=d.get('status'), clean=d.get('clean_for_qualification'),
                source_ts_ms=d.get('source_ts_ms'), source_age_ms=d.get('age_ms'), upstream_errors=d.get('upstream_errors'),
                error_type=d.get('last_error_type'), error_text=d.get('last_error_text'), http_429=d.get('http_429')))
            prior=current
    report['owner_status_samples']=dict(owner_states);report['owner_transitions']=recoveries
    reasons=Counter();final_fail=Counter();v81_reasons=Counter();v81_active=0;v81_invalid_active=[];v81_provenance=0;serial={}
    main_source_epochs=set();frozen_weights=set()
    for r in records:
        d=r.get('state')
        if not isinstance(d,dict):continue
        if r['service']=='main':
            main_source_epochs.add(d.get('source_timestamp_utc'))
            if d.get('fair_model_weights_sha256'):frozen_weights.add(d['fair_model_weights_sha256'])
            if observation(d,utc(r['response_received_utc']))['usable_frame']:
                for lane in ('early','final','scalp'):reasons[lane+':'+str(d.get(lane,{}).get('status',d.get(lane,{}).get('ready')))] +=1
                for key,value in d.get('final',{}).get('conditions',{}).items():
                    if value is False:final_fail[key]+=1
        if r['service']=='v81':
            v81_reasons[str(d.get('primary_wait_reason'))]+=1
            p=d.get('input_provenance') or {};v81_provenance+=p.get('schema')=='V81_TIMESTAMPED_INPUTS_V1'
            if d.get('active') is True:
                v81_active+=1;now=utc(r['response_received_utc']).timestamp();q=p.get('quote') or {};b=p.get('brti') or {}
                valid=(p.get('ticker')==d.get('contract')==q.get('ticker') and p.get('signal_only') is True and p.get('orders') is False
                    and q.get('transport')=='timestamped_contiguous_ws' and b.get('clean_for_qualification') is True and b.get('status')=='PRIMARY_OK'
                    and 0<=now-utc(d['generated_utc']).timestamp()<=3.5 and 0<=now-b.get('source_ts_ms',0)/1000<=5
                    and 0<=now-q.get('source_ts_ms',0)/1000<=6)
                if not valid:v81_invalid_active.append(dict(received=r['response_received_utc'],contract=d.get('contract')))
        if r['service']=='scalp':
            for t in d.get('terminal_history') or []:
                if start <= utc(t['terminal_time_utc']) < end and t['candidate_id'].split('|')[0] in {c['ticker'] for c in contracts}:
                    serial.setdefault(t['candidate_id'],t)
    report['main_gate_descriptions']=dict(reasons);report['final_failed_conditions']=dict(final_fail)
    report['v81_source_check']=dict(active_frames=v81_active,invalid_active_frames=v81_invalid_active,provenance_frames=v81_provenance,
        wait_reasons=dict(v81_reasons),note='Active source flags are not proof of browser delivery or complete signal recall')
    report['serial_terminal_events']=list(serial.values())
    report['main_unique_source_snapshots']=len(main_source_epochs);report['dashboard_weight_hashes']=sorted(frozen_weights)
    report['runtime_identity_requires_startup_log_evidence']=True
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--journal',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--markets',type=Path,required=True);p.add_argument('--start',required=True);p.add_argument('--end',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    manifest=json.loads(a.manifest.read_text());start,end=utc(a.start),utc(a.end)
    records,inputs=load_segment(a.journal,manifest,start,end)
    markets=[json.loads(f.read_text())['market'] for f in sorted(a.markets.glob('*.json'))]
    result=assess(records,inputs,markets,start,end)
    result.update(cohort_id=manifest['cohort_id'],phase='development_tuning',partial_window=True,
        parent_manifest_sha256=manifest['canonical_content_sha256_excluding_this_field'],orders=False,
        journal_bytes=a.journal.stat().st_size,journal_sha256=hashlib.file_digest(a.journal.open('rb'),'sha256').hexdigest(),
        frozen_calendar_unchanged=True,changed_runtime_not_pooled=True)
    with a.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps(dict(output=str(a.output),contracts=len(result['contract_evidence']),counts=result['counts'],
        lanes={k:{q:v[q]for q in ['strict_qualified_contracts','accuracy','entry_ask','minutes_remaining']}for k,v in result['lanes'].items()},
        owner_status_samples=result['owner_status_samples'],v81_active=result['v81_source_check']['active_frames'])))
