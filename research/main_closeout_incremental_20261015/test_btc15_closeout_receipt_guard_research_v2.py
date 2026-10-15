"""Offline V2 journal-receipt and crash-boundary tests; zero network/production writes."""
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock
import zlib

from btc15_closeout_receipt_guard_research_v2 import DurableReceiptInspector
from btc15_cohort_closeout_incremental_research_v1 import EvidenceChanged
from btc15_cohort_closeout_incremental_research_v2 import ReceiptGatedIncrementalCloseout
from test_btc15_cohort_closeout_incremental_research_v1 import FIELDS, parity_row, legacy_select

DEPLOY = "11111111-2222-4333-8444-555555555555"
BUILD = "a" * 40
REVISION = "BTC15_INTEGRATED_OFFLINE_20261006"


class TestJournalReceipt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.parity = self.root / "parity.csv"
        self.cohort = self.root / "deployment-native-cohort.jsonl"
        self.dbpath = self.root / "main.sqlite3"
        with self.parity.open("w", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()
        self._db_init()
        self.inspector = DurableReceiptInspector(self.dbpath, deployment=DEPLOY,
                                                 build=BUILD, revision=REVISION)
        self.calls = []

    def _db_init(self):
        with sqlite3.connect(self.dbpath) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT NOT NULL)")
            db.execute("CREATE TABLE events(seq INTEGER PRIMARY KEY,at REAL NOT NULL,contract TEXT,kind TEXT NOT NULL,sha256 TEXT NOT NULL,body BLOB NOT NULL)")
            db.execute("CREATE INDEX by_contract ON events(contract,seq)")
            for k, v in dict(deployment=DEPLOY,build=BUILD,product_revision=REVISION,lane="main").items():
                db.execute("INSERT INTO meta VALUES (?,?)", (k,v))

    def append(self, rows):
        with self.parity.open("a", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writerows(rows)

    def write_receipt(self, ticker, settlement, *, patch=None):
        event = dict(schema="BTC15_LADDER_JOURNAL_V1", kind="BRTI_CLOSEOUT",
                     contract=ticker, brti_closeout=settlement,
                     evidence=dict(kind="BRTI_CLOSEOUT", contract=ticker,settlement=settlement),
                     product=dict(revision=REVISION,lane="main",deployment=DEPLOY,build=BUILD),
                     signal_only=True,orders=False)
        if patch:patch(event)
        raw=json.dumps(event,sort_keys=True,separators=(",", ":")).encode()
        with sqlite3.connect(self.dbpath) as db:
            nextseq=db.execute("SELECT coalesce(max(seq),0)+1 FROM events").fetchone()[0]
            db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)",
                       (nextseq,123.0,ticker,"BRTI_CLOSEOUT",hashlib.sha256(raw).hexdigest(),zlib.compress(raw)))
        return nextseq

    def dispatch(self,ticker,value):
        self.calls.append((ticker,value))
        self.write_receipt(ticker,value)
        return True

    def reader(self, dispatch=None):
        return ReceiptGatedIncrementalCloseout(self.parity,self.cohort,
                                               self.dispatch if dispatch is None else dispatch,
                                               self.inspector)

    def test_matching_durable_journal_receipt_and_exact_legacy_cohort(self):
        rows=[parity_row("A"),parity_row("A"),parity_row("B",final60_count="59"),parity_row("C")]
        self.append(rows)
        expected, callbacks=legacy_select(rows)
        engine=self.reader()
        self.assertEqual(engine.poll_once(),["A","C"])
        self.assertEqual(self.cohort.read_text().splitlines(keepends=True),expected)
        self.assertEqual(self.calls,callbacks)
        self.assertEqual(engine.poll_once(),[])
        self.assertEqual(engine.poll_once(),[])
        self.assertEqual(self.reader().poll_once(),[])
        self.assertEqual(len(self.calls),2)
        self.assertEqual(engine.committed,{"A":1,"C":2})
        self.assertEqual(self.inspector.lookup("A",callbacks[0][1]),1)

    def test_crash_after_durable_commit_before_audit_commit_reconciles_no_dispatch(self):
        self.append([parity_row("A")])
        engine=self.reader()
        original=engine._write_audit
        def fail_after_journal(ticker,digest,phase,**kwargs):
            if phase=="COMMITTED":raise RuntimeError("CRASH_AFTER_COMMIT")
            return original(ticker,digest,phase,**kwargs)
        with mock.patch.object(engine,"_write_audit",side_effect=fail_after_journal):
            with self.assertRaisesRegex(RuntimeError,"CRASH_AFTER_COMMIT"):
                engine.poll_once()
        self.assertEqual(len(self.calls),1)
        # Fresh process finds exact cohort and journal match, writes COMMITTED
        # without invoking the settlement callback again.
        after=self.reader(dispatch=lambda *_:self.fail("DUPLICATE_SETTLEMENT"))
        self.assertEqual(after.poll_once(),[])
        self.assertEqual(after.poll_once(),[])
        self.assertEqual(after.committed,{"A":1})
        self.assertEqual(len(self.calls),1)

    def test_crash_after_cohort_before_journal_is_quarantined(self):
        self.append([parity_row("A")]);engine=self.reader(dispatch=lambda *_:False)
        with self.assertRaisesRegex(EvidenceChanged,"JOURNAL_DISPATCH_NOT_ACKNOWLEDGED"):
            engine.poll_once()
        self.assertEqual(self.inspector.lookup("A",dict(contract="A")),None)
        with self.assertRaisesRegex(EvidenceChanged,"AMBIGUOUS_SETTLEMENT_WINDOW"):
            self.reader().poll_once()
        self.assertEqual(len(self.calls),0)

    def test_callback_says_true_without_durable_journal_is_quarantined(self):
        self.append([parity_row("A")]);engine=self.reader(dispatch=lambda *_:True)
        with self.assertRaisesRegex(EvidenceChanged,"JOURNAL_DURABLE_RECEIPT_ABSENT"):
            engine.poll_once()
        with self.assertRaisesRegex(EvidenceChanged,"AMBIGUOUS_SETTLEMENT_WINDOW"):
            self.reader().poll_once()

    def test_crash_before_cohort_write_requires_manual_reconciliation(self):
        self.append([parity_row("A")]);engine=self.reader()
        with mock.patch.object(engine,"_append_cohort_checked",side_effect=OSError("ENOSPC")):
            with self.assertRaisesRegex(OSError,"ENOSPC"):engine.poll_once()
        with self.assertRaisesRegex(EvidenceChanged,"AMBIGUOUS_COHORT_WRITE"):
            self.reader().poll_once()
        self.assertEqual(self.calls,[])

    def test_identity_guard_fails_foreign_cohort(self):
        self.append([parity_row("A")]);engine=self.reader()
        with sqlite3.connect(self.dbpath) as db:
            db.execute("UPDATE meta SET v=? WHERE k='deployment'", ("other",))
        with self.assertRaisesRegex(EvidenceChanged,"IDENTITY_MISMATCH"):
            engine.poll_once()

    def test_conflicting_receipt_fails_closed(self):
        self.append([parity_row("A")]);engine=self.reader(dispatch=lambda t,v:(self.write_receipt(t,{**v,"final60_average":123.456}),True)[1])
        with self.assertRaisesRegex(EvidenceChanged,"PAYLOAD_MISMATCH"):
            engine.poll_once()

    def test_duplicate_receipt_never_counts_as_exactly_once(self):
        self.append([parity_row("A")]);engine=self.reader(dispatch=lambda t,v:(self.write_receipt(t,v),self.write_receipt(t,v),True)[2])
        with self.assertRaisesRegex(EvidenceChanged,"JOURNAL_DUPLICATE_CLOSEOUT"):
            engine.poll_once()

    def test_receipt_without_evidence_identity_is_rejected(self):
        self.append([parity_row("A")])
        def corrupt(t,v):
            self.write_receipt(t,v,patch=lambda event:event["evidence"].update(contract="WRONG"))
            return True
        with self.assertRaisesRegex(EvidenceChanged,"JOURNAL_EVIDENCE_MISMATCH"):
            self.reader(dispatch=corrupt).poll_once()

    def test_missing_journal_fails_closed(self):
        self.dbpath.unlink()
        with self.assertRaisesRegex(EvidenceChanged,"JOURNAL_MISSING"):
            self.inspector.lookup("A",dict())

    def test_transient_receipt_read_error_reconciles_without_redelivery(self):
        self.append([parity_row("A")]);engine=self.reader()
        with mock.patch.object(self.inspector,"lookup",side_effect=EvidenceChanged("JOURNAL_READ_UNAVAILABLE")):
            with self.assertRaisesRegex(EvidenceChanged,"JOURNAL_READ_UNAVAILABLE"):
                engine.poll_once()
        restored=self.reader(dispatch=lambda *_:self.fail("REDISPATCH_NOT_ALLOWED"))
        self.assertEqual(restored.poll_once(),[])
        self.assertEqual(restored.poll_once(),[])
        self.assertEqual(len(self.calls),1)

    def test_committed_audit_cannot_fake_deleted_journal_receipt(self):
        self.append([parity_row("A")]);engine=self.reader()
        self.assertEqual(engine.poll_once(),["A"])
        with sqlite3.connect(self.dbpath) as db:
            db.execute("DELETE FROM events WHERE kind='BRTI_CLOSEOUT'")
        with self.assertRaisesRegex(EvidenceChanged,"AUDIT_COMMIT_JOURNAL_MISMATCH"):
            self.reader().poll_once()

    def test_partial_concurrent_native_cohort_line_fails_before_append(self):
        self.append([parity_row("A")]);self.cohort.write_text('{"schema":"BTC15_COHORT_NATIVE_V1","final_status":"PASS"')
        with self.assertRaisesRegex(EvidenceChanged,"COHORT_PARTIAL_TRAILER"):
            self.reader().poll_once()
        self.assertEqual(self.calls,[])

    def test_native_partial_arriving_during_intent_is_caught_before_append(self):
        self.append([parity_row("A")]);engine=self.reader()
        original=engine._write_audit
        def inject(ticker,digest,phase,**kw):
            original(ticker,digest,phase,**kw)
            if phase=="INTENT":
                with self.cohort.open("a") as dest:
                    dest.write('{"schema":"BTC15_COHORT_NATIVE_V1","contract":"NATIVE"')
        with mock.patch.object(engine,"_write_audit",side_effect=inject):
            with self.assertRaisesRegex(EvidenceChanged,"COHORT_PARTIAL_BEFORE_APPEND"):
                engine.poll_once()
        self.assertEqual(self.calls,[])
        self.assertNotIn('"CLOSEOUT_ONLY"',self.cohort.read_text())

    def test_existing_identical_duplicate_closeout_is_quarantined(self):
        self.append([parity_row("A")]);self.reader().poll_once()
        with self.cohort.open("a") as dest:
            dest.write(self.cohort.read_text())
        with self.assertRaisesRegex(EvidenceChanged,"COHORT_DUPLICATE_CLOSEOUT"):
            self.reader().poll_once()

    def test_corrupted_sqlite_digest_is_quarantined(self):
        self.append([parity_row("A")])
        def corrupt(t,v):
            seq=self.write_receipt(t,v)
            with sqlite3.connect(self.dbpath) as db:
                db.execute("UPDATE events SET sha256=? WHERE seq=?",("0"*64,seq))
            return True
        with self.assertRaisesRegex(EvidenceChanged,"JOURNAL_EVENT_DIGEST_MISMATCH"):
            self.reader(dispatch=corrupt).poll_once()

    def test_uncoordinated_native_writer_interleave_is_a_production_blocker(self):
        # Exhibit the unresolved TOCTOU: check final newline, then a native
        # process starts a partial append before the closeout writer writes.
        # This test documents the hazard; it does not claim a protocol fix.
        native = b'{"schema":"BTC15_COHORT_NATIVE_V1","contract":"NATIVE"'
        closeout = b'{"schema":"BTC15_COHORT_NATIVE_V1","contract":"CLOSEOUT","final_status":"CLOSEOUT_ONLY"}\n'
        self.cohort.write_bytes(b'{"seed":true}\n')
        with self.cohort.open("a+b") as out:
            out.seek(-1,2)
            self.assertEqual(out.read(1),b"\n")
            with self.cohort.open("ab") as other:
                other.write(native)
                other.flush()
            out.write(closeout)
            out.flush()
        records=self.cohort.read_text().splitlines()
        with self.assertRaises(json.JSONDecodeError):
            json.loads(records[-1])

    def test_idle_polls_do_not_repeat_historical_reads_or_receipt_lookups(self):
        self.append([parity_row("A")]*250)
        engine=self.reader();self.assertEqual(engine.poll_once(),["A"])
        engine.poll_once()
        before=engine.stats()
        with mock.patch.object(self.inspector,"lookup",side_effect=AssertionError("IDLE_LOOKUP")):
            for _ in range(12):self.assertEqual(engine.poll_once(),[])
        after=engine.stats()
        self.assertEqual(before["parity_bytes_read"],after["parity_bytes_read"])
        self.assertEqual(before["cohort_bytes_read"],after["cohort_bytes_read"])
        self.assertEqual(before["audit_bytes_read"],after["audit_bytes_read"])

    def test_no_real_order_or_production_imports(self):
        import inspect
        import btc15_closeout_receipt_guard_research_v2 as guard
        import btc15_cohort_closeout_incremental_research_v2 as v2
        text=inspect.getsource(guard)+inspect.getsource(v2)
        for forbidden in ("create_order", "place_order", "requests.post", "btc15_v2_product.production", "btc15_v2_product.runtime"):
            self.assertNotIn(forbidden,text)


if __name__=="__main__":unittest.main()
