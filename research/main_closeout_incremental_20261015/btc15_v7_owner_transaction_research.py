"""Research-only transaction method for a *single* V2 journal writer.

Not installed into production. This intentionally does not open a second
connection or create a second writer. Integration requires calling this from
the owning journal thread and preserving the V2 product envelope.
"""
import hashlib
import json
import zlib

class CloseoutConflict(RuntimeError):
    pass

def _packed(v):
    return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def commit_closeout_in_owner(journal,record,state):
    """Commit one BRTI_CLOSEOUT and receipt in one owner-held SQLite transaction.

    Return (sequence, replayed, payload_digest). This is not the full V2
    RevisionJournal.commit override; caller must preserve admin hooks and
    ensure this executes only in the existing worker thread.
    """
    if record.get('kind')!='BRTI_CLOSEOUT' or not record.get('contract'):
        raise ValueError('NOT_A_CLOSEOUT')
    if record.get('signal_only') is not True or record.get('orders') is not False:
        raise ValueError('SIGNAL_ONLY_BOUNDARY')
    if not isinstance(record.get('product'),dict):
        raise ValueError('V2_PRODUCT_ENVELOPE_REQUIRED')
    payload=_packed(record['brti_closeout'])
    sha=hashlib.sha256(payload).hexdigest()
    db=journal.db
    # No second connection. DDL and event/receipt commit share the same txn.
    with db:
        db.execute("""CREATE TABLE IF NOT EXISTS closeout_receipts_research_v7
                   (contract TEXT PRIMARY KEY, payload_sha TEXT NOT NULL,
                    sequence INTEGER NOT NULL UNIQUE, payload BLOB NOT NULL)""")
        key=record['contract']
        prior=db.execute("SELECT payload_sha,sequence,payload FROM closeout_receipts_research_v7 WHERE contract=?",(key,)).fetchone()
        if prior:
            if prior[0]!=sha or prior[2]!=payload:
                raise CloseoutConflict('CONFLICTING_RECEIPT')
            return (prior[1],True,sha)
        # Before first receipt, reject ambiguous historical duplicates. Retention
        # gaps must be reconciled before using this method for a cutover.
        legacy=db.execute("SELECT seq,body FROM events WHERE kind='BRTI_CLOSEOUT' AND contract=? ORDER BY seq",(key,)).fetchall()
        if len(legacy)>1:
            raise CloseoutConflict('HISTORICAL_DUPLICATES')
        if legacy:
            old=json.loads(zlib.decompress(legacy[0][1]))
            if _packed(old.get('brti_closeout'))!=payload:
                raise CloseoutConflict('HISTORICAL_CONFLICT')
            seq=legacy[0][0]
        else:
            raw=_packed(record)
            seq=int(journal.get('sequence','0'))+1
            db.execute("INSERT INTO events VALUES(?,?,?,?,?,?)",
                       (seq,float(record['published_ts']),key,'BRTI_CLOSEOUT',
                        hashlib.sha256(raw).hexdigest(),zlib.compress(raw)))
            # Identical state/meta update to frozen Journal.commit, but receipt
            # insertion must happen before the enclosing transaction commits.
            for name,value in [('sequence',str(seq)),('state',_packed(state).decode()),
                               ('latest',raw.decode())]:
                db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)",(name,value))
        db.execute("INSERT INTO closeout_receipts_research_v7 VALUES (?,?,?,?)",
                   (key,sha,seq,payload))
    return (seq,bool(legacy),sha)
