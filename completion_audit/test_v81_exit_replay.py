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
                        brti_source_ts_ms=int((epoch(ts)-1)*1000),up_bid=bid,down_bid=bid,signal_only=True,orders=False)
        receipt='2026-09-23T20:31:04Z'if late else'2026-09-23T20:31:01Z'
        event=dict(contract='KXBTC15M-A',side='DOWN',entry_price=.35,signal_timestamp_utc='2026-09-23T20:31:00Z')
        observation=dict(record_type='OBSERVATION',run_id='test',sources=[dict(service='v81',response_received_utc=receipt,
            state=dict(active=True,manual_execution_only=True,order_action=None,generated_utc='2026-09-23T20:31:00Z',last_signal_event=event))])
        return [quote('2026-09-23T20:30:59Z',.33),observation,quote('2026-09-23T20:31:02Z',.41),quote('2026-09-23T20:31:03Z',.39)]

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


if __name__=='__main__':unittest.main()
