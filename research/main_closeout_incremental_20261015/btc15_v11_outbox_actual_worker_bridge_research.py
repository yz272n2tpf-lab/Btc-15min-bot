"""Research-only V11 V3 outbox -> actual V2 worker receipt bridge.

Only use on isolated fixtures. No production paths, network, orders or deployments.
The existing V3 outbox owns capture/cutover; this bridge handles ONLY pending items.
"""
import hashlib
import json
import sqlite3
from pathlib import Path
from .btc15_v10_receipt_readback_research import verify_receipt, ReceiptUnavailable
from .btc15_closeout_outbox_research_v3 import _research_guard, _read_meta, OUTBOX_SCHEMA, EvidenceChanged, _lock

def dispatch_pending(outbox_path, journal_path, offer, *, max_items=200, hook=None):
    outbox_path=Path(outbox_path)
    journal_path=Path(journal_path)
    _research_guard(outbox_path,journal_path)
    completed=[]
    with _lock(outbox_path.with_suffix('.owner.lock')):
        with sqlite3.connect(outbox_path,isolation_level=None,timeout=5) as db:
            meta=_read_meta(db)
            if meta.get('schema')!=OUTBOX_SCHEMA or meta.get('historical_cutover')!='EXPLICIT_NO_BACKFILL':
                raise EvidenceChanged('OUTBOX_CUTOVER_NOT_VERIFIED')
            items=db.execute("SELECT contract,payload,sha256 FROM items WHERE journal_seq IS NULL ORDER BY source_offset LIMIT ?",(max_items,)).fetchall()
            for contract,body,sha in items:
                if hashlib.sha256(body.encode()).hexdigest()!=sha:
                    raise EvidenceChanged('OUTBOX_PAYLOAD_CORRUPT')
                row=json.loads(body)
                if row.get('contract')!=contract or not isinstance(row.get('brti'),dict):
                    raise EvidenceChanged('OUTBOX_IDENTITY_CONFLICT')
                settlement=row['brti']
                # Verify first: after an interrupted acknowledgement, never
                # submit a duplicate if the journal already committed.
                try:
                    receipt=verify_receipt(journal_path,contract,settlement)
                except ReceiptUnavailable as exc:
                    if str(exc)!='NOT_DURABLY_COMMITTED':
                        raise
                    if not offer(dict(kind='BRTI_CLOSEOUT',contract=contract,settlement=settlement)):
                        raise EvidenceChanged('WORKER_DID_NOT_ACK_COMMIT')
                    receipt=verify_receipt(journal_path,contract,settlement)
                if hook:hook('AFTER_JOURNAL',contract)
                db.execute('BEGIN IMMEDIATE')
                try:
                    cur=db.execute("UPDATE items SET journal_seq=? WHERE contract=? AND sha256=? AND journal_seq IS NULL",(receipt['sequence'],contract,sha))
                    if cur.rowcount!=1:raise EvidenceChanged('OUTBOX_ACK_CONFLICT')
                    db.execute('COMMIT')
                except BaseException:
                    if db.in_transaction:db.execute('ROLLBACK')
                    raise
                completed.append(contract)
                if hook:hook('AFTER_ACK',contract)
    return completed
