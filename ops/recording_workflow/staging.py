"""Allowlisted local overlay installation and byte-exact rollback; never launch."""
from pathlib import Path
import hashlib,json,os,subprocess,tarfile,io
from .policy import local_root
from .evidence import file_sha
from candidates.early_recording_20261012.archive import canonical
ROOT=Path(__file__).resolve().parents[2]
RELEASE='4f9ffe51ff9af6adf3f1eb0bd4a77f91dc2caa7c'
WRITERS=['btc15_information_journal_v1.py','btc15_information_service_v1.py','btc15_quote_proof_offpath_v1.py']

def allowlist():
    return WRITERS+['ops/recording_workflow/target_dependencies.lock']+sorted(str(p.relative_to(ROOT)) for base in ('candidates/early_recording_20261012','ops/recording_workflow')
        for p in (ROOT/base).glob('*.py') if not p.name.startswith('test_'))

def make_target(target):
    target=local_root(target)
    if target.exists():raise ValueError('NEW_TARGET_REQUIRED')
    raw=subprocess.check_output(['git','archive',RELEASE],cwd=ROOT)
    target.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(raw)) as f:
        for m in f:
            if m.isdir():continue
            if not m.isfile() or '..' in Path(m.name).parts or Path(m.name).is_absolute():raise ValueError('RELEASE_ARCHIVE_MEMBER')
            p=target/m.name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(f.extractfile(m).read())
    manifest={str(p.relative_to(target)):file_sha(p) for p in target.rglob('*') if p.is_file()}
    (target/'LOCAL_STAGING_TARGET.json').write_bytes(canonical(dict(release=RELEASE,files=manifest,never_launch=True)))
    return dict(target=str(target),release=RELEASE,files=len(manifest))

def install(target):
    target=local_root(target);marker=target/'LOCAL_STAGING_TARGET.json'
    if not marker.exists():raise ValueError('LOCAL_TARGET_MARKER_REQUIRED')
    baseline=json.loads(marker.read_bytes())
    if baseline['release']!=RELEASE:raise ValueError('WRONG_RELEASE')
    state=target/'LOCAL_RECORDING_OVERLAY'
    if state.exists():raise ValueError('ALREADY_INSTALLED_OR_INTERRUPTED')
    paths=allowlist()
    # Entire release verified BEFORE any mutation; prevent unreviewed base drift.
    for name,digest in baseline['files'].items():
        if not (target/name).is_file() or file_sha(target/name)!=digest:raise ValueError('TARGET_DRIFT:'+name)
    plan=[]
    for name in paths:
        p=target/name
        if p.exists() and name not in WRITERS:raise ValueError('UNEXPECTED_OVERLAP:'+name)
        plan.append(dict(path=name,before=file_sha(p) if p.exists() else None,after=file_sha(ROOT/name)))
    state.mkdir();(state/'plan.json').write_bytes(canonical(plan))
    for r in plan:
        p=target/r['path'];p.parent.mkdir(parents=True,exist_ok=True)
        if p.exists():
            backup=state/'before'/r['path'];backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(p.read_bytes())
        tmp=p.with_name(p.name+'.recording-local-tmp');tmp.write_bytes((ROOT/r['path']).read_bytes());tmp.replace(p)
    (state/'installed.json').write_bytes(canonical(dict(status='LOCAL_INSTALLED_CAPTURE_DEFAULT_OFF',release=RELEASE,allowlist=plan)))
    return dict(files=len(plan),capture_default=False,release=RELEASE,services_started=0)

def rollback(target):
    target=local_root(target);state=target/'LOCAL_RECORDING_OVERLAY';plan=json.loads((state/'plan.json').read_bytes())
    # Refuse modified overlays; never overwrite new user changes.
    for r in plan:
        p=target/r['path']
        if p.exists() and file_sha(p) not in (r['before'],r['after']):raise ValueError('OVERLAY_DRIFT:'+r['path'])
        if r['before'] is not None:
            b=state/'before'/r['path']
            if not b.exists() or file_sha(b)!=r['before']:raise ValueError('ROLLBACK_BACKUP_HASH')
    for r in reversed(plan):
        p=target/r['path']
        if r['before'] is None:p.unlink(missing_ok=True)
        else:p.write_bytes((state/'before'/r['path']).read_bytes())
    baseline=json.loads((target/'LOCAL_STAGING_TARGET.json').read_bytes())
    for name,digest in baseline['files'].items():
        if file_sha(target/name)!=digest:raise ValueError('ROLLBACK_HASH')
    (state/'rolled_back.json').write_bytes(canonical(dict(status='VERIFIED',original_files=len(baseline['files']),services_restarted=0)))
    return dict(status='VERIFIED',original_files=len(baseline['files']),overlay_files_removed=sum(r['before'] is None for r in plan),services_restarted=0)
