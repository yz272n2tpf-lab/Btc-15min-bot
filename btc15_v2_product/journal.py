"""Product revision metadata around the byte-frozen journal/strategy processors."""
from copy import deepcopy
import json
import os
from pathlib import Path
import time
import uuid
import btc15_ladder_journal_v1 as frozen
from . import REVISION,STRATEGY,ENVELOPE
from .admin import LOCAL

ORIGINAL_JOURNAL=frozen.Journal
ORIGINAL_WORKER=frozen.Worker
ADMINS={}


class RevisionJournal(ORIGINAL_JOURNAL):
    def __init__(self,path,lane):
        # Reject foreign nonempty DBs before opening writable; preserve all history.
        path=Path(path)
        deployment=os.getenv('RAILWAY_DEPLOYMENT_ID','OFFLINE')
        build=os.getenv('RAILWAY_GIT_COMMIT_SHA','OFFLINE')
        if path.exists():
            import sqlite3
            with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
                prior=dict(db.execute('SELECT k,v FROM meta'))
                if prior.get('product_revision')!=REVISION:raise ValueError('FOREIGN_COHORT_ROOT')
                for key,val in [('deployment',deployment),('build',build),('lane',lane)]:
                    if prior.get(key)!=val:raise ValueError('COHORT_IDENTITY_CHANGED:'+key)
        super().__init__(path,lane)
        for key,val in [('product_revision',REVISION),('deployment',deployment),('build',build)]:
            old=self.get(key)
            if old is not None and old!=val:raise ValueError('COHORT_IDENTITY_CHANGED:'+key)
            self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',(key,val))
        self.boot=str(uuid.uuid4());self.startup_slot=int(time.time()//900)*900
        starts=self.get('startup_slots',[])
        if self.startup_slot not in starts:starts.append(self.startup_slot)
        self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',('startup_slots',json.dumps(starts)))
        self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',('runtime_epoch',self.boot))
        self.db.commit()

    def coverage(self,record):
        super().coverage(record)
        slot=int(record['published_ts']//900)*900
        if record['kind'] not in ('SETTLEMENT','BRTI_CLOSEOUT') and slot in self.get('startup_slots',[]):
            self.db.execute('UPDATE contracts SET missing=1 WHERE opened=?',(slot,))

    def commit(self,record,state):
        # New immutable receipt fields do not enter process(), qualify(), origins or state.
        record['product']['runtime_epoch']=self.boot
        handoff=getattr(self,'handoff',None)
        if handoff:
            cursor,view=handoff
            self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',('handoff_cursor',str(cursor)))
            if record.get('kind')!='SETTLEMENT':
                self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',('handoff_view',frozen.packed(view).decode()))
        try:seq=super().commit(record,state)
        except Exception:
            self.db.rollback()
            raise
        admin=ADMINS.get(self.get('lane'))
        if admin:admin.pipeline(record,seq,time.time())
        return seq


class ProcessorEnvelope:
    def __init__(self,processor,lane):self.processor,self.lane=processor,lane;self.identity=None
    def restore(self,saved):return self.processor.restore(saved)
    def process(self,value,now):
        f,attempt_id=value
        record,state,view=self.processor.process(f,now)
        record['product']=dict(revision=REVISION,lane=self.lane,attempt_id=attempt_id,
            deployment=os.getenv('RAILWAY_DEPLOYMENT_ID','OFFLINE'),build=os.getenv('RAILWAY_GIT_COMMIT_SHA','OFFLINE'))
        view.update(schema=ENVELOPE,product_revision=REVISION,lane=self.lane)
        if all(view.get(k) is not None for k in ('contract','target','official_open','official_close')):
            self.identity={k:view[k] for k in ('contract','target','official_open','official_close')}
        if self.identity and self.identity['official_open']<=now<self.identity['official_close'] and view.get('contract')==self.identity['contract']:
            view['official_identity']=dict(self.identity,authority='IDENTITY_ONLY_NOT_ACTION_FRESHNESS')
        admin=ADMINS.get(self.lane)
        if admin:view['administrative_journal']=admin.health()
        return record,state,view


class RevisionWorker(ORIGINAL_WORKER):
    def __init__(self,root,lane,processor,clock=time.time):
        super().__init__(root,lane,ProcessorEnvelope(processor,lane),clock)
    def offer(self,value):
        a=getattr(LOCAL,'attempt',None)
        result=super().offer((value,a['attempt_id'] if a else None)) if value is not None else super().offer(None)
        admin=ADMINS.get(self.lane)
        if admin and a:admin.offered(result,value.get('kind'))
        return result


def install(admin=None):
    if admin:ADMINS[admin.lane]=admin
    frozen.Journal=RevisionJournal;frozen.Worker=worker_for


def worker_for(root,lane,processor,clock=time.time):
    if lane=='v81':
        from .durable_handoff import DurableWorker
        return DurableWorker(root,lane,processor,clock)
    return RevisionWorker(root,lane,processor,clock)


def unavailable(lane,reason,now,value=None):
    value=value or {}
    out=dict(schema=ENVELOPE,product_revision=REVISION,candidate=STRATEGY,lane=lane,
        status='UNAVAILABLE',reason=reason,served_ts=now,historical_only=True,
        signal_only=True,manual_execution_only=True,orders=False)
    identity=value.get('official_identity')
    if identity and identity.get('official_open',now+1)<=now<identity.get('official_close',now):
        out['official_identity']=identity;out['contract']=identity['contract']
        origin=value.get('origin')
        if origin and origin.get('contract')==identity['contract']:out['origin']=origin
    for key in ('published_ts','journal','administrative_journal','handoff'):
        if key in value:out[key]=value[key]
    return out


def public_view(root,lane,now=None):
    now=time.time() if now is None else now
    if lane=='v81':
        from .durable_handoff import ACTIVE
        worker=ACTIVE.get(str(Path(root).resolve()))
        if worker and (worker.failed or worker.pressure or not worker.thread.is_alive()):
            value=unavailable(lane,worker.failed or 'HANDOFF_BACKPRESSURE',now)
            value['handoff']=worker.health()
            return value
    try:
        raw=(Path(root)/(lane+'.json')).read_bytes()
        if len(raw)>frozen.MAX_BYTES:raise ValueError('OVERSIZE_VIEW')
        v=json.loads(raw)
        if lane=='v81' and worker:
            v['handoff']=worker.health()
        try:
            health=(Path(root)/(lane+'.admin-health.json')).read_bytes()
            if len(health)<=4096:v['administrative_journal']=json.loads(health)
        except (OSError,ValueError):pass
        if (v.get('schema')!=ENVELOPE or v.get('product_revision')!=REVISION or v.get('lane')!=lane
            or v.get('candidate')!=STRATEGY or v.get('signal_only') is not True or v.get('orders') is not False):
            raise ValueError('PRODUCT_IDENTITY')
        if v.get('status')=='UNAVAILABLE':return unavailable(lane,v.get('reason','SOURCE_UNAVAILABLE'),now,v)
        if not v['published_ts']<=now<v['expires_at']:return unavailable(lane,'SOURCE_EXPIRED',now,v)
        v['served_ts']=now;return v
    except (OSError,ValueError,KeyError,TypeError):return unavailable(lane,'JOURNAL_UNAVAILABLE',now)
