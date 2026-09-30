"""Read-only pre-live hard gate. Never request native strategy evaluation."""
import concurrent.futures,gzip,hashlib,json,time,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HOSTS={'main':'btc-15min-bot-production.up.railway.app','v81':'v81-live-diagnostics-production.up.railway.app'}
BUILDS={'main':'abe212b513827c8cec28a2f64e0161e79296bd82','v81':'b05723ec622f901a05402ecf27f4d33505753ef1'}
PAYLOAD=json.loads((ROOT/'capture_repair/results/payload.json').read_text())
EXPECTED={n:hashlib.sha256(s.encode()).hexdigest() for n,s in PAYLOAD.items() if n.startswith('capture2/')}

def get(url):
    with urllib.request.urlopen(url,timeout=15) as r:return r.read(2*1024*1024+1),r.status,dict(r.headers)

def probe(mode):
    base='https://'+HOSTS[mode]+'/ground-zero/';stamp=str(time.time_ns())
    raw,status,headers=get(base+'manifest');d=json.loads(raw);m=d['manifest'];h=d['health']
    folder=ROOT/'capture_repair/fresh'/mode/m['run_id'];folder.mkdir(parents=True,exist_ok=True)
    (folder/('manifest-'+stamp+'.json')).write_bytes(raw)
    receipt={'url':base+'manifest','http_status':status,'observed_wall_ns':time.time_ns(),'sha256':hashlib.sha256(raw).hexdigest()}
    (folder/('http-'+stamp+'.json')).write_text(json.dumps(receipt)+'\n')
    errors=[]
    if m.get('build')!=BUILDS[mode] or m.get('native_strategy_commit')!=BUILDS[mode]:errors.append('STRATEGY_BINDING')
    if m.get('capture_files')!=EXPECTED:errors.append('PAYLOAD_HASH_BINDING')
    if m.get('signal_only') is not True or m.get('orders') is not False:errors.append('SAFETY')
    if h.get('invalid') or h.get('producer_drop_observed') or h.get('sequence_gaps'):errors.append('PRODUCER_LOSS_OR_INVALID')
    if h.get('status')!='RECORDING_OPERATIONAL_UNCERTIFIED':errors.append('WRITER_'+str(h.get('status')))
    transports=h.get('transport_status',{})
    if not h.get('packets'):errors.append('NO_PRODUCER_PACKETS')
    if not transports:errors.append('NO_TRANSPORT_ACCOUNTING')
    for pid in h.get('streams',{}):
        if pid not in transports:errors.append('MISSING_TRANSPORT_ACCOUNTING:'+pid)
    for pid,v in transports.items():
        if v.get('producer_dropped') or v.get('rejected') or v.get('last_transport_error') or v.get('finished'):
            errors.append('TRANSPORT_FAILURE:'+pid)
        if v.get('pending_bytes',0)>v.get('max_bytes',0) or v.get('pending_packets',0)>v.get('max_packets',0):errors.append('UNBOUNDED_TRANSPORT:'+pid)
    result={'mode':mode,'run_id':m['run_id'],'http_status':status,'hashes_match':m.get('capture_files')==EXPECTED,'errors':errors,'health':h}
    # Preserve a bounded archive prefix even when the gate fails; do not wait for
    # events or reinterpret missing evidence. Full raw chronology stays untouched.
    path=folder/'packets.jsonl.gz';offset=path.stat().st_size if path.exists() else 0;goal=h['bytes']
    if goal<=16*1024*1024:
        with path.open('ab') as out,(folder/'receipts.jsonl').open('a') as receipts:
            while offset<goal:
                block,code,hd=get(base+f'chunk?offset={offset}&limit={min(2*1024*1024,goal-offset)}')
                hd={k.lower():v for k,v in hd.items()};digest=hashlib.sha256(block).hexdigest()
                if code!=200 or int(hd['x-capture-offset'])!=offset or hd['x-capture-sha256']!=digest or not block:raise ValueError('CHUNK_INTEGRITY')
                out.write(block);receipts.write(json.dumps(dict(offset=offset,bytes=len(block),sha256=digest))+'\n');offset+=len(block)
        rows=0;seq={};gaps=[];kinds={};contracts=set();times=[]
        with gzip.open(path,'rb') as stream:
            for line in stream:
                r=json.loads(line);e=r['event'];canonical=json.dumps(e,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
                if hashlib.sha256(canonical).hexdigest()!=r['sha256']:raise ValueError('EVENT_HASH')
                pid=e['identity']['producer_id'];expected=seq.get(pid,0)+1
                if e['sequence']!=expected:gaps.append({'producer_id':pid,'expected':expected,'received':e['sequence']})
                seq[pid]=e['sequence'];rows+=1;times.append(e['hook_read']['wall_ns'])
                b=e['body'];em=b.get('emission',{});state=em.get('state') or b.get('state') or {}
                kind=em.get('schema',e['kind'])+'|'+str(em.get('phase',''));kinds[kind]=kinds.get(kind,0)+1
                for ticker in (em.get('ticker'),state.get('contract'),state.get('ticker'),b.get('ticker')):
                    if isinstance(ticker,str):contracts.add(ticker)
                if e.get('prior_dropped'):errors.append('EVENT_DROP_COUNTER')
        if gaps:errors.append('ARCHIVE_SEQUENCE_GAPS')
        result['inspected']={'rows':rows,'bytes':offset,'archive_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'kinds':kinds,'contracts':sorted(contracts),'gaps':gaps,'first_wall_ns':min(times) if times else None,'last_wall_ns':max(times) if times else None}
    else:result['archive_not_downloaded_reason']='PRELIVE_SIZE_BOUND'
    result['result']='FAIL' if errors else 'PASS'
    (folder/('inspection-'+stamp+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    result={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(probe,mode):mode for mode in HOSTS}
        for future,mode in futures.items():
            try:result[mode]=future.result()
            except Exception as e:result[mode]={'result':'FAIL','error':type(e).__name__+':'+str(e)}
    path=ROOT/'capture_repair/results/prelive.json';path.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
