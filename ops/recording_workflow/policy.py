"""Explicit local-run budgets; no allocation, deletion, cloud or production action."""
from pathlib import Path
import json, math, os
MiB=1024**2
GiB=1024**3
FLAGS=dict(signal_only=True,orders=False,production_enabled=False,actionable=False)

def validate_policy(p):
    if p.get('schema')!='BTC15_LOCAL_STORAGE_POLICY_V1' or p.get('reclaim') is not False:
        raise ValueError('NO_RECLAMATION_POLICY')
    for k in ('per_archive_bytes','archive_instances','index_bytes','package_bytes','backlog_bytes','reserve_bytes','total_bytes'):
        if type(p.get(k)) is not int or p[k]<=0:raise ValueError('INVALID_STORAGE_BUDGET:'+k)
    if p['per_archive_bytes']>128*GiB or p['archive_instances']!=2:raise ValueError('BOUNDED_ARCHIVE_PLAN')
    if p['total_bytes']<sum([p['per_archive_bytes']*p['archive_instances'],p['index_bytes'],p['package_bytes'],p['backlog_bytes'],p['reserve_bytes']]):
        raise ValueError('AGGREGATE_STORAGE_UNDERBUDGET')
    if p.get('duration_seconds',0)<86400+120+420 or p.get('margin',0)<1.5:raise ValueError('DURATION_OR_MARGIN')
    return p

def local_policy():
    return validate_policy(dict(schema='BTC15_LOCAL_STORAGE_POLICY_V1',reclaim=False,
        per_archive_bytes=256*MiB,archive_instances=2,index_bytes=128*MiB,package_bytes=512*MiB,
        backlog_bytes=512*MiB,reserve_bytes=128*MiB,total_bytes=1792*MiB,
        duration_seconds=86400+120+420,margin=1.5,qualified_24h=False,
        basis='BOUNDED_LOCAL_REHEARSAL_ONLY_NOT_24H_CAPACITY'))

def proposed_policy(measured_bytes_per_second):
    # All roles measured together; assign EACH archive the worst aggregate bound.
    horizon=86400+120+420
    per=max(GiB,math.ceil(measured_bytes_per_second*horizon*1.5/GiB)*GiB)
    if per>128*GiB:raise ValueError('EXCEEDS_REVIEWABLE_STORAGE_LIMIT')
    # Raw retained once, reader/offload copy once, temporary full-copy worst case,
    # index and interrupted transfer + restart reserve all accounted independently.
    return validate_policy(dict(schema='BTC15_LOCAL_STORAGE_POLICY_V1',reclaim=False,
        per_archive_bytes=per,archive_instances=2,index_bytes=max(GiB,per//2),
        package_bytes=2*per,backlog_bytes=2*per,reserve_bytes=2*GiB,
        total_bytes=6*per+max(GiB,per//2)+2*GiB,duration_seconds=horizon,
        margin=1.5,qualified_24h=False,basis='MEASURED_FIXTURE_PROJECTION_REQUIRES_LIVE_QUALIFICATION'))

def local_root(path):
    p=Path(path).absolute()
    # No symlink traversal or protected production filesystem, even via aliases.
    if any(x.is_symlink() for x in [p,*p.parents]):raise ValueError('SYMLINK_PATH')
    p=p.resolve()
    if str(p) in ('/','/data','/app') or p.is_relative_to('/data') or p.is_relative_to('/app'):
        raise ValueError('PROTECTED_PATH')
    return p

def config(root, *, enabled=False, run_id='fixture-rollover', policy=None):
    return dict(schema='BTC15_STAGING_CONFIG_V1',capture_enabled=enabled,
        mode='OFFLINE_FIXTURE',run_id=run_id,root=str(local_root(root)),
        health_channel='STDERR_AND_MEMORY',storage=policy or local_policy(),
        ingress=dict(queue_size=16384,queue_bytes=32*MiB),**FLAGS)

def validate_config(c):
    if c.get('schema')!='BTC15_STAGING_CONFIG_V1' or c.get('mode')!='OFFLINE_FIXTURE':
        raise ValueError('LIVE_INSTALLATION_NOT_AUTHORIZED')
    if any(c.get(k)!=v for k,v in FLAGS.items()):raise ValueError('RESEARCH_FLAGS')
    if not isinstance(c.get('run_id'),str) or not c['run_id'].replace('-','').isalnum():raise ValueError('RUN_ID')
    ingress=c.get('ingress',dict(queue_size=64,queue_bytes=8*MiB))
    if set(ingress)!={'queue_size','queue_bytes'} or not 1<=ingress['queue_size']<=16384 or not 1<=ingress['queue_bytes']<=32*MiB:raise ValueError('INGRESS_BUDGET')
    local_root(c['root']);validate_policy(c['storage']);return c
