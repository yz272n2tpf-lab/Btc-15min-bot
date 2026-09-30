"""Read-only MAIN lifetime hard gate: producer archive, all status pages, no evaluation GET."""
import gzip,hashlib,json,time,urllib.request,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MODE=sys.argv[1] if len(sys.argv)>1 else 'main'
HOSTS={'main':'btc-15min-bot-production.up.railway.app','v81':'v81-live-diagnostics-production.up.railway.app'}
BASE='https://'+HOSTS[MODE]+'/ground-zero/'
BUILD={'main':'abe212b513827c8cec28a2f64e0161e79296bd82','v81':'b05723ec622f901a05402ecf27f4d33505753ef1'}[MODE]
PAYLOAD=json.loads((ROOT/'event_ground_zero/results/payload.json').read_text())
EXPECTED={n:hashlib.sha256(s.encode()).hexdigest() for n,s in PAYLOAD.items() if n.startswith('capture2/')}

def get(url):
    with urllib.request.urlopen(url,timeout=20) as r:return r.read(2*1024*1024+1),r.status,dict(r.headers)

def probe(raw=None,status=200,headers=None):
    if raw is None:raw,status,headers=get(BASE+'manifest')
    stamp=str(time.time_ns());d=json.loads(raw);m=d['manifest'];h=d['health']
    folder=ROOT/'event_ground_zero/fresh'/MODE/m['run_id'];folder.mkdir(parents=True,exist_ok=True)
    (folder/('manifest-'+stamp+'.json')).write_bytes(raw)
    errors=[];a=h.get('transport_accounting',{});records=[];offset=0
    cached={}
    for saved in folder.glob('page-*.json'):
        value=json.loads(saved.read_text())
        if value.get('snapshot_id')==a['snapshot_id']:cached[value['offset']]=saved.read_bytes()
    while offset is not None:
        if offset in cached:body,code=cached[offset],200
        else:body,code,_=get(BASE+f"transports?snapshot={a['snapshot_id']}&offset={offset}&limit=128")
        page=json.loads(body);(folder/('page-'+stamp+'-'+str(offset)+'.json')).write_bytes(body)
        if code!=200 or page['snapshot_id']!=a['snapshot_id'] or page['total']!=a['total']:raise ValueError('PAGE_IDENTITY')
        records+=page['records'];offset=page['next_offset']
    if len(records)!=a['total'] or len({r['producer_id'] for r in records})!=a['total']:errors.append('PAGE_COVERAGE')
    if m.get('build')!=BUILD or m.get('native_strategy_commit')!=BUILD:errors.append('STRATEGY_BINDING')
    if m.get('capture_files')!=EXPECTED:errors.append('PAYLOAD_HASH_BINDING')
    if m.get('signal_only') is not True or m.get('orders') is not False:errors.append('SAFETY')
    if h.get('invalid') or h.get('producer_drop_observed') or h.get('sequence_gaps'):errors.append('PRODUCER_LOSS_OR_INVALID')
    if h.get('status')!='RECORDING_OPERATIONAL_UNCERTIFIED':errors.append('WRITER_'+str(h.get('status')))
    if not a.get('complete'):errors+=a.get('errors') or ['ACCOUNTING_UNAVAILABLE']
    if not h.get('packets'):errors.append('NO_PRODUCER_PACKETS')
    for r in records:
        if r['producer_dropped'] or r['rejected'] or r['last_transport_error']:errors.append('TRANSPORT_FAILURE:'+r['producer_id'])
        if r['pending_bytes']>r['max_bytes'] or r['pending_packets']>r['max_packets']:errors.append('BUFFER_BOUND')
    for p in a['populations']:
        if p['active']>p['max_active_senders'] or p['active_sender_high_water']>p['max_active_senders']:errors.append('SENDER_BOUND')
        if p['created']>p['max_created_streams'] or p['active_buffer_bytes']>p['max_aggregate_buffer_bytes']:errors.append('POPULATION_BOUND')
    result=dict(run_id=m['run_id'],http_status=status,hashes_match=m.get('capture_files')==EXPECTED,
                observed_wall_ns=time.time_ns(),manifest_sha256=hashlib.sha256(raw).hexdigest(),errors=errors,health=h)
    path=folder/'packets.jsonl.gz';offset=path.stat().st_size if path.exists() else 0;goal=h['bytes']
    if goal>32*1024*1024:raise ValueError('QUALIFICATION_ARCHIVE_BOUND')
    with path.open('ab') as out,(folder/'receipts.jsonl').open('a') as receipts:
        while offset<goal:
            block,code,hd=get(BASE+f'chunk?offset={offset}&limit={min(2*1024*1024,goal-offset)}')
            hd={k.lower():v for k,v in hd.items()};digest=hashlib.sha256(block).hexdigest()
            if code!=200 or int(hd['x-capture-offset'])!=offset or hd['x-capture-sha256']!=digest or not block:raise ValueError('CHUNK_INTEGRITY')
            out.write(block);receipts.write(json.dumps(dict(offset=offset,bytes=len(block),sha256=digest))+'\n');offset+=len(block)
    seq={};gaps=[];kinds={};contracts=set();latest={};rows=0;examples={};eligible=[];signals=[];final_rows=[];cohort=[]
    with gzip.open(path,'rb') as stream:
        for line in stream:
            r=json.loads(line);e=r['event'];canonical=json.dumps(e,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
            if hashlib.sha256(canonical).hexdigest()!=r['sha256']:raise ValueError('EVENT_HASH')
            pid=e['identity']['producer_id'];expected=seq.get(pid,0)+1
            if e['identity']['build_sha']!=BUILD or e['identity']['run_id']!=m['run_id'] or e['identity']['source_sha256'] not in m['source_hashes']:raise ValueError('EVENT_IDENTITY')
            if e['sequence']!=expected:gaps.append(dict(producer_id=pid,expected=expected,received=e['sequence']))
            seq[pid]=e['sequence'];rows+=1
            b=e['body'];em=b.get('emission',{});state=em.get('state') or b.get('state') or {}
            kind=em.get('schema',e['kind'])+'|'+str(em.get('phase',''));kinds[kind]=kinds.get(kind,0)+1
            examples[kind]=e
            if e['kind']=='PROTECTED_GENERATION' and (state.get('early') or {}).get('ready') is True:eligible.append(e)
            if em.get('schema')=='BTC15_V81_PASSIVE_EMISSION_V1' and em.get('phase')=='SIGNAL':signals.append(e)
            if e['kind']=='SHADOW_FINAL_COMMITTED_ROW':final_rows.append(e)
            if e['kind']=='NATIVE_COMMITTED_COHORT':cohort.append(e)
            tickers=[v for v in (em.get('ticker'),state.get('contract'),state.get('ticker'),b.get('ticker')) if isinstance(v,str)]
            contracts.update(tickers)
            latest[kind]=dict(wall_ns=e['hook_read']['wall_ns'],tickers=tickers,
                generated_utc=state.get('generated_utc'),source_timestamp_utc=state.get('source_timestamp_utc'),
                target=b.get('target',state.get('target')),close_dt=b.get('close_dt'),seconds_left=b.get('seconds_left'),market=b.get('market'))
            if e.get('prior_dropped'):errors.append('EVENT_DROP_COUNTER')
    if gaps:errors.append('ARCHIVE_SEQUENCE_GAPS')
    if rows!=h['packets']:errors.append('COMMITTED_PACKET_COUNT')
    if set(seq)-{r['producer_id'] for r in records}:errors.append('ARCHIVE_STREAM_UNACCOUNTED')
    result['inspected']=dict(rows=rows,streams=len(seq),bytes=offset,archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),kinds=kinds,contracts=sorted(contracts),gaps=gaps,latest=latest)
    result['result']='FAIL' if errors else 'PASS'
    evidence=dict(last_example_by_kind=examples,eligible_protected=eligible,v81_signals=signals,final_rows=final_rows,native_cohort=cohort,archive_heads=seq)
    (ROOT/('event_ground_zero/results/events-'+MODE+'.json')).write_text(json.dumps(evidence,indent=2)+'\n')
    (folder/('inspection-'+stamp+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    (ROOT/('event_ground_zero/results/live-'+MODE+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    r=probe();a=r['health']['transport_accounting'];e=json.loads((ROOT/('event_ground_zero/results/events-'+MODE+'.json')).read_text())
    print(json.dumps(dict(mode=MODE,result=r['result'],errors=r['errors'],http=r['http_status'],hashes=r['hashes_match'],rows=r['inspected']['rows'],contracts=r['inspected']['contracts'],kinds=r['inspected']['kinds'],created=a['created'],active=a['active'],retired=a['retired'],drops=a['dropped'],retries=a['retried'],eligible=len(e['eligible_protected']),v81_signals=len(e['v81_signals']),final_rows=len(e['final_rows']),cohort_rows=len(e['native_cohort'])),indent=2))
