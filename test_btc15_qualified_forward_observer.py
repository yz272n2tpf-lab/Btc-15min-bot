import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from btc15_qualified_forward_observer_v1 import observation, append

class ForwardEvidence(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc)
        stamp=self.now.isoformat()
        self.state=dict(contract='KXBTC15M-TEST',source_timestamp_utc=stamp,
                        health=dict(paired_quotes=True),safety=dict(read_only=True,orders_enabled=False),
                        timer=dict(seconds_left=500),market=dict(brti_ready=True,brti_value=100000.,brti_age_seconds=1),
                        parity=dict(status='PASS',contract='KXBTC15M-TEST',api_contract='KXBTC15M-TEST',timestamp_utc=stamp),
                        final=dict(ready=True),early=dict(ready=True),scalp=dict(ready=True))

    def test_raw_anchor_is_not_qualified_when_parity_waits(self):
        self.state['parity']['status']='WAIT'
        row=observation(self.state,self.now)
        self.assertTrue(row['lanes']['final']['raw_ready'])
        self.assertFalse(row['lanes']['final']['source_qualified'])
        self.assertFalse(row['lanes']['final']['publication_eligible'])

    def test_stale_and_cross_ticker_fail_closed(self):
        self.assertTrue(observation(self.state,self.now)['lanes']['final']['source_qualified'])
        self.assertFalse(observation(self.state,self.now+timedelta(seconds=6))['lanes']['final']['source_qualified'])
        self.state['parity']['contract']='OLD'
        self.assertFalse(observation(self.state,self.now)['usable_frame'])

    def test_restart_appends_preserve_prior_evidence_and_unavailability(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'evidence.csv'
            append(observation(self.state,self.now),p)
            append(dict(observed_utc=self.now.isoformat(),record_type='UNAVAILABLE'),p)
            with p.open() as f: rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[1]['record_type'],'UNAVAILABLE')

if __name__=='__main__': unittest.main()
