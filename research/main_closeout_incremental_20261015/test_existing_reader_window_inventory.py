"""Offline tests of the EXISTING reader's bounded streaming inventory.

No change to native signals, Kalshi/BRTI, or EARLY scoring. The manifest is
a structural, original-record continuity prerequisite, NOT a strategy PASS.
"""
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from candidates.early_recording_20261012.archive import Archive,BUDGET
from ops.recording_workflow.policy import local_policy
from ops.recording_workflow.evidence import (
    index_run,streaming_window_inventory,file_sha
)


def source(path, *, segment_bytes=1000, n=90, stop=True, gap_at=None):
    budget=dict(BUDGET,max_total_bytes=64*1024**2,segment_bytes=segment_bytes)
    a=Archive(path,evidence_class='FIXTURE',source_binding='original-sequence',
              budget=budget,storage_policy=local_policy())
    a.start()
    for i in range(n):
        if i==gap_at:
            a.write('EVIDENCE_GAP',dict(reasons=dict(QUEUE_BYTES=2)))
        else:
            a.write('SOURCE_GAP',dict(reason='SOURCE_START_OR_EPOCH_CHANGE',
                                      observed_at=1792012600+i*31,ordinal=i))
    if stop:a.write('STOP',dict(clean=True))
    a.close()
    return a


class BoundedExistingReaderInventory(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'native_capture'
        (self.root/'source.segments').mkdir(parents=True)

    def mk(self,**kw):
        return source(self.root/'source',**kw)

    def run_inventory(self,**kw):
        return streaming_window_inventory(self.root,Path(self.temp.name)/'windowed',**kw)

    def test_counts_hashes_and_file_ids_match_original_sqlite_index(self):
        self.mk(n=140,segment_bytes=750)
        out=self.run_inventory(max_window_records=7,max_window_bytes=5*1024**2)
        original=index_run(self.root,Path(self.temp.name)/'original_index')
        self.assertEqual(out['record_count'],sum(original['counts'].values()))
        self.assertEqual(out['per_kind'],original['counts'])
        self.assertEqual(out['windows_manifest_sha256'],file_sha(Path(self.temp.name)/'windowed/windows.jsonl'))
        self.assertEqual(out['structural_integrity'],'PASS')
        self.assertFalse(out['complete_market_evidence'])
        self.assertFalse(out['early_strategy_qualified'])
        self.assertFalse(out['actual_contract_alignment_verified'])
        self.assertTrue(out['loss_free'])
        self.assertGreater(out['windows'],10)
        windows=[json.loads(x) for x in (Path(self.temp.name)/'windowed/windows.jsonl').read_text().splitlines()]
        self.assertEqual(sum(x['records'] for x in windows),out['record_count'])
        self.assertLessEqual(max(x['records'] for x in windows),7)
        self.assertEqual(windows[-1]['last_record_sha256'],out['sessions'][-1]['last_record_sha256'])
        self.assertEqual(len(out['source_files']),len(original['files']))
        self.assertFalse((Path(self.temp.name)/'windowed/index.sqlite3').exists())

    def test_corrupt_sha_fails_closed_and_no_final_manifest(self):
        self.mk(n=8)
        changed=False
        for f in (self.root/'source.segments').glob('*.jsonl.gz'):
            with gzip.open(f,'rb') as g: lines=g.readlines()
            for i,raw in enumerate(lines):
                if b'SOURCE_START_OR_EPOCH_CHANGE' in raw:
                    lines[i]=raw.replace(b'SOURCE_START_OR_EPOCH_CHANGE',b'SOURCE_START_OR_EPOCH_MUTATION')
                    f.write_bytes(gzip.compress(b''.join(lines),mtime=0))
                    changed=True
                    break
            if changed:break
        self.assertTrue(changed,'corruption must modify an original envelope')
        with self.assertRaises(ValueError):
            self.run_inventory()
        self.assertFalse((Path(self.temp.name)/'windowed/window_inventory_manifest.json').exists())

    def test_missing_original_sequence_cannot_pass(self):
        self.mk(n=14,segment_bytes=4096)
        files=list((self.root/'source.segments').glob('*.jsonl.gz'))
        chosen=None
        for f in files:
            with gzip.open(f,'rb') as g: rows=g.readlines()
            if len(rows)>=3 and json.loads(rows[1])['sequence']>1:
                chosen=(f,rows);break
        self.assertIsNotNone(chosen)
        f,rows=chosen
        rows.pop(1)
        f.write_bytes(gzip.compress(b''.join(rows),mtime=0))
        with self.assertRaisesRegex(ValueError,'WINDOWED_MISSING_DUPLICATE_OR_OUT_OF_ORDER_RECORD'):
            self.run_inventory()

    def test_loss_preserved_and_never_marked_complete(self):
        self.mk(n=36,gap_at=12)
        out=self.run_inventory()
        self.assertEqual(out['loss_indicators'].get('EVIDENCE_GAP'),1)
        self.assertFalse(out['loss_free'])
        self.assertFalse(out['complete_market_evidence'])
        self.assertFalse(out['early_strategy_qualified'])

    def test_unsealed_session_is_an_explicit_error(self):
        self.mk(n=22,stop=False)
        with self.assertRaisesRegex(ValueError,'WINDOWED_SESSION_UNCLOSED'):
            self.run_inventory()
        self.assertFalse((Path(self.temp.name)/'windowed/window_inventory_manifest.json').exists())

    def test_window_budget_is_hard_limit_no_unbounded_allocations(self):
        self.mk(n=23)
        out=self.run_inventory(max_window_records=3,max_window_bytes=5*1024**2)
        rows=[json.loads(x) for x in (Path(self.temp.name)/'windowed/windows.jsonl').read_text().splitlines()]
        self.assertLessEqual(max(x['records'] for x in rows),3)
        self.assertEqual(sum(x['records'] for x in rows),out['record_count'])
        self.assertGreater(out['unclocked_records'],0)
        self.assertTrue(all(x['bucket_is_actual_contract'] is False for x in rows))

    def test_changed_source_digest_and_output_overwrite_blocked(self):
        self.mk(n=10)
        self.run_inventory()
        with self.assertRaisesRegex(ValueError,'WINDOWED_SOURCE_OR_OUTPUT'):
            self.run_inventory()


if __name__=='__main__':unittest.main()