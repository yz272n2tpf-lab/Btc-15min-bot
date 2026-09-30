"""Read only the reviewed detached writer; never request a native evaluation."""
import argparse,hashlib,json,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HOSTS={'main':'btc-15min-bot-production.up.railway.app','v81':'v81-live-diagnostics-production.up.railway.app'}
BUILDS={'main':'abe212b513827c8cec28a2f64e0161e79296bd82','v81':'b05723ec622f901a05402ecf27f4d33505753ef1'}
PAYLOAD=json.loads((ROOT/'capture2/results/payload.json').read_text())

def get(url):
    with urllib.request.urlopen(url,timeout=12) as response:
        return response.read(2*1024*1024+1),dict(response.headers)

def acquire(mode):
    base='https://'+HOSTS[mode]+'/ground-zero/'
    raw,headers=get(base+'manifest');manifest=json.loads(raw);m=manifest['manifest'];h=manifest['health']
    assert m['build']==BUILDS[mode] and m['native_strategy_commit']==BUILDS[mode],'BUILD_BINDING'
    assert m['signal_only'] is True and m['orders'] is False,'SAFETY'
    expected={n:hashlib.sha256(s.encode()).hexdigest() for n,s in PAYLOAD.items() if n.startswith('capture2/')}
    assert m['capture_files']==expected,'CAPTURE_FILE_BINDING'
    folder=ROOT/'capture_activation/fresh'/mode/m['run_id'];folder.mkdir(parents=True,exist_ok=True)
    stamp=str(time.time_ns());(folder/('manifest-'+stamp+'.json')).write_bytes(raw)
    (ROOT/'capture_activation/fresh'/mode/'latest.json').write_bytes(raw)
    path=folder/'packets.jsonl.gz';offset=path.stat().st_size if path.exists() else 0;goal=h['bytes']
    assert offset<=goal,'ARCHIVE_REGRESSION'
    with path.open('ab') as stream,(folder/'receipts.jsonl').open('a') as receipts:
        while offset<goal:
            limit=min(2*1024*1024,goal-offset);data,hd=get(base+f'chunk?offset={offset}&limit={limit}')
            hd={k.lower():v for k,v in hd.items()}
            assert int(hd['x-capture-offset'])==offset and 0<len(data)<=limit,'RANGE'
            sha=hashlib.sha256(data).hexdigest();assert sha==hd['x-capture-sha256'],'CHUNK_HASH'
            stream.write(data);receipts.write(json.dumps(dict(offset=offset,bytes=len(data),sha256=sha,observed_ns=time.time_ns()))+'\n');offset+=len(data)
    print(json.dumps(dict(mode=mode,run=m['run_id'],health={k:h[k] for k in ('status','packets','invalid','producer_drop_observed')},streams=len(h['streams']),sequence_gaps=len(h['sequence_gaps']),retained_bytes=offset)),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=0);a=p.parse_args();until=time.monotonic()+a.seconds
    while True:
        for mode in HOSTS:
            try:acquire(mode)
            except Exception as e:print(mode,type(e).__name__,str(e),flush=True)
        if time.monotonic()>=until:break
        time.sleep(min(30,max(0,until-time.monotonic())))
