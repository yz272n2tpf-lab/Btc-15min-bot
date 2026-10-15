"""Research V3 protocol tests: no Railway, no native-cohort writes, no orders."""
import csv
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest import mock

from btc15_closeout_outbox_research_v3 import ResearchJournalV3, ResearchOutboxV3
from btc15_cohort_closeout_incremental_research_v1 import EvidenceChanged
from test_btc15_cohort_closeout_incremental_research_v1 import FIELDS, parity_row, legacy_select

DEPLOY = "11111111-2222-4333-8444-555555555555"
BUILD = "a" * 40
REVISION = "BTC15_INTEGRATED_OFFLINE_20261006"


class V3Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.parity = self.root / "parity.csv"
        self.cohort = self.root / "native-owned.jsonl"
        self.db = self.root / "outbox.sqlite3"
        self.journal_path = self.root / "journal.sqlite3"
        with self.parity.open("w", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()
        self.journal = ResearchJournalV3(self.journal_path, deployment=DEPLOY,
                                         build=BUILD, revision=REVISION)
        self.journal.init_fixture()
        self.obj = ResearchOutboxV3(self.parity, self.db, self.journal)
        self.obj.explicit_cutover()

    def append(self, rows):
        with self.parity.open("a", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writerows(rows)

    def pending(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            return db.execute("SELECT contract,journal_seq FROM items ORDER BY source_offset").fetchall()

    def journal_events(self):
        with closing(sqlite3.connect(self.journal_path)) as db, db:
            return db.execute("SELECT contract,seq FROM events ORDER BY seq").fetchall()

    def fresh(self):
        return ResearchOutboxV3(self.parity, self.db, self.journal)

    def test_cutover_is_explicit_and_historical_prefix_excluded(self):
        self.append([parity_row("OLD")])
        new_db = self.root / "after.sqlite3"
        new_obj = ResearchOutboxV3(self.parity, new_db, self.journal)
        with self.assertRaisesRegex(EvidenceChanged, "EXPLICIT_CUTOVER"):
            new_obj.poll_once()
        new_obj.explicit_cutover()
        self.assertEqual(new_obj.poll_once(), [])
        self.append([parity_row("NEW")])
        self.assertEqual(new_obj.poll_once(), ["NEW"])
        self.assertEqual(self.journal_events(), [("NEW", 1)])

    def test_exact_legacy_projection_and_durable_v2_receipt(self):
        rows = [parity_row("A"), parity_row("A"), parity_row("B", final60_count="59"),
                parity_row("C", final60_side="DOWN", final60_average="109000")]
        self.append(rows)
        expected, callbacks = legacy_select(rows)
        self.assertEqual(self.obj.poll_once(), ["A", "C"])
        self.assertEqual(self.obj.read_only_cohort_projection(), expected)
        self.assertEqual([x[0] for x in callbacks], [x[0] for x in self.journal_events()])
        self.assertEqual([self.journal.inspector().lookup(t, v) for t, v in callbacks], [1, 2])
        self.assertFalse(self.cohort.exists(), "native JSONL must have no competing closeout writer")
        self.assertEqual(self.obj.poll_once(), [])
        self.assertEqual(self.fresh().poll_once(), [])
        self.assertEqual(self.obj.status()["pending"], 0)

    def test_duplicate_rows_do_not_repeat_journal(self):
        self.append([parity_row("A") for _ in range(7)])
        self.assertEqual(self.obj.poll_once(), ["A"])
        self.assertEqual(self.journal_events(), [("A", 1)])
        self.assertEqual(self.fresh().poll_once(), [])

    def test_out_of_order_late_completion(self):
        self.append([parity_row("A", final60_complete="False"), parity_row("B")])
        self.assertEqual(self.obj.poll_once(), ["B"])
        self.append([parity_row("A"), parity_row("C")])
        self.assertEqual(self.fresh().poll_once(), ["A", "C"])
        self.assertEqual(self.journal_events(), [("B", 1), ("A", 2), ("C", 3)])

    def test_conflicting_later_row_quarantines(self):
        self.append([parity_row("A")])
        self.assertEqual(self.obj.poll_once(), ["A"])
        self.append([parity_row("A", final60_average="110300.00")])
        with self.assertRaisesRegex(EvidenceChanged, "PARITY_CONFLICTING"):
            self.obj.poll_once()
        self.assertEqual(self.journal_events(), [("A", 1)])

    def test_partial_source_row_retained_until_newline(self):
        from io import StringIO
        buffer = StringIO(newline="")
        csv.DictWriter(buffer, fieldnames=FIELDS).writerow(parity_row("PARTIAL"))
        raw = buffer.getvalue().encode()
        with self.parity.open("ab") as f:
            f.write(raw[:-1])
        self.assertEqual(self.obj.poll_once(), [])
        with self.parity.open("ab") as f:
            f.write(raw[-1:])
        self.assertEqual(self.obj.poll_once(), ["PARTIAL"])

    def test_corrupt_row_arity_fails_without_dispatch(self):
        with self.parity.open("a") as f:
            f.write("bad,column,count\n")
        with self.assertRaisesRegex(EvidenceChanged, "PARITY_ROW_ARITY"):
            self.obj.poll_once()
        self.assertEqual(self.journal_events(), [])

    def test_prefix_mutation_rejected(self):
        self.append([parity_row("A")])
        with self.parity.open("r+b") as f:
            f.seek(0);f.write(b"X")
        with self.assertRaisesRegex(EvidenceChanged, "PARITY_PREFIX_MUTATED"):
            self.obj.poll_once()

    def test_inode_replacement_rejected(self):
        candidate = self.root / "replacement.csv"
        candidate.write_bytes(self.parity.read_bytes())
        candidate.replace(self.parity)
        self.append([parity_row("A")])
        with self.assertRaisesRegex(EvidenceChanged, "PARITY_ROTATED"):
            self.obj.poll_once()

    def test_source_truncation_rejected(self):
        self.append([parity_row("A")])
        self.assertEqual(self.obj.poll_once(), ["A"])
        self.parity.write_text("tiny\n")
        with self.assertRaisesRegex(EvidenceChanged, "PARITY_ROTATED_OR_TRUNCATED"):
            self.obj.poll_once()

    def test_outbox_identity_mismatch_rejected(self):
        self.append([parity_row("A")])
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("UPDATE meta SET v='WRONG' WHERE k='deployment'")
        with self.assertRaisesRegex(EvidenceChanged, "OUTBOX_IDENTITY_MISMATCH"):
            self.obj.poll_once()

    def test_journal_identity_mismatch_rejected(self):
        self.append([parity_row("A")])
        with closing(sqlite3.connect(self.journal_path)) as db, db:
            db.execute("UPDATE meta SET v='WRONG' WHERE k='build'")
        with self.assertRaisesRegex(EvidenceChanged, "JOURNAL_IDENTITY_MISMATCH"):
            self.obj.poll_once()
        self.assertEqual(self.journal_events(), [])

    def test_crash_before_journal_keeps_durable_pending_and_replays(self):
        self.append([parity_row("A")])
        def crash(stage, ticker):
            if stage == "BEFORE_JOURNAL":
                raise RuntimeError("CRASH_BEFORE_JOURNAL")
        with self.assertRaisesRegex(RuntimeError, "CRASH_BEFORE_JOURNAL"):
            self.obj.poll_once(hook=crash)
        self.assertEqual(self.pending(), [("A", None)])
        self.assertEqual(self.journal_events(), [])
        self.assertEqual(self.fresh().poll_once(), ["A"])
        self.assertEqual(self.journal_events(), [("A", 1)])

    def test_crash_after_journal_before_ack_retries_same_sequence(self):
        self.append([parity_row("A")])
        def crash(stage, ticker):
            if stage == "AFTER_JOURNAL":
                raise RuntimeError("CRASH_AFTER_JOURNAL")
        with self.assertRaisesRegex(RuntimeError, "CRASH_AFTER_JOURNAL"):
            self.obj.poll_once(hook=crash)
        self.assertEqual(self.journal_events(), [("A", 1)])
        self.assertEqual(self.pending(), [("A", None)])
        self.assertEqual(self.fresh().poll_once(), ["A"])
        self.assertEqual(self.journal_events(), [("A", 1)])
        self.assertEqual(self.pending(), [("A", 1)])

    def test_crash_after_ack_does_not_dispatch_twice(self):
        self.append([parity_row("A")])
        def crash(stage, ticker):
            if stage == "AFTER_ACK":
                raise RuntimeError("CRASH_AFTER_ACK")
        with self.assertRaisesRegex(RuntimeError, "CRASH_AFTER_ACK"):
            self.obj.poll_once(hook=crash)
        self.assertEqual(self.pending(), [("A", 1)])
        self.assertEqual(self.fresh().poll_once(), [])
        self.assertEqual(self.journal_events(), [("A", 1)])

    def test_crash_inside_journal_transaction_rolls_back_and_replays(self):
        self.append([parity_row("A")])
        orig = self.journal.commit_once
        def inject(t, settlement):
            def crash(stage):
                if stage == "BEFORE_JOURNAL_COMMIT":
                    raise RuntimeError("BEFORE_JOURNAL_COMMIT")
            return orig(t, settlement, hook=crash)
        with mock.patch.object(self.journal,"commit_once",side_effect=inject):
            with self.assertRaisesRegex(RuntimeError, "BEFORE_JOURNAL_COMMIT"):
                self.obj.poll_once()
        self.assertEqual(self.journal_events(), [])
        self.assertEqual(self.fresh().poll_once(), ["A"])
        self.assertEqual(self.journal_events(), [("A", 1)])

    def test_concurrent_journal_dispatch_commit_once(self):
        settlement = legacy_select([parity_row("A")])[1][0][1]
        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(lambda _: self.journal.commit_once("A", settlement), range(12)))
        self.assertEqual(set(results), {1})
        self.assertEqual(self.journal_events(), [("A", 1)])

    def test_journal_conflicting_payload_quarantined(self):
        original = legacy_select([parity_row("A")])[1][0][1]
        self.journal.commit_once("A", original)
        with self.assertRaisesRegex(EvidenceChanged, "JOURNAL_CONFLICTING_CLOSEOUT"):
            self.journal.commit_once("A", {**original,"final60_average":9999})
        self.assertEqual(self.journal_events(), [("A", 1)])

    def test_parallel_outbox_owner_fails_closed(self):
        with self.obj.lock_path.open("a+b") as f:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                with self.assertRaisesRegex(EvidenceChanged, "OUTBOX_OWNER_BUSY"):
                    self.obj.poll_once()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def test_rejected_production_runtime_environment(self):
        with mock.patch.dict(os.environ,{"RAILWAY_PROJECT_ID":"pretend-production"}):
            with self.assertRaisesRegex(EvidenceChanged,"RAILWAY_RUNTIME_FORBIDDEN"):
                ResearchOutboxV3(self.parity,self.db,self.journal)

    def test_no_native_cohort_write_even_if_present(self):
        initial = json.dumps(dict(schema="BTC15_COHORT_NATIVE_V1",contract="X",final_status="PASS")) + "\n"
        self.cohort.write_text(initial)
        self.append([parity_row("A"),parity_row("B")])
        self.assertEqual(self.obj.poll_once(), ["A", "B"])
        self.assertEqual(self.cohort.read_text(),initial)

    def test_ack_journal_corruption_is_rejected(self):
        self.append([parity_row("A")])
        self.obj.poll_once()
        settlement = legacy_select([parity_row("A")])[1][0][1]
        with closing(sqlite3.connect(self.journal_path)) as db, db:
            db.execute("UPDATE events SET sha256='bad' WHERE kind='BRTI_CLOSEOUT'")
        with self.assertRaisesRegex(EvidenceChanged,"JOURNAL_CORRUPT_DIGEST"):
            self.journal.commit_once("A",settlement)

    def test_disallow_automatic_historical_cutover_reattempt(self):
        with self.assertRaisesRegex(EvidenceChanged, "OUTBOX_ALREADY_EXISTS"):
            self.obj.explicit_cutover()

    def test_only_complete_new_rows_are_counted(self):
        self.append([parity_row("A"),parity_row("B",final60_count="55")])
        self.assertEqual(self.obj.poll_once(max_rows=1),["A"])
        self.assertEqual(self.obj.poll_once(max_rows=1),[])
        self.assertEqual(self.obj.status()["total"],1)
        self.assertEqual(self.obj.status()["parity_bytes_since_cutover"],sum(len(x) for x in self.parity.read_bytes().splitlines(keepends=True)[1:]))

    def test_replay_pending_before_processing_new_rows(self):
        self.append([parity_row("A")])
        def crash(stage,ticker):
            if stage=="BEFORE_JOURNAL":raise RuntimeError("stopped")
        with self.assertRaisesRegex(RuntimeError,"stopped"):
            self.obj.poll_once(hook=crash)
        self.append([parity_row("B")])
        self.assertEqual(self.fresh().poll_once(),["A","B"])
        self.assertEqual(self.journal_events(),[("A",1),("B",2)])

    def test_historical_qualified_contract_reappearing_after_cutover_is_never_reissued(self):
        self.append([parity_row("OLD"), parity_row("OLD")])
        second = ResearchOutboxV3(self.parity, self.root / "historical.sqlite3", self.journal)
        second.explicit_cutover()
        self.append([parity_row("OLD"), parity_row("NEW")])
        self.assertEqual(second.poll_once(), ["NEW"])
        self.assertEqual(self.journal_events(), [("NEW", 1)])
        with closing(sqlite3.connect(second.outbox_db)) as db:
            self.assertEqual(db.execute("SELECT v FROM meta WHERE k='historical_eligible_contracts'").fetchone()[0],"1")

    def test_historical_incomplete_later_becomes_eligible(self):
        self.append([parity_row("OLD", final60_count="55")])
        second=ResearchOutboxV3(self.parity,self.root/"partial-history.sqlite3",self.journal)
        second.explicit_cutover()
        self.append([parity_row("OLD", final60_count="60")])
        self.assertEqual(second.poll_once(), ["OLD"])

    def test_crash_inside_outbox_transaction_preserves_cursor_and_dedupe(self):
        self.append([parity_row("A")])
        start=self.parity.stat().st_size
        def fail(stage,ticker):
            if stage=="BEFORE_OUTBOX_COMMIT":raise RuntimeError("OUTBOX_WRITE_CRASH")
        with self.assertRaisesRegex(RuntimeError,"OUTBOX_WRITE_CRASH"):
            self.obj.poll_once(hook=fail)
        self.assertEqual(self.pending(), [])
        self.assertEqual(self.journal_events(), [])
        self.assertEqual(self.fresh().poll_once(),["A"])
        self.assertEqual(self.journal_events(), [("A",1)])

    def test_crash_after_outbox_commit_recovers_pending_record(self):
        self.append([parity_row("A")])
        def fail(stage,ticker):
            if stage=="AFTER_OUTBOX_COMMIT":raise RuntimeError("OUTBOX_COMMITTED_CRASH")
        with self.assertRaisesRegex(RuntimeError,"OUTBOX_COMMITTED_CRASH"):
            self.obj.poll_once(hook=fail)
        self.assertEqual(self.pending(), [("A",None)])
        self.assertEqual(self.journal_events(), [])
        self.assertEqual(self.fresh().poll_once(),["A"])
        self.assertEqual(self.journal_events(), [("A",1)])

    def test_pending_outbox_not_replayed_if_source_rotates(self):
        self.append([parity_row("A")])
        def fail(stage,ticker):
            if stage=="BEFORE_JOURNAL":raise RuntimeError("CRASHED")
        with self.assertRaisesRegex(RuntimeError,"CRASHED"):
            self.obj.poll_once(hook=fail)
        self.assertEqual(self.pending(), [("A", None)])
        replacement=self.root/"new-parity.csv"
        replacement.write_bytes(self.parity.read_bytes())
        replacement.replace(self.parity)
        with self.assertRaisesRegex(EvidenceChanged,"PARITY_ROTATED"):
            self.fresh().poll_once()
        self.assertEqual(self.journal_events(), [])

    def test_projection_requires_current_journal_receipt(self):
        self.append([parity_row("A")])
        self.assertEqual(self.obj.poll_once(),["A"])
        with closing(sqlite3.connect(self.journal_path)) as db, db:
            db.execute("DELETE FROM events WHERE contract='A' AND kind='BRTI_CLOSEOUT'")
        with self.assertRaisesRegex(EvidenceChanged,"PROJECTION_JOURNAL_MISMATCH"):
            self.obj.read_only_cohort_projection()

    def test_projection_rejects_tampered_outbox_ack(self):
        self.append([parity_row("A")])
        self.assertEqual(self.obj.poll_once(),["A"])
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("UPDATE items SET journal_seq=999 WHERE contract='A'")
        with self.assertRaisesRegex(EvidenceChanged,"PROJECTION_JOURNAL_MISMATCH"):
            self.obj.read_only_cohort_projection()

    def test_concurrent_native_owned_jsonl_append_does_not_collide(self):
        self.append([parity_row("A")])
        first=dict(schema="BTC15_COHORT_NATIVE_V1",contract="FIRST",final_status="PASS")
        second=dict(schema="BTC15_COHORT_NATIVE_V1",contract="SECOND",final_status="PASS")
        started=threading.Event();finished=threading.Event()
        def native_owner():
            with self.cohort.open("a") as f:
                f.write(json.dumps(first))
                f.flush()
                started.set()
                self.assertTrue(finished.wait(timeout=2))
                f.write("\n"+json.dumps(second)+"\n")
                f.flush()
        worker=threading.Thread(target=native_owner)
        worker.start()
        self.assertTrue(started.wait(timeout=2))
        self.assertEqual(self.obj.poll_once(),["A"])
        finished.set();worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual([json.loads(x)["contract"] for x in self.cohort.read_text().splitlines()],
                         ["FIRST","SECOND"])
        self.assertEqual(len(self.obj.read_only_cohort_projection()),1)

    def test_no_network_or_production_api_in_research_module(self):
        src=Path(__import__("btc15_closeout_outbox_research_v3").__file__).read_text()
        self.assertNotIn("requests.",src)
        self.assertNotIn("create_order(",src)
        self.assertNotIn("place_order(",src)
        self.assertNotIn("btc15_v2_product.directional.settlement(",src)
        self.assertNotIn("btc15_ladder_product_v1.settlement(",src)
        self.assertIn("production_ready=False",src)


if __name__=="__main__":unittest.main()
