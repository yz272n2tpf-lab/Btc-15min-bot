"""Read-only Oct-13 recorder writer/drain diagnostics using pinned SSH identity."""
import json
import shlex
from research.main_closeout_incremental_20261015.verify_isolated_railway_ssh_main import (
    check_local, scan_host, run, stop, KEY, KNOWN, GATEWAY
)
from research.main_closeout_incremental_20261015.verify_isolated_railway_ssh_transfer import PRODUCTION

REMOTE = r"""
import json,pathlib
from pathlib import Path
root=Path('/data/btc15_recordings/PF_20261013_4d0f8ed15e')
out={}
for role in ('main','information','v81'):
    p=root/role
    if not p.is_dir():continue
    result={}
    for name in ('health.json','terminal-status.json','seal.json'):
        f=p/name
        if not f.is_file() or f.is_symlink() or f.stat().st_size>1048576:
            result[name]={'present':False};continue
        x=json.loads(f.read_bytes())
        details={'present':True}
        if name in ('health.json','terminal-status.json'):
            details.update({k:x.get(k) for k in ('status','reason','failure','stopped','elapsed','records','raw_bytes','compressed_bytes','stopped_at')})
            w=x.get('writer') or {}
            details['writer']={k:w.get(k) for k in ('queued_bytes','peak_queued_bytes','queue_byte_budget','queue_capacity','archive_failed','losses')}
            hooks=x.get('hooks') or {}
            details['hooks']={k:v for k,v in hooks.items() if k in ('max_ns','over_1ms','calls') and isinstance(v,(int,float))}
        if name=='seal.json':
            details.update({k:x.get(k) for k in ('status','last_sequence','last_sha256')})
        result[name]=details
    out[role]=result
print('BTC15_OCT13_DRAIN_DIAG '+json.dumps(out,sort_keys=True))
"""


def main():
    check_local()
    scan_host()
    for name,(domain,identity,role) in PRODUCTION.items():
        cmd=["ssh","-T","-oBatchMode=yes","-oIdentitiesOnly=yes",
             "-oStrictHostKeyChecking=yes","-oUserKnownHostsFile="+str(KNOWN),
             "-oGlobalKnownHostsFile=/dev/null","-oCheckHostIP=no",
             "-oConnectTimeout=10","-oConnectionAttempts=1",
             "-i",str(KEY),domain+"@"+GATEWAY,"python -B -c "+shlex.quote(REMOTE)]
        r=run(cmd,45)
        if r.returncode:
            stop(name+"_OCT13_DIAGNOSTICS_FAILED","exit="+str(r.returncode)+" stderr="+r.stderr[:230])
        lines=[line[len("BTC15_OCT13_DRAIN_DIAG "):] for line in r.stdout.splitlines() if line.startswith("BTC15_OCT13_DRAIN_DIAG ")]
        if len(lines)!=1:stop(name+"_OCT13_DIAG_OUTPUT_MISSING")
        data=json.loads(lines[0])
        permitted={'MAIN':{'main','information'},'V81':{'v81'}}[name]
        filtered={k:v for k,v in data.items() if k in permitted}
        print("BTC15_OCT13_DRAIN_DIAGNOSTICS "+json.dumps({"service":name,"capture":filtered,"source_read_only":True,"production_changes":False},sort_keys=True),flush=True)


if __name__=="__main__":main()
