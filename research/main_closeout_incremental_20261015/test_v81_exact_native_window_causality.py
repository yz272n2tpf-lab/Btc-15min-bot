"""Existing reader Stage5 V81 original INPUT -> SCALP causal-join offline regressions.

Uses the same Kalshi Book, QualifiedInputs.require_qualified and immutable
Archive records. No new strategy or trading orders, and tests never claim a
hypothetical entry price as an actual fill or fee-qualified return.
"""
import base64
from datetime import datetime,timezone
import json
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from btc15_kalshi_quote_provenance_v1 import Book
from candidates.early_recording_20261012.archive import Archive,BUDGET
from ops.recording_workflow.policy import local_policy
from ops.recording_workflow.evidence import streaming_window_inventory
from ops.live_recording.policy import canonical,sha
from ops.live_recording.quote_window_handoff_research import QuoteWindowHandoff
from ops.live_recording.source_contract_window_handoff_research import SourceContractWindowHandoff
from ops.live_recording.v81_window_associations_research import V81WindowAssociations

OPEN=datetime(2026,10,16,15,30,tzinfo=timezone.utc).timestamp()
CLOSE=OPEN+900
NOW=OPEN+300
TICKER='KXBTC15M-'+datetime.fromtimestamp(CLOSE,timezone.utc).astimezone(
    ZoneInfo('America/New_York')).strftime('%y%b%d%H%M-%M').upper()
TARGET=64102.0
EPOCH='original-kalshi-epoch'
MARKET='exact-original-market-id'
ATTEMPT='original-attempt-001'


def at_iso(x):
    return datetime.fromtimestamp(x,timezone.utc).isoformat().replace('+00:00','Z')


def make_archive(root):
    a=Archive(root/'source',evidence_class='FIXTURE',
              source_binding='original-v81-native-source-only',
              budget=dict(BUDGET,segment_bytes=4096,max_total_bytes=64*1024**2),
              storage_policy=local_policy())
    a.start()
    return a


def market(*,target=TARGET):
    return dict(ticker=TICKER,open_time=at_iso(OPEN),close_time=at_iso(CLOSE),
                floor_strike=target,
                event_ticker='fixture-original',strike_type='greater',
                rules_primary='above target',rules_secondary='')


def original_market(a,*,target=TARGET):
    raw=canonical(dict(market=market(target=target)))
    a.observe('HTTP_RESPONSE',dict(raw=raw,
              endpoint='/trade-api/v2/markets/'+TICKER,
              received_at=NOW-5,receipt_basis='ORIGINAL_HTTP_OWNER',
              source='EXISTING_KALSHI_HTTP'))


def quote_event(a,raw,received):
    a.observe('QUOTE_RECEIVE',dict(raw=raw,epoch=EPOCH,ticker=TICKER,
              received_at=received,monotonic_ns=112233,
              receipt_basis='WS_RECV_RETURN_APPLICATION_TIME'))
    a.observe('QUOTE_ACCEPT',dict(raw=raw,epoch=EPOCH,ticker=TICKER,
              received_at=received,accepted_at=received+.01,
              accept_basis='AFTER_EXISTING_EVIDENCE_ACCEPT'))


def quote_book(a,*,add_delta=True):
    a.write('STREAM_START',dict(ticker=TICKER,epoch=EPOCH,observed_at=NOW-2))
    snapshot=dict(type='orderbook_snapshot',sid=7,seq=1,
                  msg=dict(market_ticker=TICKER,market_id=MARKET,
                           yes_dollars_fp=[['0.35','20']],
                           no_dollars_fp=[['0.55','30']]))
    delta=dict(type='orderbook_delta',sid=7,seq=2,
               msg=dict(market_ticker=TICKER,market_id=MARKET,
                        ts_ms=int((NOW-1)*1000),side='yes',
                        price_dollars='0.35',delta_fp='1'))
    quote_event(a,json.dumps(snapshot,separators=(',',':')).encode(),NOW-1.4)
    if add_delta:
        quote_event(a,json.dumps(delta,separators=(',',':')).encode(),NOW-.8)
    book=Book(TICKER);book.apply(snapshot)
    if add_delta:book.apply(delta)
    quotes=[float(v) for v in book.quotes(int((NOW-.1)*1000),int(CLOSE*1000))] if add_delta else [.35,.45,.55,.65]
    frame=dict(ticker=TICKER,epoch=EPOCH,market_id=MARKET,
               sid=7,sequence=2,
               source_ts_ms=int((NOW-1)*1000),
               validated_at_ms=int((NOW-.1)*1000),
               transport='timestamped_contiguous_ws',
               **dict(zip(('up_bid','up_ask','down_bid','down_ask'),quotes)))
    return frame


def btc_http(a,*,rec=NOW-.5):
    body=canonical(dict(time=at_iso(NOW-2),price='64101.0'))
    a.write('ORIGINAL_RESPONSE',dict(raw_base64=base64.b64encode(body).decode(),
               sha256=sha(body),
               endpoint='https://api.exchange.coinbase.com/products/BTC-USD/ticker',
               received_at=rec,status_code=200,
               receipt_basis='HTTP_GET_RETURN_BEFORE_NATIVE_DECODE'))
    return sha(body),rec


def brti_read(a,*,ts=NOW-2,at=NOW-.4):
    b=dict(value=64100.0,source_ts_ms=int(ts*1000),
           owner_epoch='brti-primary-original',sequence=49,
           status='PRIMARY_OK',clean_for_qualification=True)
    raw=canonical(b)
    a.write('BRTI_READ',dict(raw=raw.decode(),sha256=sha(raw),
              received_at=at,receipt_basis='EXISTING_SHARED_CONSUMER_RETURN'))
    return b,sha(raw),at


def build_provenance(quote,b,*,target=TARGET):
    return dict(schema='V81_TIMESTAMPED_INPUTS_V1',
                ticker=TICKER,open_ts=OPEN,close_ts=CLOSE,target=target,
                quote=quote,brti=b,btc_source_utc=at_iso(NOW-2),
                signal_only=True,orders=False)


def v81_row(a,quote,b,btc,brti,*,attempt=ATTEMPT,change_prices=False,target=TARGET):
    p=build_provenance(quote,b,target=target)
    if change_prices:
        p['quote']=dict(p['quote'],up_bid=.36)
    row=dict(ts=NOW,ticker=TICKER,left=CLOSE-NOW,target=target,
             btc=64101.0,brti=b['value'],input_provenance=p,
             **{k:p['quote'][k] for k in ('up_bid','up_ask','down_bid','down_ask')})
    raw=canonical(row)
    a.write('V81_INPUT',dict(raw=raw.decode(),sha256=sha(raw),
         accepted_at=NOW+.01,receipt_basis='AFTER_EXISTING_REQUIRE_QUALIFIED',
         btc_response_sha256=btc[0],btc_received_at=btc[1],
         brti_observation_sha256=brti[1],brti_received_at=brti[2],
         attempt_id=attempt))
    return p


def scalp_native(a,p,*,attempt=ATTEMPT,published=NOW+.03):
    record=dict(kind='SCALP_OBSERVATION',candidate='V81',
                contract=TICKER,provenance=p,published_ts=published,
                signal_only=True,orders=False,
                guidance='PASS',
                product=dict(attempt_id=attempt,lane='v81'))
    raw=canonical(record)
    a.write('NATIVE_RECORD',dict(raw=raw.decode(),sha256=sha(raw),
            original_journal='ORIGINAL-V81-JOURNAL',sequence=131,
            record_basis='POST_ORIGINAL_COMMIT',lane='v81',
            committed_at=published+.01))


class ExistingV81CausalReaderTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp=Path(t.name)
        self.root=self.tmp/'native'
        self.root.mkdir()

    def setup_case(self,*,missing_btc=False,missing_brti=False,
                   bad_market=False,missing_delta=False,brti_age=2,
                   changed_quote=False,wrong_attempt=False):
        a=make_archive(self.root)
        original_market(a,target=TARGET+11 if bad_market else TARGET)
        q=quote_book(a,add_delta=not missing_delta)
        btc=(sha(canonical(dict(time=at_iso(NOW-2),price='64101.0'))),NOW-.5)
        if not missing_btc:btc=btc_http(a)
        brti=(dict(value=64100.0,source_ts_ms=int((NOW-brti_age)*1000),
                   owner_epoch='brti-primary-original',sequence=49,
                   status='PRIMARY_OK',clean_for_qualification=True),None,NOW-.4)
        brti=(brti[0],sha(canonical(brti[0])),brti[2])
        if not missing_brti:brti=brti_read(a,ts=NOW-brti_age)
        p=v81_row(a,q,brti[0],btc,brti,change_prices=changed_quote)
        scalp_native(a,p,attempt='different-attempt' if wrong_attempt else ATTEMPT)
        a.write('STOP',dict(clean=True))
        a.close()

    def verify(self,**caps):
        quote=QuoteWindowHandoff()
        src=SourceContractWindowHandoff()
        v81=V81WindowAssociations(quote,src,**caps)
        result=streaming_window_inventory(
            self.root,self.tmp/'out',max_window_records=2,max_window_bytes=5*1024**2,
            quote_handoff=quote,source_handoff=src,v81_handoff=v81)
        return result

    def test_full_v81_input_and_native_causal_receipts_across_original_windows(self):
        self.setup_case()
        out=self.verify()
        result=out['v81_causal_handoff']
        self.assertEqual(result['original_evidence_counts']['ORIGINAL_INPUT_ACCEPTED_FULLY_CAUSAL'],1)
        self.assertEqual(result['original_evidence_counts']['ORIGINAL_SCALP_FULL_CAUSAL_INPUT_AND_QUOTE'],1)
        self.assertEqual(len(result['verified_native_receipts']),1)
        self.assertEqual(result['original_source_or_capture_gaps'],0)
        self.assertFalse(result['full_campaign_verified'])
        self.assertFalse(result['original_lifecycle_and_settlement_verified'])
        self.assertFalse((self.tmp/'out/index.sqlite3').exists())
        windows=[json.loads(line) for line in (self.tmp/'out/windows.jsonl').read_text().splitlines()]
        self.assertTrue(any(x['v81_causal_handoff']['accepted_inputs']==1 for x in windows))
        self.assertTrue(any(x['v81_causal_handoff']['proven_native_scalp_inputs']==1 for x in windows))

    def test_missing_coinbase_response_is_not_rebuilt(self):
        self.setup_case(missing_btc=True)
        with self.assertRaisesRegex(ValueError,'V81_LINKS_EXACT_BTC_RESPONSE_MISSING'):
            self.verify()
        self.assertFalse((self.tmp/'out/window_inventory_manifest.json').exists())

    def test_missing_original_brti_read_is_not_rebuilt(self):
        self.setup_case(missing_brti=True)
        with self.assertRaisesRegex(ValueError,'V81_LINKS_EXACT_BRTI_READ_MISSING'):
            self.verify()

    def test_quote_source_older_than_original_six_second_limit_rejected(self):
        self.setup_case(changed_quote=True)
        with self.assertRaisesRegex(ValueError,'QUOTE_HANDOFF_EXACT_ACCEPTED_DEPTH_PRICE_MISMATCH'):
            self.verify()

    def test_original_brti_source_older_than_five_seconds_rejected(self):
        self.setup_case(brti_age=6)
        with self.assertRaisesRegex(ValueError,'V81_LINKS_ORIGINAL_INPUT_NOT_QUALIFIED'):
            self.verify()

    def test_wrong_market_strike_is_never_substituted(self):
        self.setup_case(bad_market=True)
        with self.assertRaisesRegex(ValueError,'SOURCE_HANDOFF_EXACT_OFFICIAL_MARKET_MISSING'):
            self.verify()

    def test_quote_state_missing_exact_source_sequence_is_not_inferred(self):
        self.setup_case(missing_delta=True)
        with self.assertRaisesRegex(ValueError,'QUOTE_HANDOFF_EXACT_ACCEPTED_DEPTH_MISSING'):
            self.verify()

    def test_wrong_attempt_cannot_inherit_another_input(self):
        self.setup_case(wrong_attempt=True)
        with self.assertRaisesRegex(ValueError,'V81_LINKS_EXACT_V81_INPUT_OR_ATTEMPT_MISSING'):
            self.verify()

    def test_original_evidence_gap_quarantines_subsequent_native(self):
        a=make_archive(self.root)
        original_market(a)
        quote=quote_book(a)
        btc=btc_http(a)
        brti=brti_read(a)
        p=v81_row(a,quote,brti[0],btc,brti)
        a.write('EVIDENCE_GAP',dict(reasons={'QUEUE_BYTES':7}))
        scalp_native(a,p)
        a.write('STOP',dict(clean=True));a.close()
        out=self.verify()
        summary=out['v81_causal_handoff']
        self.assertTrue(summary['quarantined_on_original_loss'])
        self.assertEqual(summary['original_evidence_counts'].get(
            'ORIGINAL_SCALP_FULL_CAUSAL_INPUT_AND_QUOTE',0),0)
        self.assertEqual(summary['original_evidence_counts']['NATIVE_OR_INPUT_DISQUALIFIED_AFTER_GAP'],1)
        self.assertFalse(out['loss_free'])

    def test_bounded_original_input_cache_does_not_silently_retain_old(self):
        self.setup_case()
        out=self.verify(max_inputs=1)
        self.assertLessEqual(out['v81_causal_handoff']['max_retained_accepted_inputs'],1)


if __name__=='__main__':unittest.main()
