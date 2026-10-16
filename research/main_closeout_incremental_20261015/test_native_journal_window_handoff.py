"""Offline original native journal continuity / literal-label handoff tests.

These are cross-window identity prerequisites in EXISTING reader, not a new
EARLY strategy model, replay of absent prices, or settlement verification.
"""
import json
import tempfile
import unittest
from pathlib import Path

from btc15_ladder_journal_v1 import digest
from candidates.early_recording_20261012.archive import Archive,BUDGET
from ops.recording_workflow.policy import local_policy
from ops.recording_workflow.evidence import streaming_window_inventory
from ops.live_recording.native_window_handoff_research import NativeJournalWindowHandoff
from ops.live_recording.policy import sha

TICKER='KXBTC15M-26OCT161130-30'
T0=1792012600.
JOURNAL='MAIN-ORIGINAL-JOURNAL'


def opened(root):
    a=Archive(root/'source',evidence_class='FIXTURE',
              source_binding='original-native-commit-only',
              budget=dict(BUDGET,segment_bytes=4096,max_total_bytes=16*1024**2),
              storage_policy=local_policy())
    a.start()
    return a


def evidence(frame=11,now=T0):
    return dict(contract=TICKER,native_epoch='native-epoch',
                native_sequence=frame,captured_ts=now,
                official_open=T0-600,official_close=T0+300,
                target=64200.0)


def main_native(frame=11,*,with_origin=True,management='HOLD'):
    f=evidence(frame,T0+(frame-11)*.03)
    n=dict(kind='NATIVE_DECISION',candidate='MAIN',
           event='BUY' if with_origin else 'WATCH',
           evidence=f,published_ts=f['captured_ts']+.001,
           management=dict(state=management))
    if with_origin:
        oid=digest(['MAIN',TICKER,['native-epoch',frame],'UP'])
        n['origin']=dict(origin_id=oid,contract=TICKER,
                         native_epoch='native-epoch',native_sequence=frame,
                         side='UP',entry_provenance=f)
        n['origin_id']=oid
        n['final']=dict(early_origin_id=oid,
                        publication_id=digest(['MAIN','FINAL',['native-epoch',frame]]),
                        state='WATCH')
    else:
        n['final']=dict(publication_id=digest(['MAIN','FINAL',
                           ['native-epoch',frame]]),state='WATCH')
    return n


def put(a,n,seq,*,lane='main',override_sha=None):
    raw=json.dumps(n,separators=(',',':')).encode()
    a.write('NATIVE_RECORD',dict(raw=raw.decode(),sha256=override_sha or sha(raw),
             original_journal=JOURNAL,sequence=seq,lane=lane,
             committed_at=n.get('published_ts',T0)+.01,
             record_basis='POST_ORIGINAL_COMMIT'))
    return sha(raw)


class NativeBoundedHandoffTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp=Path(temp.name)
        self.source=self.tmp/'src'
        self.source.mkdir()
    def inventory(self,*,max_records=1):
        return streaming_window_inventory(self.source,self.tmp/'out',
                                          max_window_records=max_records,
                                          max_window_bytes=5*1024**2,
                                          native_handoff=NativeJournalWindowHandoff())

    def test_original_buy_state_and_journal_commit_persist_across_windows(self):
        a=opened(self.source)
        n=main_native()
        digest1=put(a,n,801)
        n2=main_native(frame=12,with_origin=False,management='EXIT')
        digest2=put(a,n2,802)
        a.write('STOP',dict(clean=True))
        a.close()
        summary=self.inventory()
        hand=summary['native_journal_handoff']
        self.assertEqual(hand['original_commit_counts']['original_journal_envelopes'],2)
        self.assertEqual(hand['journal_count'],1)
        self.assertEqual(hand['contract_count'],1)
        self.assertEqual(hand['origin_count'],1)
        self.assertEqual(hand['exact_emitted_labels']['BUY'],1)
        self.assertEqual(hand['exact_emitted_labels']['EXIT'],1)
        self.assertEqual(hand['original_evidence_gap_envelopes'],0)
        self.assertFalse(hand['full_early_validation_complete'])
        self.assertFalse(hand['source_and_quote_associations_complete'])
        self.assertFalse(hand['outcome_receipts_verified'])
        rows=[json.loads(s) for s in (self.tmp/'out/windows.jsonl').read_text().splitlines()]
        self.assertTrue(any(any(j['last_original_sequence']==801 for j in
              w['native_journal_handoff']['journal_ranges']) for w in rows))
        self.assertTrue(any(any(j['last_original_sequence']==802 for j in
              w['native_journal_handoff']['journal_ranges']) for w in rows))
        self.assertTrue(any(any(c['last_original_raw_sha256']==digest1 for c in
              w['native_journal_handoff']['contract_states']) for w in rows))
        self.assertTrue(any(any(c['last_original_raw_sha256']==digest2 for c in
              w['native_journal_handoff']['contract_states']) for w in rows))
        self.assertFalse((self.tmp/'out/index.sqlite3').exists())

    def test_original_journal_commit_gap_fails_closed(self):
        a=opened(self.source)
        put(a,main_native(),100)
        put(a,main_native(frame=12,with_origin=False),102)
        a.write('STOP',dict(clean=True));a.close()
        with self.assertRaisesRegex(ValueError,'NATIVE_WINDOW_GAP_OR_DUPLICATE_ORIGINAL_COMMIT'):
            self.inventory()
        self.assertFalse((self.tmp/'out/window_inventory_manifest.json').exists())

    def test_native_inner_raw_sha_mismatch_fails_closed(self):
        a=opened(self.source)
        put(a,main_native(),7,override_sha='0'*64)
        a.write('STOP',dict(clean=True));a.close()
        with self.assertRaisesRegex(ValueError,'NATIVE_WINDOW_RAW_HASH'):
            self.inventory()

    def test_origin_hash_mismatch_fails_closed(self):
        a=opened(self.source)
        bad=main_native();bad['origin']['origin_id']='0'*64
        put(a,bad,99)
        a.write('STOP',dict(clean=True));a.close()
        with self.assertRaisesRegex(ValueError,'NATIVE_WINDOW_MAIN_ORIGIN_IDENTITY'):
            self.inventory()

    def test_original_gap_disqualifies_following_native_labels(self):
        a=opened(self.source)
        put(a,main_native(),500)
        a.write('EVIDENCE_GAP',dict(reasons=dict(QUEUE_BYTES=4)))
        put(a,main_native(frame=12,with_origin=False,management='EXIT'),501)
        a.write('STOP',dict(clean=True));a.close()
        summary=self.inventory(max_records=2)
        hand=summary['native_journal_handoff']
        self.assertTrue(hand['quarantined_on_loss'])
        self.assertEqual(hand['original_evidence_gap_envelopes'],1)
        self.assertEqual(hand['original_commit_counts']['original_journal_envelopes'],1)
        self.assertEqual(hand['original_commit_counts']['unqualified_native_after_gap'],1)
        self.assertNotIn('EXIT',hand['exact_emitted_labels'])
        self.assertFalse(summary['loss_free'])

    def test_v81_origin_hash_checks_keep_exact_quote_identity(self):
        a=opened(self.source)
        prov=dict(quote=dict(epoch='v81epoch',sequence=9,
                             up_ask=.32,down_ask=.68),
                  ticker=TICKER,open_ts=T0-600,close_ts=T0+300,
                  target=64200,brti=dict(value=64210))
        side='UP';ts=T0
        oid=digest(['V81',TICKER,side,ts,prov['quote']['epoch'],
                    prov['quote']['sequence']])
        native=dict(kind='SCALP_OBSERVATION',candidate='V81',
                    contract=TICKER,provenance=prov,
                    published_ts=T0+.05,
                    event='BUY',guidance='BUY',
                    origin=dict(origin_id=oid,contract=TICKER,side=side,
                                signal_ts=ts,entry_provenance=prov,
                                original_ask=prov['quote']['up_ask']))
        put(a,native,25,lane='v81')
        a.write('STOP',dict(clean=True));a.close()
        result=self.inventory()['native_journal_handoff']
        self.assertEqual(result['origin_count'],1)
        self.assertEqual(result['original_commit_counts']['native_kind:SCALP_OBSERVATION'],1)
        self.assertFalse(result['source_and_quote_associations_complete'])

if __name__=='__main__':
    unittest.main()
