"""Offline-only tests. Run after copying research module into this directory."""
import sqlite3, tempfile, unittest
from pathlib import Path
from btc15_v7_owner_transaction_research import commit_closeout_in_owner,CloseoutConflict

class JournalFixture:
    def __init__(self,db):self.db=db
    def get(self,key,default=None):
        row=self.db.execute('SELECT v FROM meta WHERE k=?',(key,)).fetchone()
        return row[0] if row else default

class OwnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=sqlite3.connect(str(Path(self.tmp.name)/'main.sqlite3'))
        self.db.executescript("""CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT NOT NULL);
          CREATE TABLE events(seq INTEGER PRIMARY KEY,at REAL,contract TEXT,kind TEXT,sha256 TEXT,body BLOB);
          INSERT INTO meta VALUES('sequence','0');""")
        self.j=JournalFixture(self.db)
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def record(self,contract='A',side='UP'):
        return dict(kind='BRTI_CLOSEOUT',contract=contract,published_ts=1000.0,
                    brti_closeout=dict(final60_side=side,final60_count=60,final60_complete=True),
                    product=dict(revision='RESEARCH'),signal_only=True,orders=False)
    def test_idempotent_and_conflict(self):
        first=commit_closeout_in_owner(self.j,self.record(),{})
        second=commit_closeout_in_owner(self.j,self.record(),{})
        self.assertEqual(first[0],second[0]);self.assertTrue(second[1])
        with self.assertRaises(CloseoutConflict):
            commit_closeout_in_owner(self.j,self.record(side='DOWN'),{})
        self.assertEqual(self.db.execute("SELECT count(*) FROM events").fetchone()[0],1)
    def test_restart_receipt(self):
        commit_closeout_in_owner(self.j,self.record(),{})
        self.db.close();self.db=sqlite3.connect(str(Path(self.tmp.name)/'main.sqlite3'))
        self.j=JournalFixture(self.db)
        self.assertTrue(commit_closeout_in_owner(self.j,self.record(),{})[1])
    def test_atomic_rollback(self):
        self.db.execute("""CREATE TABLE closeout_receipts_research_v7
            (contract TEXT PRIMARY KEY,payload_sha TEXT,sequence INTEGER UNIQUE,payload BLOB)""")
        self.db.execute("""CREATE TRIGGER fail_receipt BEFORE INSERT ON closeout_receipts_research_v7
            BEGIN SELECT RAISE(ABORT,'forced'); END;""")
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            commit_closeout_in_owner(self.j,self.record(),{})
        self.assertEqual(self.db.execute("SELECT count(*) FROM events").fetchone()[0],0)
    def test_native_sequence_interleave(self):
        commit_closeout_in_owner(self.j,self.record(),{})
        self.db.execute("INSERT INTO events VALUES(2,1001,'B','NATIVE_DECISION','x',X'01')")
        self.db.execute("UPDATE meta SET v='2' WHERE k='sequence'");self.db.commit()
        self.assertEqual(commit_closeout_in_owner(self.j,self.record('C'),{})[0],3)
    def test_no_orders(self):
        r=self.record();r['orders']=True
        with self.assertRaises(ValueError):commit_closeout_in_owner(self.j,r,{})
if __name__=='__main__':unittest.main()
