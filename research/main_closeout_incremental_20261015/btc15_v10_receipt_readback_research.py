"""V10 research-only read-only durable receipt verification.

This does not write to the V2 journal or assume queue acceptance means commit.
The caller must wait for the existing V2 writer to finish before consulting it.
"""
import hashlib
import json
import sqlite3
import zlib
from pathlib import Path

class ReceiptUnavailable(RuntimeError):pass
class ReceiptConflict(RuntimeError):pass

def packed(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def verify_receipt(db_path,contract,settlement):
    if not contract or not isinstance(settlement,dict):
        raise ValueError('INVALID_RECEIPT_REQUEST')
    expected=packed(settlement)
    digest=hashlib.sha256(expected).hexdigest()
    path=Path(db_path)
    if not path.is_file():raise ReceiptUnavailable('JOURNAL_MISSING')
    try:
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.5) as db:
            db.execute('PRAGMA query_only=ON')
            receipt=db.execute('SELECT payload_digest,seq,payload FROM closeout_receipts_v9 WHERE contract=?',(contract,)).fetchone()
            if receipt is None:raise ReceiptUnavailable('NOT_DURABLY_COMMITTED')
            sha,seq,payload=receipt
            if sha!=digest or payload!=expected:raise ReceiptConflict('RECEIPT_PAYLOAD_CONFLICT')
            event=db.execute('SELECT contract,kind,sha256,body FROM events WHERE seq=?',(seq,)).fetchone()
            if event is None:raise ReceiptUnavailable('EVENT_MISSING_OR_RETAINED_OUT')
            c,kind,event_sha,body=event
            if c!=contract or kind!='BRTI_CLOSEOUT':raise ReceiptConflict('EVENT_IDENTITY_CONFLICT')
            raw=zlib.decompress(body)
            if hashlib.sha256(raw).hexdigest()!=event_sha:raise ReceiptConflict('EVENT_DIGEST_CONFLICT')
            decoded=json.loads(raw)
            if packed(decoded.get('brti_closeout'))!=expected:raise ReceiptConflict('EVENT_PAYLOAD_CONFLICT')
            if decoded.get('orders') is not False or decoded.get('signal_only') is not True:
                raise ReceiptConflict('SIGNAL_ONLY_CONFLICT')
            return dict(contract=contract,sequence=seq,payload_digest=digest,durable=True,orders=False)
    except sqlite3.Error as exc:
        raise ReceiptUnavailable('JOURNAL_UNREADABLE:'+type(exc).__name__) from exc
