"""Bounded GET-only recovery of an existing append-only common JSONL export.

No database opens, mutation methods, source polling, deployment or credentials.
Probe an existing fixed-size prefix; keep range hashes and gzip CRC diagnostics.
This does not certify publisher acquisition timing or native issuance.
"""
import argparse, hashlib, json, urllib.request
from datetime import datetime
from pathlib import Path
from completion_audit.common_journal import scan

BASE='https://scalp-finalprod-clean-v1-production.up.railway.app/research/common-export'

def recover(start,end,out,max_bytes=80_000_000):
    out.mkdir(parents=True,exist_ok=True);requests=[];budget=0
    def read(offset,limit):
        nonlocal budget
        if budget+limit>max_bytes:raise RuntimeError('Explicit bounded read budget exceeded')
        with urllib.request.urlopen(BASE+f'?offset={offset}&limit={limit}',timeout=25)as h:
            data=h.read();headers={k.lower():v for k,v in h.headers.items()}
        budget+=len(data);sha=hashlib.sha256(data).hexdigest()
        assert headers['x-evidence-sha256']==sha
        assert int(headers['x-evidence-offset'])==offset
        p=out/f'range-{offset}-{len(data)}.gz';p.write_bytes(data)
        requests.append(dict(offset=offset,bytes=len(data),sha256=sha,total_bytes=int(headers['x-evidence-total-bytes'])))
        return p,requests[-1]
    def probe(offset):
        p,meta=read(offset,65536);damage=[];members=list(scan(p,damage))
        if not members:raise RuntimeError('No complete gzip member in probe')
        timed=[m for m in members if m['record'].get('recorded_utc')]
        if not timed:raise RuntimeError('No observation clock in bounded probe')
        first=timed[0];when=first['record']['recorded_utc']
        return datetime.fromisoformat(when).timestamp(),offset+first['offset'],meta
    first,_,meta=probe(0);size=meta['total_bytes']
    last,_,_=probe(size-65536)
    a=datetime.fromisoformat(start.replace('Z','+00:00')).timestamp();b=datetime.fromisoformat(end.replace('Z','+00:00')).timestamp()
    if not first<=a<b<=last:raise RuntimeError('Requested period outside retained prefix')
    lo=0;hi=size-65536
    # Bounded monotonic-time lookup. All decoded records are verified afterward;
    # probes are not statistical samples or decision frames.
    for _ in range(40):
        if hi-lo<=65536:break
        mid=(lo+hi)//2;when,aligned,_=probe(mid)
        if when<a:lo=mid
        else:hi=mid
    offset=max(0,lo-65536);parts=[]
    while offset<size:
        p,m=read(offset,min(4_000_000,size-offset));parts.append(p)
        damage=[];records=list(scan(p,damage))
        timed=[m for m in records if m['record'].get('recorded_utc')]
        if timed and datetime.fromisoformat(timed[-1]['record']['recorded_utc']).timestamp()>=b:break
        offset+=m['bytes']
    whole=out/'bounded.gz'
    with whole.open('wb')as f:
        for p in parts:f.write(p.read_bytes())
    damage=[];records=[];prior=None
    for m in scan(whole,damage):
        r=m['record'];when=r.get('recorded_utc')or r.get('observed_utc')
        if not when:continue
        t=datetime.fromisoformat(when).timestamp()
        if r.get('recorded_utc'):
            if prior is not None and t<prior:raise RuntimeError('Nonmonotonic retained observation clock')
            prior=t
        if a<=t<b:records.append(r)
    # Partial edge members are expected; internal corruption is not accepted.
    internal=[d for d in damage if d['start']!=0 and d['end']!=whole.stat().st_size]
    if internal:raise RuntimeError('Internal damaged range: '+str(internal))
    path=out/'records.jsonl';path.write_text(''.join(json.dumps(r,separators=(',',':'))+'\n'for r in records))
    summary=dict(start=start,end=end,prefix_bytes=size,read_bytes=budget,requests=requests,
        records=len(records),first=(records[0].get('recorded_utc')or records[0].get('observed_utc'))if records else None,
        last=(records[-1].get('recorded_utc')or records[-1].get('observed_utc'))if records else None,edge_damage=damage,internal_damage=internal,
        run_ids=sorted({r.get('run_id','')for r in records}),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        signal_only=True,orders=False)
    (out/'recovery.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items()if k not in ['requests','edge_damage']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--start',required=True);p.add_argument('--end',required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--max-bytes',type=int,default=80_000_000);a=p.parse_args();recover(a.start,a.end,a.out,a.max_bytes)
