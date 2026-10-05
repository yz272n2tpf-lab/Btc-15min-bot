"""Product revision metadata around the byte-frozen journal/strategy processors."""
from copy import deepcopy
import json
import os
from pathlib import Path
import queue
import threading
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
        seq=super().commit(record,state)
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
        self.replay_lock=threading.Lock()
        self.replay_committed=self.replay_waits=self.replay_failures=0
        super().__init__(root,lane,ProcessorEnvelope(processor,lane),clock)

    def _replay_status(self,status):
        receipt=dict(schema='BTC15_CLOSEOUT_BACKPRESSURE_R1',lane=self.lane,status=status,
            committed=self.replay_committed,waits=self.replay_waits,failures=self.replay_failures,
            accepted=self.accepted,written=self.written,drops=self.dropped,queue_depth=self.queue.qsize(),
            reason=self.failed,signal_only=True,orders=False)
        print('LADDER CLOSEOUT REPLAY | '+json.dumps(receipt),flush=True)
        admin=ADMINS.get(self.lane)
        if admin:admin.offer(receipt)

    def _replay_healthy(self):
        if self.failed or not self.thread.is_alive():
            raise RuntimeError(self.failed or 'JOURNAL_WORKER_STOPPED')

    def _replay_drain(self):
        # Wait ONLY on the background closeout caller. Native offer stays nonblocking.
        # task_done follows commit (and, for native records, atomic JSON replacement).
        if self.queue.unfinished_tasks:
            self.replay_waits+=1
            if self.replay_waits & (self.replay_waits-1)==0:self._replay_status('BACKPRESSURE')
        with self.queue.all_tasks_done:
            while self.queue.unfinished_tasks:
                self._replay_healthy()
                self.queue.all_tasks_done.wait(.1)
        self._replay_healthy()

    def _offer_closeout(self,value):
        # The frozen copier durably appends native-cohort.jsonl before calling us.
        # Admit at most one replay record until durable progress, instead of filling
        # the 16-slot action queue. No processor/state/journal format is changed.
        with self.replay_lock:
            try:
                self._replay_drain()
                while True:
                    self._replay_healthy()
                    try:
                        self.queue.put((value,None),timeout=.1)
                        self.accepted+=1
                        break
                    except queue.Full:
                        # A concurrent native burst may take the available slots.
                        # Replay waits; it must never latch JOURNAL_QUEUE_FULL.
                        self.replay_waits+=1
                        if self.replay_waits & (self.replay_waits-1)==0:self._replay_status('BACKPRESSURE')
                self._replay_drain()
                self.replay_committed+=1
                return True
            except RuntimeError:
                self.replay_failures+=1
                self._replay_status('FAILED')
                # The frozen copier logs this exception; the durable cohort row is
                # retained. Never acknowledge a closeout after a writer failure.
                raise

    def offer(self,value):
        if self.lane=='main' and value is not None and value.get('kind')=='BRTI_CLOSEOUT':
            return self._offer_closeout(value)
        a=getattr(LOCAL,'attempt',None)
        result=super().offer((value,a['attempt_id'] if a else None)) if value is not None else super().offer(None)
        admin=ADMINS.get(self.lane)
        if admin and a:admin.offered(result,value.get('kind'))
        return result


def install(admin=None):
    if admin:ADMINS[admin.lane]=admin
    frozen.Journal=RevisionJournal;frozen.Worker=RevisionWorker


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
    for key in ('published_ts','journal','administrative_journal'):
        if key in value:out[key]=value[key]
    return out


def public_view(root,lane,now=None,confirmation=None):
    now=time.time() if now is None else now
    try:
        raw=(Path(root)/(lane+'.json')).read_bytes()
        if len(raw)>frozen.MAX_BYTES:raise ValueError('OVERSIZE_VIEW')
        v=json.loads(raw)
        try:
            health=(Path(root)/(lane+'.admin-health.json')).read_bytes()
            if len(health)<=4096:v['administrative_journal']=json.loads(health)
        except (OSError,ValueError):pass
        if (v.get('schema')!=ENVELOPE or v.get('product_revision')!=REVISION or v.get('lane')!=lane
            or v.get('candidate')!=STRATEGY or v.get('signal_only') is not True or v.get('orders') is not False):
            raise ValueError('PRODUCT_IDENTITY')
        if v.get('status')=='UNAVAILABLE':return unavailable(lane,v.get('reason','SOURCE_UNAVAILABLE'),now,v)
        if lane=='main' and confirmation is not None:
            from .revalidation import apply
            if callable(confirmation):
                confirmation=confirmation(v)
                # Include bounded handoff wait/inference time in the lease check.
                now=time.time()
            renewed=apply(v,confirmation,now)
            if renewed is not None:return renewed
        if not v['published_ts']<=now<v['expires_at']:return unavailable(lane,'SOURCE_EXPIRED',now,v)
        v['served_ts']=now;return v
    except (OSError,ValueError,KeyError,TypeError):return unavailable(lane,'JOURNAL_UNAVAILABLE',now)
