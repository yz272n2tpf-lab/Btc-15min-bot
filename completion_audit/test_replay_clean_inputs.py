import copy
import gzip
import json
import tempfile
from pathlib import Path
import unittest
import pandas as pd
from replay_clean_inputs import feature_builder, features_at, replay


class ForwardAvailability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder=staticmethod(feature_builder(Path(__file__).resolve().parents[1]/'bot_two_output_build_v4_13_profit_protection_shadow.py'))

    def setUp(self):
        self.rows=[]
        for i in range(49):
            now=pd.Timestamp('2026-09-23T20:36:00Z')+pd.Timedelta(seconds=15*i)
            self.rows.append(dict(record_type='SNAPSHOT_INPUT',ticker='KXBTC15M-FIXTURE',
                observed_utc=now.isoformat(),close_utc='2026-09-23T21:00:00Z',target=100.,
                brti_source_ts_ms=int((now-pd.Timedelta(seconds=1)).timestamp()*1000),
                btc_source_utc=(now-pd.Timedelta(milliseconds=200)).isoformat(),
                btc_received_utc=(now-pd.Timedelta(milliseconds=100)).isoformat(),
                btc_price=100+i*.1,orders=False,signal_only=True))
        self.decision=self.rows[-1]

    def test_future_and_late_received_values_cannot_change_past_features(self):
        original,status=features_at(self.rows,self.decision,self.builder)
        self.assertEqual(status,'READY')
        poison=copy.deepcopy(self.rows[-1]);poison.update(observed_utc='2026-09-23T20:48:01Z',
            btc_received_utc='2026-09-23T20:48:01Z',btc_price=999999.)
        changed,_=features_at(self.rows+[poison],self.decision,self.builder)
        self.assertEqual(original,changed)

    def test_receipt_time_never_fills_missing_source_time(self):
        for row in self.rows:row['btc_source_utc']=None
        result,status=features_at(self.rows,self.decision,self.builder)
        self.assertIsNone(result);self.assertEqual(status,'INSUFFICIENT_PAST_AVAILABLE_HISTORY')

    def test_stale_brti_remains_wait(self):
        self.decision['brti_source_ts_ms']-=5000
        result,status=features_at(self.rows,self.decision,self.builder)
        self.assertIsNone(result);self.assertEqual(status,'BRTI_SOURCE_NOT_FRESH')

    def test_fixed_target_conflict_is_rejected(self):
        self.rows[0]['target']=101.
        with self.assertRaisesRegex(ValueError,'target changed'):features_at(self.rows,self.decision,self.builder)

    def test_future_source_at_receipt_is_rejected(self):
        self.rows[0]['btc_source_utc']='2026-09-23T20:36:01Z'
        with self.assertRaisesRegex(ValueError,'Future BTC'):features_at(self.rows,self.decision,self.builder)

    def test_mixed_run_rejected_even_before_feature_window(self):
        source=Path(__file__).resolve().parents[1]/'bot_two_output_build_v4_13_profit_protection_shadow.py'
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'journal.gz'
            path.write_bytes(gzip.compress(json.dumps(dict(record_type='OBSERVATION',run_id='old')).encode()))
            with self.assertRaisesRegex(ValueError,'Mixed collector'):
                replay(path,source,'2026-09-23T21:15:00Z','2026-09-23T21:30:00Z',run_id='new')

    def test_all_input_replay_keeps_every_captured_decision(self):
        source=Path(__file__).resolve().parents[1]/'bot_two_output_build_v4_13_profit_protection_shadow.py'
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'journal.gz'
            path.write_bytes(b''.join(gzip.compress(json.dumps(dict(row,run_id='new')).encode())for row in self.rows))
            result=replay(path,source,'2026-09-23T20:45:00Z','2026-09-23T21:00:00Z',0,run_id='new')
            self.assertEqual(len(result['decisions']),13)
            self.assertEqual(result['run_id'],'new')


if __name__=='__main__':unittest.main()
