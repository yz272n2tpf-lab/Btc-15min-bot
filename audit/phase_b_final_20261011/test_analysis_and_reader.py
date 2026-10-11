"""Focused tests of offline diagnostics; characterize unsafe admission, not endorse it."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zlib

HERE=Path(__file__).parent
def load(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
analysis=load('early_late_entry_analysis');reader=load('read_incident_journal')


class LateEntry(unittest.TestCase):
    def test_admission_repeats_across_both_sides_and_remaining_times(self):
        r=analysis.characterize();self.assertEqual(len(r['observations']),18)
        for x in r['observations']:
            self.assertEqual(x['event'],'BUY',x)
            self.assertTrue(x['signal_only']);self.assertFalse(x['orders'])

    def test_accumulated_average_is_currently_ignored(self):
        from test_btc15_supported_early import value_frame,step
        from btc15_v2_product.directional import Directional
        outputs=[]
        for average in (79980.,80020.):
            f=value_frame(ask=.05,p=.83,offset=870.9)
            f['brti'].update(final60_count=30,final60_avg=average,final60_side='DOWN' if average<80000 else 'UP',final60_complete=False)
            e=Directional();e.restore({});r,_,v=step(e,f)
            outputs.append((r['event'],v['origin']['qualification']))
        self.assertEqual(outputs[0],outputs[1])

    def test_raw_break_even_arithmetic_and_invalid_inputs(self):
        self.assertEqual(str(analysis.unknown_mean_threshold('83008.51',20,'82991.01')),'83017.26')
        self.assertEqual(str(analysis.unknown_mean_threshold('83008.51',52,'83002.06')),'83050.435')
        for args in [(1,60,1),(1,-1,1),(1,True,1),(1,1,'nan')]:
            with self.assertRaises(ValueError):analysis.unknown_mean_threshold(*args)


class ReadOnlyEvidence(unittest.TestCase):
    def make(self,root):
        path=Path(root)/'main.sqlite3'
        with sqlite3.connect(path) as db:
            db.executescript('CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT);CREATE TABLE events(seq INTEGER PRIMARY KEY,at REAL,contract TEXT,kind TEXT,sha256 TEXT,body BLOB);')
            db.execute("INSERT INTO meta VALUES ('lane','main')")
            raw=json.dumps({'event':'BUY','signal_only':True,'orders':False}).encode()
            for seq,at,c in [(1,reader.START-1,reader.CONTRACTS[0]),(2,reader.START,reader.CONTRACTS[0]),(3,reader.END,reader.CONTRACTS[0]),(4,reader.START+1,'FOREIGN'),(5,reader.START+2,None)]:
                db.execute('INSERT INTO events VALUES (?,?,?,?,?,?)',(seq,at,c,'NATIVE_DECISION',hashlib.sha256(raw).hexdigest(),zlib.compress(raw)))
        return path

    def test_bounded_query_hashes_and_no_database_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.make(tmp);before=p.read_bytes();r=reader.extract(p,'main')
            self.assertEqual([x['seq'] for x in r['rows']],[2,5]);self.assertEqual(p.read_bytes(),before)
            self.assertEqual(sorted(x.name for x in Path(tmp).iterdir()),['main.sqlite3'])

    def test_wrong_lane_missing_path_and_corrupt_body_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.make(tmp)
            with self.assertRaises(ValueError):reader.extract(p,'v81')
            with self.assertRaises(FileNotFoundError):reader.extract(Path(tmp)/'missing','main')
            with sqlite3.connect(p) as db:db.execute("UPDATE events SET sha256='wrong' WHERE seq=2")
            with self.assertRaisesRegex(ValueError,'INTEGRITY'):reader.extract(p,'main')

    def test_reader_sees_committed_wal_without_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.make(tmp)
            with sqlite3.connect(p) as writer:
                writer.execute('PRAGMA journal_mode=WAL')
                writer.execute('UPDATE events SET at=? WHERE seq=1',(reader.START+.5,));writer.commit()
                before={q.name:q.read_bytes() for q in Path(tmp).iterdir() if not q.name.endswith('-shm')}
                self.assertEqual(reader.extract(p,'main')['row_count'],3)
                self.assertEqual({q.name:q.read_bytes() for q in Path(tmp).iterdir() if not q.name.endswith('-shm')},before)


if __name__=='__main__':unittest.main()
