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

MiB=1024*1024

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
            self.original.append(raw)
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
        self.original.append(raw)
        # Underlying member-based journal counts 1 for a gzip append; our
        # capture contract counts ORIGINAL JSONL envelopes instead.
        self.original.records += count-1
        self.committed_batches+=1
        self.committed_envelopes+=count
        self.pending=[]
        self.pending_bytes=0

    def evidence_batch_status(self):
        return dict(committed_batches=self.committed_batches,
                    committed_envelopes=self.committed_envelopes,
                    buffered_records=len(self.pending),
                    buffered_raw_bytes=self.pending_bytes)


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
                charge=512
                for k,value in fields.items():
                    charge+=(len(value)*(4 if isinstance(value,str) else 1)
                             if isinstance(value,(str,bytes)) else 32)
                if charge>4*MiB:
                    if not hasattr(self,'oversize_shape'):
                        self.oversize_shape={}
                    stats=self.oversize_shape.setdefault(kind,dict(count=0,max_charge=0))
                    stats['count']+=1
                    stats['max_charge']=max(stats['max_charge'],charge)
            except Exception:
                pass
        return ok

    def status(self):
        z=super().status()
        z['oversize_by_kind']=dict(getattr(self,'oversize_shape',{}))
        if self.archive is not None:
            z['durable_batch']=self.archive.journal.evidence_batch_status()
        return z
