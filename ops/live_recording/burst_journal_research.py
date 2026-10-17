"""Research candidate: off-path capture-only durable batching.

One gzip member may contain multiple complete *unchanged* JSONL envelopes.
Archive hashes, byte payloads, native caller semantics and trading evidence
are unmodified. Batches are fsync'd through the original CompressedJournal.
An uncommitted tail is never claimed sealed: START/STOP are always fsync'd.
Only install through the research-only RoleArchive candidate.
"""
from candidates.early_recording_20261012.archive import Archive
from btc15_quote_proof_offpath_v1 import OffPathProofWriter
from collections import Counter
import time

MiB=1024*1024

def observation_charge(fields):
    # Same conservative immutable-field charge as the original admission owner.
    return 512 + sum(len(v)*(4 if isinstance(v,str) else 1)
                     if isinstance(v,(str,bytes)) else 32 for v in fields.values())

class BatchedEvidenceJournal:
    """Bounded single-owner buffer; each committed gzip member is complete JSONL."""
    BATCH_BYTES=MiB
    BATCH_RECORDS=256

    def __init__(self,original):
        self.original=original
        self.pending=[]
        self.pending_bytes=0
        self.committed_batches=0
        self.committed_envelopes=0
        self.processed_observations=0;self.processed_charge=0
        self.durable_observations=0;self.durable_charge=0
        self.fsync_calls=0;self.fsync_total_ns=0;self.fsync_max_ns=0

    def __getattr__(self,name):
        return getattr(self.original,name)

    @property
    def records(self):
        return self.original.records + len(self.pending)
    @property
    def raw_bytes(self):
        return self.original.raw_bytes + self.pending_bytes
    @property
    def stored_bytes(self):
        # Conservative temporary budget charge. A batch is <=1 MiB.
        return self.original.stored_bytes + self.pending_bytes
    @property
    def total_bytes(self):
        return (self.original.total_bytes or 0) + self.pending_bytes

    def append(self,raw):
        if not isinstance(raw,bytes) or not raw.endswith(b'\n'):
            raise ValueError('COMPLETE_JOURNAL_LINE_REQUIRED')
        if (self.original.max_record_bytes is not None
                and len(raw)>self.original.max_record_bytes):
            raise ValueError('EVIDENCE_RECORD_BUDGET')
        if len(raw)>self.BATCH_BYTES:
            self.flush()
            self._append_durable(raw)
            self.committed_batches+=1
            self.committed_envelopes+=1
            return
        if self.pending_bytes + len(raw)>self.BATCH_BYTES:
            self.flush()
        self.pending.append(raw)
        self.pending_bytes+=len(raw)
        if len(self.pending)>=self.BATCH_RECORDS:
            self.flush()

    def flush(self):
        if not self.pending:
            return
        lines=self.pending
        raw=b''.join(lines)
        count=len(lines)
        # Every constituent JSONL record retains its original hash and
        # predecessor, and gzip.open().readline() reconstructs exact lines.
        # The underlying append performs its usual one-member atomic fsync.
        self._append_durable(raw)
        # Underlying member-based journal counts 1 for a gzip append; our
        # capture contract counts ORIGINAL JSONL envelopes instead.
        self.original.records += count-1
        self.committed_batches+=1
        self.committed_envelopes+=count
        self.pending=[]
        self.pending_bytes=0
        self._acknowledge()

    def _append_durable(self,raw):
        begun=time.perf_counter_ns()
        self.original.append(raw)
        elapsed=time.perf_counter_ns()-begun
        self.fsync_calls+=1;self.fsync_total_ns+=elapsed
        self.fsync_max_ns=max(self.fsync_max_ns,elapsed)

    def _acknowledge(self):
        self.durable_observations=self.processed_observations
        self.durable_charge=self.processed_charge

    def observation_processed(self,charge):
        # A processed event may have emitted multiple envelopes. It is durable
        # only after its last envelope was fsync'd; a partial batch is not credit.
        self.processed_observations+=1;self.processed_charge+=charge
        if not self.pending:self._acknowledge()

    def evidence_batch_status(self):
        return dict(committed_batches=self.committed_batches,
                    committed_envelopes=self.committed_envelopes,
                    buffered_records=len(self.pending),
                    buffered_raw_bytes=self.pending_bytes,
                    processed_observations=self.processed_observations,
                    processed_charge_bytes=self.processed_charge,
                    durable_observations=self.durable_observations,
                    durable_charge_bytes=self.durable_charge,
                    fsync_calls=self.fsync_calls,fsync_total_ns=self.fsync_total_ns,
                    fsync_max_ns=self.fsync_max_ns)


class BufferedCaptureArchive(Archive):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.journal=BatchedEvidenceJournal(self.journal)
    def write(self,kind,payload):
        # START must exist durably before ordinary capture. STOP cannot claim
        # completeness until every buffered observation is fsync'd.
        boundary=kind in ('START','STOP')
        if boundary:self.journal.flush()
        result=super().write(kind,payload)
        if boundary:self.journal.flush()
        return result


class BufferedProofWriter(OffPathProofWriter):
    def __init__(self,*args,**kwargs):
        self.admitted=Counter();self.admission_kinds={};self.oversize_shape={}
        archive=kwargs.get('archive')
        if archive is not None:
            observe=archive.observe
            def observed(kind,fields):
                result=observe(kind,fields)
                archive.journal.observation_processed(observation_charge(fields))
                return result
            archive.observe=observed
        super().__init__(*args,**kwargs)

    def _enqueue(self,capture,charge):
        ok=super()._enqueue(capture,charge)
        kind=getattr(capture,'kind','PROOF_JOB')
        if kind not in self.admission_kinds and len(self.admission_kinds)>=32:kind='OTHER'
        stats=self.admission_kinds.setdefault(kind,Counter())
        stats['attempted']+=1;stats['max_charge_bytes']=max(stats['max_charge_bytes'],charge)
        if ok:
            stats['admitted']+=1;stats['admitted_charge_bytes']+=charge
            self.admitted['observations']+=1;self.admitted['charge_bytes']+=charge
        else:stats['rejected']+=1
        return ok

    def _flush_gaps(self):
        super()._flush_gaps()
        # The original off-path thread calls this on idle and before each
        # dequeued event. Only flush on idle, shutdown or a full batch:
        # never wait for fsync on the native market/source thread.
        # Closing admission is not an idle queue. Flushing on every remaining
        # dequeue restores the original per-event fsync bottleneck precisely
        # when a saturated writer must drain. STOP flushes the final batch.
        if self.archive is not None and self.queue.empty():
            self.archive.journal.flush()

    def submit_observation(self,kind,**fields):
        ok=super().submit_observation(kind,**fields)
        if not ok and isinstance(kind,str):
            # Diagnose only the rare oversized non-actionable event.
            # No source bytes, private fields or payload content is retained.
            try:
                charge=observation_charge(fields)
                if charge>4*MiB:
                    if kind not in self.oversize_shape and len(self.oversize_shape)>=32:kind='OTHER'
                    stats=self.oversize_shape.setdefault(kind,dict(count=0,max_charge=0))
                    stats['count']+=1
                    stats['max_charge']=max(stats['max_charge'],charge)
                    raw=fields.get('raw')
                    stats['max_raw_length']=max(stats.get('max_raw_length',0),len(raw) if isinstance(raw,(str,bytes)) else 0)
                    stats['raw_type']=type(raw).__name__
                    stats['field_count']=len(fields)
            except Exception:
                pass
        return ok

    def status(self):
        z=super().status()
        z['oversize_by_kind']={k:dict(v) for k,v in list(self.oversize_shape.items())}
        z['admitted_observations']=self.admitted['observations']
        z['admitted_charge_bytes']=self.admitted['charge_bytes']
        z['admission_by_kind']={k:dict(v) for k,v in list(self.admission_kinds.items())}
        z['queue_items']=self.queue.qsize()
        z['unfinished_observations']=self.queue.unfinished_tasks
        if self.archive is not None:
            z['durable_batch']=self.archive.journal.evidence_batch_status()
            z['not_yet_durable_charge_bytes']=max(0,self.admitted['charge_bytes']-z['durable_batch']['durable_charge_bytes'])
            z['flow_snapshot_consistent']=(z['durable_batch']['durable_observations']<=z['admitted_observations']
                and z['durable_batch']['durable_charge_bytes']<=z['admitted_charge_bytes'])
        return z
