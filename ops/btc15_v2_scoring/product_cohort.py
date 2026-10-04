"""Explicit reviewed product partition for the EXISTING bridge, never a new scorer."""
from contextlib import contextmanager
from copy import deepcopy
from btc15_v2_product.release import read_receipt,data_root
from btc15_v2_product import REVISION

@contextmanager
def configured(bridge,path,sha,allow_fixture=False):
    receipt=read_receipt(path,sha)
    bridge.require(receipt['evidence_class']=='PRODUCTION' or allow_fixture,'FIXTURE_NOT_PRODUCTION')
    saved=(bridge.IDENTITIES,bridge.FIRST_POSSIBLE_OPEN,bridge.ACTIVE_RELEASE)
    bridge.IDENTITIES={lane:dict(build=v['build'],service=v['service'],deployment=v['deployment'],interval=15 if lane=='main' else 6)
                       for lane,v in receipt['lanes'].items()}
    bridge.FIRST_POSSIBLE_OPEN=(int(max(v['started_at'] for v in receipt['lanes'].values())//900)+1)*900
    bridge.ACTIVE_RELEASE=receipt
    try:yield
    finally:bridge.IDENTITIES,bridge.FIRST_POSSIBLE_OPEN,bridge.ACTIVE_RELEASE=saved

def validate_meta(bridge,m,lane):
    r=bridge.ACTIVE_RELEASE
    if r is None:
        bridge.require('product_revision' not in m['meta'],'NEW_PRODUCT_REQUIRES_REVIEWED_RECEIPT')
        return
    meta=m['meta'];v=r['lanes'][lane]
    bridge.require(meta.get('product_revision')==REVISION and meta.get('build')==v['build'] and meta.get('deployment')==v['deployment'],'PRODUCT_COHORT_METADATA')

def validate_record(bridge,record,lane):
    r=bridge.ACTIVE_RELEASE
    if r is None:
        bridge.require('product' not in record,'NEW_PRODUCT_REQUIRES_REVIEWED_RECEIPT');return
    p=record.get('product') or {};v=r['lanes'][lane]
    bridge.require(p.get('revision')==REVISION and p.get('lane')==lane and p.get('build')==v['build'] and p.get('deployment')==v['deployment'] and bool(p.get('runtime_epoch')),'MIXED_OR_UNREVIEWED_PRODUCT_EVENT')

def source(bridge,lane):
    return str(data_root(bridge.ACTIVE_RELEASE,lane)/(lane+'.sqlite3')) if bridge.ACTIVE_RELEASE else '/data/btc15_ladders_v2/'+lane+'.sqlite3'
