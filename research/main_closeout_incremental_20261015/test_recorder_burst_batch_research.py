"""Targeted offline regression for EXISTING native recorder burst failure.

No live data, market connectivity, strategy/scoring code or orders. Covers
hash-chain exactness, fsync reduction, bounded drain and fail-closed gaps.
"""
import json
import tempfile
import unittest
from pathlib import Path

from candidates.early_recording_20261012.archive import BUDGET, Archive, read_archive
from ops.recording_workflow.policy import local_policy
from ops.live_recording.capture import RoleArchive
from ops.live_recording.burst_journal_research import BufferedProofWriter


def archive(path, buffered=True, max_total=None):
    cap=dict(BUDGET)
    cap['max_total_bytes']=max_total or 128*1024*1024
    p=local_policy()
    klass=RoleArchive if buffered else Archive
    return klass(path,evidence_class='FIXTURE',
                 source_binding='fixture:controlled',budget=cap,
                 storage_policy=p)


def writer_for(tmp, a):
    return BufferedProofWriter(tmp/'unused',lambda proof,w: w.identity,
                               2*1024*1024,queue_size=16384,
                               archive=a,queue_bytes=32*1024*1024,
                               admission_limits=dict(queue_size=16384,queue_bytes=32*1024*1024))


class RecorderBurstTests(unittest.TestCase):
    def test_original_jsonl_hash_chain_unchanged_by_batches(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            a=archive(root/'baseline',False)
            b=archive(root/'optimized',True)
            a.session=b.session='constant-session-for-equality'
            a.start();b.start()
            for i in range(1500):
                payload=dict(reason='COMPARED_ORIGINAL_RECORD',at=i,
                             text=('event-%05d'%i))
                a.write('SOURCE_GAP',payload)
                b.write('SOURCE_GAP',payload)
            a.write('STOP',dict(clean=True))
            b.write('STOP',dict(clean=True))
            a.close();b.close()
            ar=read_archive(root/'baseline')
            br=read_archive(root/'optimized')
            self.assertEqual(ar['gaps'],br['gaps'])
            self.assertEqual(ar['records'],br['records'])
            self.assertEqual(a.journal.records,b.journal.records)
            self.assertEqual(a.journal.raw_bytes,b.journal.raw_bytes)
            self.assertGreater(b.journal.committed_envelopes,1000)
            self.assertLess(b.journal.committed_batches,30)
            self.assertEqual(b.journal.evidence_batch_status()['buffered_records'],0)

    def test_v81_shaped_quote_burst_drains_and_is_sealed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);a=archive(root/'recorded')
            writer=writer_for(root,a)
            self.assertTrue(writer._thread.is_alive())
            for i in range(9000):
                raw=json.dumps({'type':'orderbook_delta','sid':1,'seq':i,
                      'msg':{'market_id':'fixture-market',
                             'yes':[[i%99,12]],'no':[]}},
                      separators=(',',':')).encode()
                fields=dict(ticker='KXBTC15M-FIXTURE',epoch='fixture-epoch',
                            received_at=1000+i/2000,raw=raw)
                self.assertTrue(writer.submit_observation('QUOTE_RECEIVE',**fields))
                self.assertTrue(writer.submit_observation('QUOTE_ACCEPT',**fields,accepted_at=1000+i/2000+.001))
            self.assertTrue(writer.close(timeout=35),'writer must drain')
            state=writer.status()
            self.assertFalse(state['archive_failed'])
            self.assertEqual(state['losses'],{})
            self.assertEqual(state['durable_batch']['buffered_records'],0)
            decoded=read_archive(root/'recorded',max_decoded_bytes=128*1024*1024)
            kinds=[r['kind'] for r in decoded['records']]
            self.assertEqual(kinds.count('QUOTE_RECEIVE'),9000)
            self.assertEqual(kinds.count('QUOTE_ACCEPT'),9000)
            self.assertEqual(kinds.count('QUOTE_BYTES'),9000)
            self.assertEqual(kinds.count('STOP'),1)
            self.assertEqual(decoded['gaps'],[])
            self.assertLess(state['durable_batch']['committed_batches'],1100)

    def test_oversized_event_identified_without_acceptance(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);a=archive(root/'recorded')
            writer=writer_for(root,a)
            self.assertFalse(writer.submit_observation(
                'ORIGINAL_RESPONSE',raw=b'X'*(4*1024*1024+1),
                endpoint='https://example.invalid',received_at=10.0))
            self.assertTrue(writer.close(timeout=15))
            status=writer.status()
            self.assertGreater(status['oversize_by_kind']['ORIGINAL_RESPONSE']['max_charge'],4*1024*1024)
            self.assertGreaterEqual(status['losses'].get('OVERSIZE',0),1)
            records=read_archive(root/'recorded')
            self.assertTrue(any(row['kind']=='EVIDENCE_GAP' for row in records['records']))
            self.assertEqual(sum(row['kind']=='ORIGINAL_RESPONSE' for row in records['records']),0)

    def test_missing_capacity_fails_closed_no_complete_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);a=archive(root/'recorded',max_total=512)
            writer=writer_for(root,a)
            for i in range(150):
                writer.submit_observation('SOURCE_GAP',reason='quota',observed_at=i)
            self.assertTrue(writer.close(timeout=15))
            status=writer.status()
            self.assertTrue(status['archive_failed'])
            raw=read_archive(root/'recorded')
            self.assertTrue(raw['gaps'])
            self.assertFalse(raw['records'] and raw['records'][-1]['kind']=='STOP')


if __name__=='__main__':
    unittest.main()
