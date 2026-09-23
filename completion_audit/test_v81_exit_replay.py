import gzip
import json
from pathlib import Path
import tempfile
import unittest
from replay_v81_exits import evaluate,epoch


class PublishedEventReplay(unittest.TestCase):
    def rows(self,late=False):
        def quote(ts,bid):
            return dict(record_type='SNAPSHOT_INPUT',run_id='test',ticker='KXBTC15M-A',close_utc='2026-09-23T20:45:00Z',
                        observed_utc=ts,quote_validation_utc=ts,quote_transport='timestamped_contiguous_ws',
                        brti_source_ts_ms=int((epoch(ts)-1)*1000),target=84362.95,
                        up_bid=bid,down_bid=bid,up_ask=max(.35,bid+.01),down_ask=max(.35,bid+.01),signal_only=True,orders=False)
        receipt='2026-09-23T20:31:04Z'if late else'2026-09-23T20:31:01Z'
        event=dict(contract='KXBTC15M-A',side='DOWN',entry_price=.35,signal_timestamp_utc='2026-09-23T20:31:00Z')
        t=epoch(event['signal_timestamp_utc']);event['signal_ts']=t
        event['entry_provenance']=dict(schema='V81_TIMESTAMPED_INPUTS_V1',ticker='KXBTC15M-A',
            open_ts=epoch('2026-09-23T20:30:00Z'),close_ts=epoch('2026-09-23T20:45:00Z'),target=84362.95,
            signal_only=True,orders=False,quote=dict(ticker='KXBTC15M-A',transport='timestamped_contiguous_ws',
                epoch='ws',market_id='market',sid=1,sequence=2,source_ts_ms=int((t-.2)*1000),
                validated_at_ms=int(t*1000),down_ask=.35),
            brti=dict(source_ts_ms=int((t-1)*1000),status='PRIMARY_OK',clean_for_qualification=True,
                owner_epoch='owner',value=84345.17))
        observation=dict(record_type='OBSERVATION',run_id='test',sources=[dict(service='v81',response_received_utc=receipt,
            state=dict(active=True,manual_execution_only=True,order_action=None,generated_utc='2026-09-23T20:31:00Z',last_signal_event=event))])
        return [quote('2026-09-23T20:30:59Z',.33),observation,quote('2026-09-23T20:31:01.5Z',.34),quote('2026-09-23T20:31:02Z',.41),quote('2026-09-23T20:31:03Z',.39)]

    def run_rows(self,rows):
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'data.gz'
            path.write_bytes(b''.join(gzip.compress(json.dumps(row).encode())for row in rows))
            return evaluate(path,'2026-09-23T20:30:00Z','2026-09-23T20:45:00Z',run_id='test')

    def test_real_event_schema_connects_to_bid_protection_state_machine(self):
        result=self.run_rows(self.rows())
        self.assertEqual(len(result['published_entries']),1)
        self.assertEqual(result['counts'],{'INCOMPLETE_PATH':3,'PROTECT':1})
        closed=next(x for x in result['outcomes']if x['status']=='PROTECT')
        self.assertEqual(closed['side'],'DOWN');self.assertAlmostEqual(closed['exit_bid_minus_entry_ask'],.04)
        self.assertFalse(result['production_connected'])
    def test_late_event_keeps_rejection_instead_of_backdating_entry(self):
        result=self.run_rows(self.rows(late=True))
        self.assertEqual(len(result['published_entries']),1);self.assertEqual(len(result['rejected_entries']),1)
        self.assertFalse(result['outcomes'])
    def test_mixed_runs_cannot_be_silently_joined(self):
        rows=self.rows();rows[-1]['run_id']='other'
        with self.assertRaisesRegex(ValueError,'Mixed run'):self.run_rows(rows)
    def test_legacy_40c_signal_cannot_invent_immediate_16c_gain(self):
        rows=self.rows();event=rows[1]['sources'][0]['state']['last_signal_event']
        event['entry_price']=.4;del event['entry_provenance']
        for row in rows[2:]:row.update(down_bid=.56,down_ask=.57)
        result=self.run_rows(rows)
        self.assertEqual(len(result['published_entries']),1)
        self.assertIn('ENTRY_SOURCE_PROVENANCE_MISSING',result['rejected_entries'][0]['reason'])
        self.assertEqual(result['outcomes'],[])
    def test_first_observed_ask_above_entry_is_not_replaced_by_later_dip(self):
        rows=self.rows();rows[2]['down_ask']=.57;rows[3]['down_ask']=.30
        result=self.run_rows(rows)
        self.assertIn('PRICE_UNAVAILABLE',result['rejected_entries'][0]['reason'])
        self.assertEqual(result['outcomes'],[])
    def test_missing_ask_or_stale_entry_brti_remains_unscored(self):
        rows=self.rows();del rows[2]['down_ask']
        self.assertIn('ASK_MISSING',self.run_rows(rows)['rejected_entries'][0]['reason'])
        rows=self.rows();p=rows[1]['sources'][0]['state']['last_signal_event']['entry_provenance']
        p['brti']['source_ts_ms']-=5001
        self.assertIn('BRTI_SOURCE_INVALID',self.run_rows(rows)['rejected_entries'][0]['reason'])


if __name__=='__main__':unittest.main()
