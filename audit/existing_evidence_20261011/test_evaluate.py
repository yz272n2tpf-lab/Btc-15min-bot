"""Selection, causality and denominator regressions for offline analysis."""
import copy
import unittest
from datetime import datetime, timezone
from audit.existing_evidence_20261011 import evaluate as e
from audit.existing_evidence_20261011.catalog import csv_summary


class EvidenceTests(unittest.TestCase):
    def test_duplicate_rows_do_not_inflate_sample(self):
        rows, d=e.unique_rows([dict(contract='A',time=1,p=.91)]*3,['contract','time'])
        self.assertEqual((len(rows),d['duplicates']),(1,2))

    def test_conflicting_identity_is_excluded_not_first_wins(self):
        a=dict(contract='A',time=1,p=.91);b=dict(a,p=.95)
        for records in ([a,b,a],[b,a,b]):
            rows,d=e.unique_rows(records,['contract','time'])
            self.assertEqual(rows,[]);self.assertEqual(d['conflicting_keys'],1)

    def test_outcomes_do_not_select_entry(self):
        a=dict(contract='A',time=1,p=.91,left=420,gap=80,side='UP',correct=False)
        b=dict(a,time=2,p=.95,left=410,correct=True)
        rows=[b,a];selected=e.first_per_contract(rows,lambda r:r['p']>=.90)
        self.assertEqual(selected,[a])
        changed=[dict(r,correct=not r['correct'])for r in rows]
        self.assertEqual(e.first_per_contract(changed,lambda r:r['p']>=.90)[0]['time'],1)

    def test_existing_distance_schedule_boundaries(self):
        self.assertEqual(e.distance('CURRENT_75_50',360.001),75)
        self.assertEqual(e.distance('CURRENT_75_50',360),50)
        self.assertEqual(e.distance('FIXED_40',420),40)
        self.assertEqual(e.distance('NO_FIXED',420),0)

    def test_ablation_preserves_confidence_and_one_contract_denominator(self):
        a=dict(contract='A',time=1,p=.89,left=420,gap=20,side='UP',correct=True)
        b=dict(a,contract='B',p=.92)
        table=e.policy_table([a,b,dict(b,time=2,left=419)],lambda r:r['p']>=.90)
        self.assertEqual(table['CURRENT_75_50']['selected_contracts'],0)
        self.assertEqual(table['FIXED_20']['selected_contracts'],1)
        self.assertEqual(table['NO_FIXED']['selected_contracts'],1)

    def test_outcome_denominator_excludes_unlabeled(self):
        s=e.stats([dict(correct=True,p=.9,left=100),dict(correct=None,p=.9,left=90)])
        self.assertEqual((s['selected_contracts'],s['labeled_contracts']),(2,1))
        self.assertIsNone(e.wilson(0,0))
        self.assertLess(e.wilson(6,6)[0],.7)

    @staticmethod
    def quote(sec,bid=.6):
        t=datetime.fromtimestamp(1000+sec,timezone.utc).isoformat()
        return dict(timestamp_utc=t,target=83000,up_bid=bid,up_ask=bid+.01,
                    brti=dict(direct_brti_ready=True,brti_timestamp_utc=t))

    def test_future_or_stale_brti_rejected(self):
        for delta in (-1,6):
            r=self.quote(0);r['brti']['brti_timestamp_utc']=self.quote(-delta)['timestamp_utc']
            self.assertFalse(e.usable_quote_observation(r,'UP',83000))

    def test_target_crossed_quote_or_known_outage_rejected(self):
        r=self.quote(0)
        for bad in (dict(r,target=83001),dict(r,up_bid=.7),dict(r,brti={'direct_brti_ready':False}),dict(r,up_bid=None)):
            self.assertFalse(e.usable_quote_observation(bad,'UP',83000))

    def test_fixed_horizon_selects_first_not_best_future_bid(self):
        seq=[self.quote(i)for i in range(0,261,5)];seq[-1]['up_bid']=.99;seq[-1]['up_ask']=1
        r=e.fixed_horizon_quote(seq,1000,240,500,'UP',83000)
        self.assertEqual(e.epoch(r['timestamp_utc']),1240)
        self.assertEqual(r['up_bid'],.6)

    def test_horizon_rejects_gap_expiry_and_missing_origin(self):
        seq=[self.quote(i)for i in range(0,246,5)]
        self.assertIsNone(e.fixed_horizon_quote(seq,1000,240,29.1,'UP',83000))
        self.assertIsNone(e.fixed_horizon_quote(seq,1000,240,240,'UP',83000))
        self.assertIsNone(e.fixed_horizon_quote(seq[1:],1000,240,500,'UP',83000))
        self.assertIsNone(e.fixed_horizon_quote(seq[:4]+seq[9:],1000,240,500,'UP',83000))

    def test_fee_scenario_uses_dollars_and_rounds_each_leg(self):
        self.assertEqual(e.fee_scenario(.5),.02)
        self.assertEqual(e.fee_scenario(.05),.01)
        self.assertEqual(e.fee_scenario(0),0)

    def test_catalog_distinguishes_rows_contracts_and_duplicate_ids(self):
        s=csv_summary(b'contract_id,timestamp_utc,ask\nA,2026-09-24T00:00:00Z,.5\nA,2026-09-24T00:00:00Z,.5\nB,2026-09-24T00:15:00Z,\n')
        self.assertEqual((s['rows'],s['exact_unique_rows'],s['contracts']),(3,2,2))
        self.assertEqual(s['missing_by_column']['ask'],1)


if __name__=='__main__':unittest.main()
