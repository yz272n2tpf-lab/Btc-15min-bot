"""Inspect only already-downloaded fresh producer prefixes; no network or strategy execution."""
from pathlib import Path
import collections,datetime,gzip,json
ROOT=Path(__file__).resolve().parents[1];base=ROOT/'event_ground_zero';out={}
for mode in ('main','v81'):
    result=json.loads((base/f'results/live-{mode}.json').read_text());a=result['health']['transport_accounting']
    folder=base/'fresh'/mode/result['run_id'];reports={}
    for p in folder.glob('page-*.json'):
        page=json.loads(p.read_text())
        if page['snapshot_id']==a['snapshot_id']:
            reports.update({r['producer_id']:r for r in page['records']})
    counts=collections.Counter();heads={};start=None;end=None;contract=set();native_markets=[];qualified_origins=[]
    with gzip.open(folder/'packets.jsonl.gz','rb') as f:
        for line in f:
            e=json.loads(line)['event'];b=e['body'];em=b.get('emission',{});state=b.get('state') or em.get('state') or {};rec=b.get('record') or {}
            heads[e['identity']['producer_id']]=e['sequence'];t=e['hook_read']['wall_ns'];start=min(start,t) if start is not None else t;end=max(end,t) if end is not None else t
            if e['kind']=='PROTECTED_GENERATION':
                counts['protected_generations']+=1
                counts['early_eligible']+=int((state.get('early') or {}).get('ready') is True)
                counts['final_ready']+=int((state.get('final') or {}).get('ready') is True)
                counts['recorded_final_call']+=int((state.get('final') or {}).get('recorded_final_call') is True)
                protection=state.get('position_protection') or {}
                counts['protected_state_status_'+str(protection.get('status'))]+=1
            if e['kind']=='NATIVE_CYCLE':
                counts['native_cycles']+=1
                counts['native_early_provisional']+=int((b.get('_ec_row') or {}).get('provisional_candidate') is True)
                counts['native_scalp_pending_observations']+=len(b.get('_true_scalp_pending') or [])
                m=b.get('market') or {};native_markets.append({k:m.get(k) for k in ('ticker','open_time','close_time','floor_strike','status')})
            if e['kind']=='NATIVE_COMMITTED_COHORT':
                counts['cohort_rows']+=1;counts['cohort_final_status_'+str(rec.get('final_status'))]+=1
                counts['closeout_60_of_60']+=int((rec.get('brti') or {}).get('final60_complete') is True and (rec.get('brti') or {}).get('final60_count')==60)
                counts['closeout_record_schema_'+str(rec.get('schema'))]+=1
            if e['kind']=='SHADOW_FINAL_COMMITTED_ROW':counts['final_protection_rows']+=1
            if em.get('schema')=='BTC15_V81_PASSIVE_EMISSION_V1':
                phase=em.get('phase');counts['v81_'+str(phase)]+=1
                if em.get('event_type')=='EVALUATION':counts['v81_active_evaluations']+=int(em.get('active') is not None)
    missing=sorted(set(heads)-set(reports));retired_mismatch=[];active_deltas={}
    for pid,v in reports.items():
        if v['finished'] and (not v['complete'] or heads.get(pid,0)!=v['delivered']):retired_mismatch.append(pid)
        if not v['finished']:active_deltas[pid]=v['received_sequence']-heads.get(pid,0)
    archive_errors=[x for x in result['errors'] if not x.startswith('POPULATION_REPORT_COUNT:')]
    if missing:archive_errors.append('ARCHIVE_STREAM_WITHOUT_REPORT')
    if retired_mismatch:archive_errors.append('RETIRED_STREAM_TAIL_MISMATCH')
    out[mode]=dict(run_id=result['run_id'],manifest_http=result['http_status'],capture_hashes_match=result['hashes_match'],
        archive_continuity='FAIL' if archive_errors else 'PASS',archive_errors=archive_errors,packet_count=result['inspected']['rows'],
        archive_streams=len(heads),status_reports=len(reports),missing_reports=missing,retired_tail_mismatch=retired_mismatch,
        active_receiver_heads_minus_archive=active_deltas,aggregate_snapshot_complete=a['complete'],aggregate_snapshot_errors=a['errors'],
        aggregate_created=a['created'],reported_streams=a['total'],drops=a['dropped'],retries=a['retried'],pending=a['pending'],counts=dict(counts),
        contracts=result['inspected']['contracts'],first_event_utc=datetime.datetime.fromtimestamp(start/1e9,datetime.timezone.utc).isoformat(),
        last_event_utc=datetime.datetime.fromtimestamp(end/1e9,datetime.timezone.utc).isoformat(),native_market_samples=native_markets)
(base/'results/fresh-event-summary.json').write_text(json.dumps(out,indent=2)+'\n')
for mode,r in out.items():print(mode,json.dumps({k:v for k,v in r.items() if k not in ('native_market_samples','active_receiver_heads_minus_archive')},indent=2))
