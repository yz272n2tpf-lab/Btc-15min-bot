"""Focused evidence latch tests; synthetic archives are not fresh-event proof."""
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from capture2.qualification import Latch, qualify, read_state, admitted_events
from capture2.wire import envelope
from capture2.test_writer_pipeline import CONFIG, IDENT
from sprint_evidence.passive_capture import SCHEMA

class QualificationTests(unittest.TestCase):
    def fixture(self, root, mode='main', count=20, spacing=100_000_000, gap=False):
        c = dict(CONFIG, mode=mode, quota_bytes=64*1024*1024)
        rows = []
        for i in range(count):
            seq = i+1+int(gap and i > 0)
            event = dict(schema=SCHEMA, identity=asdict(IDENT), sequence=seq, kind='LIFECYCLE_EMISSION',
                hook_read=dict(wall_ns=1_800_000_000_000_000_000+i*spacing,
                    before_boot_ns=1_000_000_000+i*spacing, after_boot_ns=1_000_000_001+i*spacing,
                    clock_qualified=False), prior_dropped=0, signal_only=True, orders=False,
                body=dict(emission=dict(schema='BTC15_QUOTE_RECEIVE_OBSERVATION_V1',ticker='CONTRACT')))
            rows.append(envelope(event, bytes.fromhex(c['key'])))
        path = root/'packets.jsonl.gz'
        path.write_bytes(gzip.compress(b'\n'.join(rows)+b'\n'))
        report = dict(producer_id=IDENT.producer_id, process_id=1, finished=True, complete=True,
            flushed=True, offered=count, accepted=count, delivered=count, producer_dropped=0,
            rejected=0, rejected_full=0, rejected_ended=0, last_transport_error=None,
            pending_packets=0, pending_bytes=0, retry_eagain=0, observed_boot_ns=9_000_000_000)
        (root/'transport.json').write_text(json.dumps(report))
        population = dict(census_version=1, process_id=1, active_records=[],
            retired_reports=[dict(producer_id=IDENT.producer_id,path='transport.json')],
            created=1, active=0, retired=1, retired_flushed=1, retired_incomplete=0,
            fault=None, admission_rejected=0)
        (root/'population-1.json').write_text(json.dumps(population))
        h = dict(status='BOUNDED_CAPTURE_ENDED', streams={IDENT.producer_id:count+int(gap)},
            gap_count=0, missing_packets=0, sequence_gaps=[], invalid=0, producer_drop_observed=False,
            final_fsync_completed=True, uncommitted_valid=0, packets=count, received_valid=count,
            bytes=path.stat().st_size, observed_boot_ns=9_000_000_000)
        (root/'final_health.json').write_text(json.dumps(h))
        return c

    def test_in_envelope_finishes_qualified_and_all_ladders_admit(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); c=self.fixture(root); before=(root/'packets.jsonl.gz').read_bytes()
            state=qualify(root,c)
            self.assertEqual(state['qualification_state'],'QUALIFIED')
            for ladder in ('EARLY','FINAL','SCALP'):
                self.assertEqual(len(list(admitted_events(root,c,ladder))),20)
            self.assertEqual(before,(root/'packets.jsonl.gz').read_bytes())

    def test_main_rate_latches_with_causal_witness(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); c=self.fixture(root,count=1101,spacing=1)
            state=qualify(root,c); reason=state['reasons'][0]
            self.assertEqual(state['qualification_state'],'UNQUALIFIED')
            self.assertEqual(reason['code'],'RATE_ENVELOPE_EXCEEDED')
            self.assertEqual((reason['window_ms'],reason['measured'],reason['limit']),(100,1101,1100))
            self.assertEqual(reason['stream_id'],IDENT.producer_id)
            self.assertEqual(reason['source'],IDENT.source_sha256)
            self.assertEqual(reason['boot_ns'],1_000_001_100)

    def test_v81_rate_latches_and_diagnostics_remain(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); c=self.fixture(root,'v81',351,1)
            before=hashlib.sha256((root/'packets.jsonl.gz').read_bytes()).hexdigest()
            state=qualify(root,c)
            self.assertIn('RATE_ENVELOPE_EXCEEDED',state['reason_codes'])
            self.assertEqual(len(gzip.decompress((root/'packets.jsonl.gz').read_bytes()).splitlines()),351)
            self.assertEqual(hashlib.sha256((root/'packets.jsonl.gz').read_bytes()).hexdigest(),before)

    def test_sticky_across_clean_finish_reload_and_requalification(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); c=self.fixture(root)
            latch=Latch(root,c)
            latch.fail('RATE_ENVELOPE_EXCEEDED',boot_ns=123,measured=1101,limit=1100,window_ms=100)
            first=json.loads(json.dumps(latch.state['reasons']))
            self.assertEqual(qualify(root,c)['qualification_state'],'UNQUALIFIED')
            self.assertEqual(qualify(root,c)['reasons'],first)
            self.assertEqual(read_state(root,c)['qualification_state'],'UNQUALIFIED')

    def test_integrity_failures_have_required_codes(self):
        for failure,code in [('gap','SEQUENCE_GAP'),('buffer','CAPTURE_BUFFER_FULL'),
            ('census','CENSUS_MISMATCH'),('flush','INCOMPLETE_FLUSH'),('capture','CAPTURE_FAILURE')]:
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as d:
                root=Path(d); c=self.fixture(root,gap=failure=='gap')
                if failure=='buffer':
                    path=root/'transport.json'; r=json.loads(path.read_text())
                    r.update(rejected_full=1,rejected=1,producer_dropped=1,
                             first_rejection=dict(boot_ns=42,sequence=21,reason='CAPTURE_BUFFER_FULL'))
                elif failure=='census':
                    path=root/'population-1.json'; r=json.loads(path.read_text()); r['created']=2
                elif failure in ('flush','capture'):
                    path=root/'final_health.json'; r=json.loads(path.read_text())
                    r['final_fsync_completed']=failure!='flush'
                    if failure=='capture':r['status']='UNAVAILABLE_STORAGE_OSError'
                else:path=None
                if path:path.write_text(json.dumps(r))
                state=qualify(root,c)
                self.assertEqual(state['qualification_state'],'UNQUALIFIED')
                self.assertIn(code,state['reason_codes'])

    def test_all_ladders_refuse_unqualified_pending_and_missing(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); c=self.fixture(root)
            for stage in ('missing','pending','unqualified'):
                if stage=='pending':Latch(root,c).save()
                if stage=='unqualified':Latch(root,c).fail('CAPTURE_FAILURE',detail='test')
                for ladder in ('EARLY','FINAL','SCALP'):
                    with self.subTest(stage=stage,ladder=ladder),self.assertRaisesRegex(ValueError,'EVIDENCE_NOT_QUALIFIED'):
                        list(admitted_events(root,c,ladder))

    def test_archive_and_latch_tampering_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); c=self.fixture(root); qualify(root,c)
            path=root/'packets.jsonl.gz'; path.write_bytes(path.read_bytes()+b'tamper')
            with self.assertRaisesRegex(ValueError,'QUALIFIED_ARCHIVE_CHANGED'):
                list(admitted_events(root,c,'EARLY'))
            self.assertEqual(qualify(root,c)['qualification_state'],'UNQUALIFIED')
            path=root/'qualification.json'; value=json.loads(path.read_text())
            value['state']['qualification_state']='QUALIFIED';path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'QUALIFICATION_BINDING_OR_AUTHENTICATION'):
                list(admitted_events(root,c,'FINAL'))

    def test_unfinished_capture_never_promotes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); c=self.fixture(root); (root/'final_health.json').unlink()
            self.assertEqual(qualify(root,c)['qualification_state'],'PENDING')

    def test_longer_windows_and_half_open_boundary(self):
        cases=[('main',2251,100000,250),('main',4001,249999,1000),
               ('main',10001,400000,5000),('v81',10001,909090,10000)]
        for mode,count,spacing,window in cases:
            with self.subTest(window=window),tempfile.TemporaryDirectory() as d:
                root=Path(d); c=self.fixture(root,mode,count,spacing)
                reason=next(r for r in qualify(root,c)['reasons'] if r['code']=='RATE_ENVELOPE_EXCEEDED')
                self.assertEqual(reason['window_ms'],window)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); c=self.fixture(root,'v81',351,1_000_000)
            self.assertEqual(qualify(root,c)['qualification_state'],'QUALIFIED')

if __name__=='__main__':unittest.main(verbosity=2)
