"""Fail-closed reviewed bytes and deployment/cohort binding. Offline by default."""
import hashlib
import json
import os
from pathlib import Path
import re
import math
import time
import uuid
from . import REVISION,STRATEGY

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'BTC15_V2_PRODUCT_RELEASE_R1.json'
FROZEN={'main':'de4f3e20b8657eb8cfee91bd4e525c103b5bf513','v81':'60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1'}
SERVICES={'main':'ab28dca6-7bea-4956-bdb9-dbb7b4c74635','v81':'6025e83e-a41c-4e0a-8c16-f71120bd501b'}
VOLUMES={'main':'6ced6b1a-3755-4518-a240-c895e936d443','v81':'d5eeafca-e0fc-42f0-b7d1-4705907720c6'}
PROJECT='baea4e22-d004-4434-b2c5-81a7fbc05086';ENVIRONMENT='61775c5d-c583-4dfc-af41-f25578856fd9'

def verify_files(lane,root=ROOT):
    from btc15_verify_ladder_freeze_v2 import verify
    verify(root,lane)  # Original full freeze remains mandatory, never rewritten.
    root=Path(root);m=json.loads((root/MANIFEST.name).read_text())
    if m.get('revision')!=REVISION or m.get('strategy')!=STRATEGY or m.get('orders') is not False:raise ValueError('RELEASE_MANIFEST_IDENTITY')
    for name,expected in m['files_sha256'].items():
        p=(root/name).resolve()
        if not p.is_relative_to(root.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError('RELEASE_FILE_MISMATCH:'+name)
    for name,expected in m['lane_protected_files'][lane].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:raise ValueError('SOURCE_MODEL_OR_DEPENDENCY_CHANGED:'+name)
    return m

def read_receipt(path,expected_sha):
    raw=Path(path).read_bytes()
    if not expected_sha or hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('REVIEWED_RECEIPT_HASH_REQUIRED')
    r=json.loads(raw)
    if (r.get('schema')!='BTC15_V2_RELEASE_RECEIPT_R1' or r.get('revision')!=REVISION
        or r.get('strategy')!=STRATEGY or r.get('signal_only') is not True or r.get('orders') is not False
        or r.get('project')!=PROJECT or r.get('environment')!=ENVIRONMENT):raise ValueError('RELEASE_RECEIPT_IDENTITY')
    if r.get('evidence_class') not in ('PRODUCTION','FIXTURE'):raise ValueError('RECEIPT_CLASS')
    for lane in ('main','v81'):
        v=r['lanes'][lane]
        if (v.get('service')!=SERVICES[lane] or v.get('volume')!=VOLUMES[lane]
            or not re.fullmatch('[0-9a-f]{40}',v.get('build','')) or v['build']==FROZEN[lane]
            or not re.fullmatch('[0-9a-f-]{36}',v.get('deployment',''))
            or type(v.get('started_at')) not in (int,float) or not math.isfinite(v['started_at']) or v['started_at']<=0):raise ValueError('RELEASE_LANE_IDENTITY:'+lane)
    if r.get('manifest_sha256')!=hashlib.sha256(MANIFEST.read_bytes()).hexdigest():raise ValueError('RELEASE_MANIFEST_RECEIPT_MISMATCH')
    return r

def data_root(receipt,lane):
    return Path('/data/btc15_v2_product')/REVISION/receipt['lanes'][lane]['deployment']

def verify_environment(lane):
    verify_files(lane)
    path=os.getenv('BTC15_V2_RELEASE_RECEIPT')
    if path:
        r=read_receipt(path,os.getenv('BTC15_V2_RELEASE_RECEIPT_SHA256'))
        if r['evidence_class']!='PRODUCTION':raise ValueError('FIXTURE_CANNOT_START_PRODUCTION')
        lane_receipt=r['lanes'][lane]
    else:
        # Deployment IDs are allocated by Railway after approval/build creation.
        # Start authorization pins reviewed content + git build + existing service/volume.
        # This runtime identity is NOT sufficient for production scoring; that still
        # requires a separate control-plane-verified exact deployment receipt.
        digest=hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
        build=os.getenv('BTC15_V2_APPROVED_BUILD','')
        if os.getenv('BTC15_V2_APPROVED_MANIFEST_SHA256')!=digest or not re.fullmatch('[0-9a-f]{40}',build) or build==FROZEN[lane]:
            raise ValueError('DEPLOYMENT_NOT_AUTHORIZED_NO_REVIEWED_RELEASE')
        deployment=os.getenv('RAILWAY_DEPLOYMENT_ID','')
        try:uuid.UUID(deployment)
        except ValueError:raise ValueError('DEPLOYMENT_ID_REQUIRED') from None
        if deployment in ('ce0ac4dd-a3c4-49bb-8ca7-d1b7ed5be2fa','2051e772-bd39-4dea-a77d-52fea0a07c02'):raise ValueError('FROZEN_DEPLOYMENT_ID_FORBIDDEN')
        lane_receipt=dict(build=build,service=SERVICES[lane],volume=VOLUMES[lane],deployment=deployment,started_at=time.time())
        r=dict(schema='BTC15_V2_RUNTIME_IDENTITY_R1',revision=REVISION,strategy=STRATEGY,
            evidence_class='RUNTIME_ONLY_NOT_CONTROL_PLANE_VERIFIED',lanes={lane:lane_receipt},
            manifest_sha256=digest,signal_only=True,orders=False)
    expected=dict(RAILWAY_PROJECT_ID=PROJECT,RAILWAY_ENVIRONMENT_ID=ENVIRONMENT,
        RAILWAY_SERVICE_ID=lane_receipt['service'],RAILWAY_DEPLOYMENT_ID=lane_receipt['deployment'],
        RAILWAY_GIT_COMMIT_SHA=lane_receipt['build'],RAILWAY_VOLUME_ID=lane_receipt['volume'],RAILWAY_VOLUME_MOUNT_PATH='/data')
    for k,v in expected.items():
        if os.getenv(k)!=v:raise ValueError('RUNTIME_RECEIPT_MISMATCH:'+k)
    desired=str(data_root(r,lane))
    if os.getenv('BTC15_LADDER_DATA_ROOT',desired)!=desired:raise ValueError('COHORT_ROOT_OVERRIDE_FORBIDDEN')
    os.environ['BTC15_LADDER_DATA_ROOT']=desired
    os.environ['BTC15_COHORT_EVIDENCE_PATH']=str(Path(desired)/'native-cohort.jsonl')
    print('V2 PRODUCT RUNTIME | '+json.dumps(r,sort_keys=True,separators=(',',':')),flush=True)
    return r
