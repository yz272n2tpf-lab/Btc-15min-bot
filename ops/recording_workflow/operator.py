"""One offline operator entry point. No production launch or remote transport."""
import argparse,importlib.metadata,json,sys,traceback
from pathlib import Path
from .policy import config,validate_config,local_root
from .evidence import index_run,records_for,file_sha
from .report import generate
from .transfer import restore,package
from .staging import make_target,install,rollback
from candidates.early_recording_20261012.archive import canonical

def preflight(c):
    validate_config(c)
    from .staging import ROOT,RELEASE
    target=(ROOT/'ops/recording_workflow/target_dependencies.lock').read_text().splitlines()
    dependencies=[]
    for line in target:
        name,expected=line.split('==')
        try:actual=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:actual='MISSING'
        dependencies.append(dict(name=name,expected=expected,actual=actual,status='VERIFIED' if expected==actual else 'BLOCKED'))
    return dict(status='BLOCKED',offline_rehearsal_allowed=True,live_allowed=False,capture_enabled=c['capture_enabled'],
        target_release=RELEASE,running_bytes_verified=False,dependencies=dependencies,
        historical_archive_access='BLOCKED',production_retrieval='BLOCKED',long_test='NO_GO')

def finalize(root,output,*,health=None,verification_limits=None):
    root=Path(root);output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    idx=index_run(root,output/'index')
    report=generate(root,output/'index',output/'report',health=health,verification_limits=verification_limits)
    return dict(index=idx,report=report)

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    for cmd in ('preflight','status'):
        q=s.add_parser(cmd);q.add_argument('--config',required=True)
    q=s.add_parser('rehearse');q.add_argument('--output',required=True)
    q=s.add_parser('finalize');q.add_argument('--root',required=True);q.add_argument('--output',required=True);q.add_argument('--limits')
    q=s.add_parser('verify-run');q.add_argument('--root',required=True);q.add_argument('--index',required=True);q.add_argument('--output',required=True);q.add_argument('--limits')
    q=s.add_parser('package');q.add_argument('--root',required=True);q.add_argument('--finalized',required=True);q.add_argument('--store',required=True)
    q=s.add_parser('restore');q.add_argument('--manifest',required=True);q.add_argument('--sha256',required=True);q.add_argument('--output',required=True)
    for cmd in ('make-target','install','rollback'):
        q=s.add_parser(cmd);q.add_argument('--target',required=True)
    q=s.add_parser('retrieve');q.add_argument('--root',required=True);q.add_argument('--index',required=True);q.add_argument('--output',required=True);q.add_argument('--contract');q.add_argument('--start',type=float);q.add_argument('--end',type=float);q.add_argument('--max-bytes',type=int,default=16*1024**2)
    q=s.add_parser('remote-export');q.add_argument('--proposal-only',action='store_true')
    a=p.parse_args()
    if a.command=='preflight':result=preflight(json.loads(Path(a.config).read_bytes()))
    elif a.command=='status':
        c=validate_config(json.loads(Path(a.config).read_bytes()));root=Path(c['root'])
        receipt=root/'terminal-status.json'
        result=json.loads(receipt.read_bytes()) if receipt.exists() else dict(status='INCOMPLETE_OR_NOT_STARTED',live_health='Use in-memory Capture.status plus stderr; stale disk file is not a live health check',capture_enabled=c['capture_enabled'])
    elif a.command=='rehearse':
        from .rehearsal import run
        result=run(a.output)
    elif a.command=='finalize':result=finalize(a.root,a.output,verification_limits=json.loads(Path(a.limits).read_bytes()) if a.limits else None)
    elif a.command=='verify-run':
        from .whole_run import verify_run
        result=verify_run(a.root,a.index,a.output,budget=json.loads(Path(a.limits).read_bytes()) if a.limits else None)
    elif a.command=='package':
        f=Path(a.finalized);result=package(a.root,f/'index',a.store,quota=512*1024**2,
            identity=json.loads((Path(a.root)/'identity.json').read_bytes()),report=f/'report/quality.json')
    elif a.command=='restore':result=restore(a.manifest,a.output,expected_sha256=a.sha256)
    elif a.command=='retrieve':
        import gzip
        if not 0<a.max_bytes<=32*1024**2:raise ValueError('RETRIEVAL_LIMIT')
        rs,scope=records_for(a.root,a.index,contract=a.contract,start=a.start,end=a.end,max_bytes=a.max_bytes)
        destination=local_root(a.output)
        if destination.exists():raise ValueError('NEW_RETRIEVAL_DESTINATION')
        destination.mkdir(parents=True)
        with gzip.open(destination/'records.jsonl.gz','wb') as f:
            for r in rs:f.write(canonical(r)+b'\n')
        result=dict(scope,records=len(rs),path=str(destination/'records.jsonl.gz'),sha256=file_sha(destination/'records.jsonl.gz'))
        (destination/'receipt.json').write_bytes(canonical(result))
    elif a.command=='make-target':result=make_target(a.target)
    elif a.command=='install':result=install(a.target)
    elif a.command=='rollback':result=rollback(a.target)
    else:
        result=dict(status='BLOCKED',operation='Existing MAIN sqlite3 mode=ro Connection.backup + matching sealed segments',
            reason='No supported remote filesystem/exec/export action; no private production delivery route available',
            service='ab28dca6-7bea-4956-bdb9-dbb7b4c74635',deployment='d6f84479-d722-4139-a96d-6aa155a17dc6',
            release='4f9ffe51ff9af6adf3f1eb0bd4a77f91dc2caa7c',executed=False)
    print(json.dumps(result,sort_keys=True));return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        # Failure report is on stderr even if the archive disk has failed.
        print(json.dumps(dict(status='FAILED',complete_evidence=False,error=type(exc).__name__,reason=str(exc)[:300])),file=sys.stderr)
        raise
