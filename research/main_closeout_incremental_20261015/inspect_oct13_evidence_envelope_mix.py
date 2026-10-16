"""Read-only bounded original native Oct-13 evidence envelope mix.

No original bytes printed or transferred, never writes to production.
Segments read as complete gzip text; SHA of each envelope is checked.
"""
import json, shlex
from research.main_closeout_incremental_20261015.verify_isolated_railway_ssh_main import (
    check_local, scan_host, run, stop, KEY, KNOWN, GATEWAY
)
from research.main_closeout_incremental_20261015.verify_isolated_railway_ssh_transfer import PRODUCTION

REMOTE = r"""
import collections,gzip,json,glob,hashlib,os,statistics
from pathlib import Path
role=os.environ.get('RAILWAY_SERVICE_ID')
r='v81' if role=='6025e83e-a41c-4e0a-8c16-f71120bd501b' else 'main'
root=Path('/data/btc15_recordings/PF_20261013_4d0f8ed15e')/r/'source.segments'
results=collections.defaultdict(list)
firsts=collections.defaultdict(list)
session=collections.Counter()
bad=collections.Counter()
total=0;raw_count=0
for path in sorted(root.glob('*.jsonl.gz')):
    with gzip.open(path,'rb') as src:
        for raw in src:
            total+=len(raw);raw_count+=1
            if total>256*1024*1024 or raw_count>30000: raise ValueError('LIMIT_EXCEEDED')
            try:
                rec=json.loads(raw);kind=rec.get('kind','UNKNOWN')
                h=rec.pop('sha256',None)
                if h!=hashlib.sha256(json.dumps(rec,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest():bad['SHA']+=1
                session[rec.get('session')]+=1
                results[kind].append(len(raw))
                if kind=='EVIDENCE_GAP':bad['GAP_ENVELOPE']+=1
            except Exception:bad['JSON']+=1
summary={}
for kind,vals in results.items():
    vals.sort()
    summary[kind]={'count':len(vals),'total_bytes':sum(vals),'max_bytes':vals[-1],
        'median_bytes':vals[len(vals)//2],'p95_bytes':vals[int(.95*(len(vals)-1))]}
print('BTC15_NATIVE_ENVELOPE_STATS '+json.dumps(dict(role=r,records=raw_count,raw_bytes=total,by_kind=summary,bad=dict(bad),sessions=len(session)),sort_keys=True))
"""

def main():
    check_local();scan_host()
    for name,(domain,expected,role) in PRODUCTION.items():
        x=run(['ssh','-T','-oBatchMode=yes','-oIdentitiesOnly=yes',
               '-oStrictHostKeyChecking=yes','-oUserKnownHostsFile='+str(KNOWN),
               '-oGlobalKnownHostsFile=/dev/null','-oCheckHostIP=no','-oConnectTimeout=10','-i',str(KEY),
               domain+'@'+GATEWAY,'python -B -c '+shlex.quote(REMOTE)],45)
        if x.returncode:stop(name+'_ENVELOPE_STATS_FAILED',x.stderr[:240])
        rows=[line[len('BTC15_NATIVE_ENVELOPE_STATS '):] for line in x.stdout.splitlines() if line.startswith('BTC15_NATIVE_ENVELOPE_STATS ')]
        if len(rows)!=1:stop(name+'_STATS_RESPONSE_MISSING')
        out=json.loads(rows[0])
        if out.get('role')!=role:stop(name+'_ROLE_MISMATCH')
        print('BTC15_RECORDED_ENVELOPES '+json.dumps(out,sort_keys=True),flush=True)

if __name__=='__main__':main()