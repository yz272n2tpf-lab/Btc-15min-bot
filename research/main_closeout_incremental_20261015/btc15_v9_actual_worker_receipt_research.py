"""V9 research-only atomic receipt journal using the ACTUAL V2 RevisionWorker.

This subclass is installed only in isolated tests; production is untouched.
The frozen V2 non-closeout path remains delegated to RevisionJournal.commit.
"""
import hashlib
import json
import time
import zlib
import btc15_ladder_journal_v1 as frozen
from btc15_v2_product.journal import RevisionJournal, ADMINS

class ReceiptConflict(RuntimeError):
    pass

class ReceiptJournal(RevisionJournal):
    def __init__(self,path,lane):
        # Research-only: initialize receipt schema in the owning journal thread,
        # before any queue item can be processed. Never use a second writer.
        super().__init__(path,lane)
        with self.db:
            self.db.execute("""CREATE TABLE IF NOT EXISTS closeout_receipts_v9
                (contract TEXT PRIMARY KEY, payload_digest TEXT NOT NULL,
                 seq INTEGER NOT NULL UNIQUE, payload BLOB NOT NULL)""")

    def commit(self, record, state):
        if record.get('kind') != 'BRTI_CLOSEOUT':
            return super().commit(record,state)
        if record.get('signal_only') is not True or record.get('orders') is not False:
            raise ReceiptConflict('SIGNAL_ONLY_BOUNDARY')
        if not isinstance(record.get('product'),dict):
            raise ReceiptConflict('MISSING_V2_PRODUCT')
        contract=record.get('contract')
        if not contract: raise ReceiptConflict('MISSING_CONTRACT')
        payload=frozen.packed(record['brti_closeout'])
        digest=hashlib.sha256(payload).hexdigest()
        record['product']['runtime_epoch']=self.boot
        raw=frozen.packed(record)
        with self.db:
            self.db.execute("""CREATE TABLE IF NOT EXISTS closeout_receipts_v9
                (contract TEXT PRIMARY KEY, payload_digest TEXT NOT NULL,
                 seq INTEGER NOT NULL UNIQUE, payload BLOB NOT NULL)""")
            prior=self.db.execute("SELECT payload_digest,seq,payload FROM closeout_receipts_v9 WHERE contract=?",(contract,)).fetchone()
            if prior:
                if prior[0]!=digest or prior[2]!=payload:
                    raise ReceiptConflict('CONFLICTING_CLOSEOUT')
                return prior[1]
            legacy=self.db.execute("SELECT seq,body FROM events WHERE kind='BRTI_CLOSEOUT' AND contract=? ORDER BY seq",(contract,)).fetchall()
            if len(legacy)>1:raise ReceiptConflict('HISTORICAL_DUPLICATES')
            if legacy:
                old=json.loads(zlib.decompress(legacy[0][1]))
                if frozen.packed(old.get('brti_closeout'))!=payload:
                    raise ReceiptConflict('HISTORICAL_CONFLICT')
                seq=legacy[0][0]
            else:
                seq=int(self.get('sequence','0'))+1
                at=float(record['published_ts'])
                self.db.execute("INSERT INTO events VALUES(?,?,?,?,?,?)",
                    (seq,at,contract,'BRTI_CLOSEOUT',hashlib.sha256(raw).hexdigest(),zlib.compress(raw)))
                for key,value in [('sequence',str(seq)),('state',frozen.packed(state).decode()),('latest',raw.decode())]:
                    self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)",(key,value))
                if seq%120==0:
                    self.db.execute("DELETE FROM events WHERE seq <= ? OR at < ?",
                        (seq-frozen.MAX_RECORDS,at-30*86400))
                    self.db.execute("DELETE FROM contracts WHERE opened < ?",(at-30*86400,))
                    first=self.db.execute("SELECT min(seq) FROM events").fetchone()[0]
                    self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)",('retained_from_sequence',str(first)))
            self.db.execute("INSERT INTO closeout_receipts_v9 VALUES(?,?,?,?)",(contract,digest,seq,payload))
        if not legacy:
            admin=ADMINS.get(self.get('lane'))
            if admin:admin.pipeline(record,seq,time.time())
        return seq