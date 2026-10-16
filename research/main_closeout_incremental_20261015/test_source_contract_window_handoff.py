"""Existing reader: exact source/official-market/settlement window-handoff regressions.

All fixtures emit original archive events using the same Archive.source and
Archive.observe as native capture. No live quotes, Kalshi network, simulated
entry prices or new EARLY validator. Full CampaignVerifier remains required.
"""
import base64
from datetime import datetime,timezone
import json
import tempfile
import unittest
from pathlib import Path

from btc15_ladder_settlement_v2 import receipt as settlement_receipt
from candidates.early_recording_20261012.archive import Archive,BUDGET
from ops.recording_workflow.policy import local_policy
from ops.recording_workflow.evidence import streaming_window_inventory
from ops.live_recording.policy import canonical,sha
from ops.live_recording.source_contract_window_handoff_research import SourceContractWindowHandoff
from ops.live_recording.native_window_handoff_research import NativeJournalWindowHandoff

TICKER='KXBTC15M-26OCT161130-30'
OPEN=1792012500.
CLOSE=OPEN+900
CUT=OPEN+120
TARGET=64200.0


def iso(unix):
    return datetime.fromtimestamp(unix,timezone.utc).isoformat().replace('+00:00','Z')


def market(*,target=TARGET,status='active',result=None):
    return dict(ticker=TICKER,open_time=iso(OPEN),close_time=iso(CLOSE),
                floor_strike=target,status=status,result=result,
                is_provisional=False,settlement_ts=None,
                event_ticker='TEST-BTC',strike_type='greater',
                rules_primary='BTC above the start price',
                rules_secondary='')


def archive(root,segment_bytes=2048):
    a=Archive(root/'source',evidence_class='FIXTURE',
              source_binding='fixture-causality',
              budget=dict(BUDGET,segment_bytes=segment_bytes,
                          max_total_bytes=32*1024**2),
              storage_policy=local_policy())
    a.start()
    return a


def source(a,asset, *, value=None,source_time=None,received=None):
    val=64199.0 if asset=='BTC' else 64201.0
    a.source(dict(asset=asset,
                  value=val if value is None else value,
                  source_ts=(CUT-4 if asset=='BTC' else CUT-6) if source_time is None else source_time,
                  receipt_ts=(CUT-2 if asset=='BTC' else CUT-3) if received is None else received,
                  original_receipt_ts=(CUT-2 if asset=='BTC' else CUT-3) if received is None else received,
                  available_at=(CUT-2 if asset=='BTC' else CUT-3) if received is None else received,
                  feed='BTC:TEST' if asset=='BTC' else 'BRTI:TEST',
                  epoch='BTC-EPOCH' if asset=='BTC' else 'BRTI-EPOCH',
                  basis='ORIGINAL',accepted_by_owner=True,
                  epoch_basis='TEST',receipt_basis='ORIGINAL_OWNER'))
    return val


def metadata(a,*,target=TARGET,received=CUT-8):
    blob=canonical(dict(market=market(target=target)))
    a.observe('HTTP_RESPONSE',dict(raw=blob,
        endpoint='/trade-api/v2/markets/'+TICKER,received_at=received,
        receipt_basis='HTTP_GET_RETURN_BEFORE_NATIVE_DECODE',
        source='EXISTING_KALSHI_HTTP'))


def frame(*,target=TARGET,btc_received=CUT-2):
    return dict(contract=TICKER,feature_cutoff=CUT,
                captured_ts=CUT+.5,official_open=OPEN,official_close=CLOSE,
                target=target,
                btc_source=CUT-4,btc_received=btc_received,btc_price=64199.0,
                brti=dict(cf_ts=CUT-6,value=64201.0,
                          delivery=dict(observed_ts=CUT-3,owner_epoch='BRTI-EPOCH')),
                native_epoch='NATIVE-EPOCH',native_sequence=19)


def native(a,n,seq, *,journal='ORIGINAL-MAIN'):
    raw=canonical(n)
    a.write('NATIVE_RECORD',dict(raw=raw.decode(),sha256=sha(raw),
             original_journal=journal,sequence=seq,
             committed_at=n['published_ts']+.01,
             record_basis='POST_ORIGINAL_COMMIT',lane='main'))


def decision(a,*,f=None,seq=400):
    f=frame() if f is None else f
    n=dict(kind='NATIVE_DECISION',candidate='MAIN',
           contract=TICKER,evidence=f,
           published_ts=f['captured_ts']+.001,
           event='PASS')
    native(a,n,seq)
    return n


def outcome(a,*,raw_receipt_time=None,accept_time=None,received_time=None):
    received=CLOSE+30 if received_time is None else received_time
    timestamp=received if raw_receipt_time is None else raw_receipt_time
    accepted=received+.1 if accept_time is None else accept_time
    original=canonical(dict(market=market(status='finalized',result='yes')))
    a.write('ORIGINAL_RESPONSE',dict(raw_base64=base64.b64encode(original).decode(),
        sha256=sha(original),endpoint='https://external-api.kalshi.com/trade-api/v2/markets/'+TICKER,
        received_at=timestamp,status_code=200,
        receipt_basis='HTTP_GET_RETURN_BEFORE_NATIVE_DECODE',
        source='EXISTING_OWNER_RESPONSE'))
    value=settlement_receipt(TICKER,OPEN,json.loads(original),received)
    raw=canonical(value)
    a.write('OUTCOME_ACCEPTANCE',dict(raw=raw.decode(),sha256=sha(raw),
        response_sha256=sha(original),accepted_at=accepted))
    native(a,dict(kind='SETTLEMENT',contract=TICKER,settlement=value,
        published_ts=accepted+.1),401)
    return value


class SourceContractHandoffOffline(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp=Path(self.temp.name)
        self.root=self.tmp/'src'
        self.root.mkdir()

    def run_source(self,**kw):
        return streaming_window_inventory(self.root,self.tmp/'audited',
                  max_window_records=1,max_window_bytes=5*1024**2,
                  source_handoff=SourceContractWindowHandoff(**kw),
                  native_handoff=NativeJournalWindowHandoff())

    def prepared(self,*,market_target=TARGET):
        a=archive(self.root)
        source(a,'BTC')
        source(a,'BRTI')
        metadata(a,target=market_target)
        return a

    def test_exact_original_btc_brti_and_official_market_causal_join(self):
        a=self.prepared()
        decision(a)
        a.write('STOP',dict(clean=True));a.close()
        report=self.run_source()
        hand=report['source_contract_handoff']
        self.assertEqual(hand['record_kinds']['MAIN_EXACT_BTC_BRTI_OFFICIAL_CUTOFF'],1)
        self.assertEqual(hand['record_kinds']['OFFICIAL_MARKET_IDENTITY'],1)
        self.assertEqual(hand['record_kinds']['SOURCE'],2)
        self.assertEqual(hand['original_evidence_gap_envelopes'],0)
        self.assertFalse(hand['source_quote_and_native_decision_fully_associated'])
        self.assertFalse(hand['full_campaign_qualified'])
        windows=[json.loads(x) for x in (self.tmp/'audited/windows.jsonl').read_text().splitlines()]
        self.assertTrue(any(z['source_contract_handoff']['main_exact_original_source_metadata_decisions']==1
                            for z in windows))
        self.assertFalse((self.tmp/'audited/index.sqlite3').exists())

    def test_missing_brti_fails_even_if_btc_and_metadata_exist(self):
        a=archive(self.root)
        source(a,'BTC');metadata(a);decision(a)
        a.write('STOP',dict(clean=True));a.close()
        with self.assertRaisesRegex(ValueError,'SOURCE_HANDOFF_MISSING_OR_AMBIGUOUS_SOURCE:BRTI'):
            self.run_source()
        self.assertFalse((self.tmp/'audited/window_inventory_manifest.json').exists())

    def test_native_btc_source_cannot_be_backdated(self):
        a=self.prepared()
        changed=frame(btc_received=CUT+1)
        decision(a,f=changed)
        a.write('STOP',dict(clean=True));a.close()
        with self.assertRaisesRegex(ValueError,'SOURCE_HANDOFF_DECISION_SOURCE_CUTOFF'):
            self.run_source()

    def test_different_market_floor_target_is_not_interchangeable(self):
        a=self.prepared(market_target=TARGET+10)
        decision(a)
        a.write('STOP',dict(clean=True));a.close()
        with self.assertRaisesRegex(ValueError,'SOURCE_HANDOFF_EXACT_OFFICIAL_MARKET_MISSING'):
            self.run_source()

    def test_same_original_source_republication_is_exact_distinct_receipt(self):
        a=self.prepared()
        source(a,'BTC',source_time=CUT-4,received=CUT-1)
        f=frame(btc_received=CUT-1)
        decision(a,f=f)
        a.write('STOP',dict(clean=True));a.close()
        out=self.run_source()
        self.assertEqual(out['source_contract_handoff']['record_kinds']['SOURCE_REPEAT'],1)
        self.assertEqual(out['source_contract_handoff']['record_kinds']['MAIN_EXACT_BTC_BRTI_OFFICIAL_CUTOFF'],1)

    def test_authoritative_outcome_matches_original_http_and_acceptance(self):
        a=self.prepared();decision(a)
        outcome(a)
        a.write('STOP',dict(clean=True));a.close()
        out=self.run_source()['source_contract_handoff']
        self.assertEqual(out['record_kinds']['AUTHORITATIVE_ORIGINAL_SETTLEMENT_ASSOCIATIONS'],1)
        self.assertEqual(out['record_kinds']['EXACT_ORIGINAL_SETTLEMENT_ASSOCIATIONS'],1)
        self.assertFalse(out['full_campaign_qualified'])

    def test_future_http_settlement_receipt_cannot_be_used(self):
        a=self.prepared();decision(a)
        outcome(a,raw_receipt_time=CLOSE+90)
        a.write('STOP',dict(clean=True));a.close()
        with self.assertRaisesRegex(ValueError,'SOURCE_HANDOFF_OUTCOME_RESPONSE_FROM_FUTURE'):
            self.run_source()

    def test_bad_original_raw_sha_fails_closed(self):
        a=archive(self.root)
        data=b'{"market":{"ticker":"tampered"}}'
        a.write('HTTP_BYTES',dict(raw_base64=base64.b64encode(data).decode(),
                                  sha256='0'*64))
        a.write('STOP',dict(clean=True));a.close()
        with self.assertRaisesRegex(ValueError,'SOURCE_HANDOFF_ORIGINAL_RAW_HASH'):
            self.run_source()

    def test_original_source_gap_quarantines_later_native_decisions(self):
        a=self.prepared()
        a.write('SOURCE_GAP',dict(reason='EXISTING_OWNER_FAILURE',observed_at=CUT-4))
        decision(a)
        a.write('STOP',dict(clean=True));a.close()
        out=self.run_source()
        src=out['source_contract_handoff']
        self.assertTrue(src['quarantined_on_loss'])
        self.assertNotIn('MAIN_EXACT_BTC_BRTI_OFFICIAL_CUTOFF',src['record_kinds'])
        self.assertEqual(src['original_evidence_gap_envelopes'],1)
        self.assertFalse(out['loss_free'])

    def test_small_source_retention_cap_rejects_not_truncates(self):
        a=self.prepared()
        decision(a)
        a.write('STOP',dict(clean=True));a.close()
        with self.assertRaisesRegex(ValueError,'SOURCE_HANDOFF_ORIGINAL_OBSERVATIONS_CAP'):
            self.run_source(max_sources=1)
        self.assertFalse((self.tmp/'audited/window_inventory_manifest.json').exists())


if __name__=='__main__':
    unittest.main()
