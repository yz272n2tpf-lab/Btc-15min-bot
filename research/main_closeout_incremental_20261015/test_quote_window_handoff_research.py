"""Research-only regression for original Kalshi quote-book across bounded slices.

The existing Book parser is reused; every raw original wire byte, acceptance
timestamp and origin stream reference is explicit. No quote fabrication,
trading order, source polling, or EARLY profitability claim.
"""
import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from candidates.early_recording_20261012.archive import Archive,BUDGET
from btc15_kalshi_quote_provenance_v1 import Book
from ops.recording_workflow.policy import local_policy
from ops.recording_workflow.evidence import streaming_window_inventory
from ops.live_recording.quote_window_handoff_research import QuoteWindowHandoff
from ops.live_recording.policy import canonical,sha


TICKER='KXBTC15M-26OCT161130-30'
EPOCH='fixture-original-epoch'
MARKET='exact-original-market-A'
T0=1792012600.


def setup(root, *, segment_bytes=2048):
    params=dict(BUDGET,segment_bytes=segment_bytes,max_total_bytes=16*1024**2)
    a=Archive(root/'source',evidence_class='FIXTURE',
              source_binding='fixture-original-sequence',
              budget=params,storage_policy=local_policy())
    a.start()
    a.write('STREAM_START',dict(ticker=TICKER,epoch=EPOCH,observed_at=T0))
    return a


def event(a,body,seq,*,accept=True):
    blob=json.dumps(body,separators=(',',':')).encode()
    digest=hashlib.sha256(blob).hexdigest()
    a.write('QUOTE_BYTES',dict(raw_base64=base64.b64encode(blob).decode(),sha256=digest))
    at=T0+seq*.01
    a.write('QUOTE_RECEIVE',dict(raw_sha256=digest,received_at=at,
                                 ticker=TICKER,epoch=EPOCH))
    if accept:
        a.write('QUOTE_ACCEPT',dict(raw_sha256=digest,received_at=at,accepted_at=at+.001,
                                    ticker=TICKER,epoch=EPOCH))
    return digest,at


def snapshot(sequence=1):
    return dict(type='orderbook_snapshot',sid=7,seq=sequence,
                msg=dict(market_ticker=TICKER,market_id=MARKET,
                         yes_dollars_fp=[['0.35','12']],
                         no_dollars_fp=[['0.46','18']]))


def delta(sequence=2):
    return dict(type='orderbook_delta',sid=7,seq=sequence,
                msg=dict(market_ticker=TICKER,market_id=MARKET,
                         ts_ms=int((T0+sequence*.01)*1000),
                         side='yes',price_dollars='0.35',delta_fp='1'))


class QuoteWindowIntegrationTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name)
        self.root=self.base/'native'
        self.root.mkdir()

    def run_original_reader(self, *, limit=2, quote=None):
        return streaming_window_inventory(
            self.root,self.base/'bounded',
            window_seconds=900,max_window_bytes=5*1024**2,
            max_window_records=limit,
            quote_handoff=quote or QuoteWindowHandoff())

    def test_exact_exchange_book_handoffs_across_receipt_accept_boundary(self):
        a=setup(self.root)
        s=snapshot();d=delta()
        event(a,s,1);event(a,d,2)
        a.write('STREAM_END',dict(epoch=EPOCH,ticker=TICKER,
                                  reason='OWNER_DISCONNECT',observed_at=T0+.2))
        a.write('STOP',dict(clean=True))
        a.close()
        result=self.run_original_reader(limit=2)
        status=result['quote_state_handoff']
        self.assertEqual(status['original_message_counts']['quote_receives'],2)
        self.assertEqual(status['original_message_counts']['quote_accepts'],2)
        self.assertEqual(status['original_message_counts']['verified_deltas'],1)
        self.assertEqual(status['original_message_counts']['verified_snapshots'],1)
        self.assertEqual(status['original_evidence_gap_envelopes'],0)
        self.assertEqual(status['open_streams_at_recording_stop'],0)
        self.assertFalse(status['whole_campaign_qualified'])
        self.assertFalse(status['native_early_qualified'])
        windows=[json.loads(x) for x in
                 (self.base/'bounded/windows.jsonl').read_text().splitlines()]
        self.assertGreater(len(windows),3)
        self.assertTrue(any(x['quote_state_handoff']['queued_exact_receives']>0 for x in windows))
        self.assertTrue(any(x['quote_state_handoff']['open_books'] for x in windows))
        reference=Book(TICKER)
        reference.apply(s);reference.apply(d)
        want=sha(canonical(QuoteWindowHandoff._state(reference)))
        self.assertTrue(any(
            book['book_state_sha256']==want for x in windows
            for book in x['quote_state_handoff']['open_books']
        ))
        self.assertFalse((self.base/'bounded/index.sqlite3').exists())

    def test_missing_exact_original_receive_fails_closed(self):
        a=setup(self.root)
        blob=json.dumps(snapshot(),separators=(',',':')).encode()
        a.write('QUOTE_BYTES',dict(raw_base64=base64.b64encode(blob).decode(),sha256=sha(blob)))
        a.write('QUOTE_ACCEPT',dict(raw_sha256=sha(blob),received_at=T0,accepted_at=T0+.01,
                                    ticker=TICKER,epoch=EPOCH))
        a.write('STOP',dict(clean=True))
        a.close()
        with self.assertRaisesRegex(ValueError,'QUOTE_HANDOFF_ACCEPT_WITHOUT_EXACT_RECEIPT'):
            self.run_original_reader()
        self.assertFalse((self.base/'bounded/window_inventory_manifest.json').exists())

    def test_unproven_quote_sequence_is_rejected(self):
        a=setup(self.root)
        event(a,snapshot(),1)
        event(a,delta(sequence=3),3)
        a.write('STOP',dict(clean=True))
        a.close()
        with self.assertRaisesRegex(ValueError,'QUOTE_HANDOFF_CONTIGUOUS_BOOK_REPLAY'):
            self.run_original_reader()
        self.assertFalse((self.base/'bounded/window_inventory_manifest.json').exists())

    def test_original_capture_gap_quarantines_all_following_quote_state(self):
        a=setup(self.root)
        event(a,snapshot(),1)
        a.write('EVIDENCE_GAP',dict(reasons={'QUEUE_BYTES':17}))
        event(a,delta(),2)
        a.write('STOP',dict(clean=True))
        a.close()
        out=self.run_original_reader(limit=2)
        audit=out['quote_state_handoff']
        self.assertEqual(out['loss_indicators'].get('EVIDENCE_GAP'),1)
        self.assertEqual(audit['original_evidence_gap_envelopes'],1)
        self.assertEqual(audit['contiguous_book_events_before_first_gap'],1)
        self.assertGreater(audit['original_message_counts']['unreplayable_quote_envelopes_after_gap'],0)
        self.assertTrue(audit['quarantined_on_evidence_loss'])
        self.assertFalse(out['loss_free'])
        self.assertFalse(out['complete_market_evidence'])

    def test_raw_bytes_hash_integrity_is_enforced_independently(self):
        a=setup(self.root)
        raw=json.dumps(snapshot(),separators=(',',':')).encode()
        a.write('QUOTE_BYTES',dict(raw_base64=base64.b64encode(raw).decode(),
                                   sha256='0'*64))
        a.write('STOP',dict(clean=True))
        a.close()
        with self.assertRaisesRegex(ValueError,'QUOTE_HANDOFF_RAW_SHA'):
            self.run_original_reader()

    def test_duplicate_stream_is_error_not_synthesized(self):
        a=setup(self.root)
        a.write('STREAM_START',dict(ticker=TICKER,epoch=EPOCH,observed_at=T0))
        a.write('STOP',dict(clean=True))
        a.close()
        with self.assertRaisesRegex(ValueError,'QUOTE_HANDOFF_DUPLICATE_OR_TOO_MANY_STREAMS'):
            self.run_original_reader()

    def test_bounded_raw_cache_rejects_single_oversize_blob(self):
        a=setup(self.root,segment_bytes=8*1024**2)
        body=b'Z'*(1024**2+20)
        a.write('QUOTE_BYTES',dict(raw_base64=base64.b64encode(body).decode(),
                                   sha256=sha(body)))
        a.write('STOP',dict(clean=True))
        a.close()
        with self.assertRaisesRegex(ValueError,'QUOTE_HANDOFF_SINGLE_RAW_OVER_CAP'):
            self.run_original_reader(quote=QuoteWindowHandoff(max_raw_bytes=1024**2))


if __name__=='__main__':
    unittest.main()