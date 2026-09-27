import json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from btc15_wednesday_report_v1 import report,comparison

def row(contract,ts,**kw):
    r=dict(schema='BTC15_COHORT_NATIVE_V1',timestamp_utc=ts,contract=contract,target=100.0,
           final_status='PASS',final_side=None,early={'provisional_candidate':False},
           unified_row_count=1,true_scalp_pending=0,profit_pending=0,brti=None,
           signal_only=True,orders=False)
    r.update(kw);return r

class WednesdayReportTests(unittest.TestCase):
    def test_window_is_half_open_and_settlement_is_disk_only(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.jsonl'
            rows=[row('BEFORE','2026-09-27T13:44:59Z'),
                  row('A','2026-09-27T13:45:00Z'),
                  row('A','2026-09-27T13:59:59Z',brti={'contract':'A','target':100,'final60_complete':True,'final60_count':60,'final60_side':'UP','final60_average':101}),
                  row('AFTER','2026-09-27T14:00:00Z')]
            p.write_text(''.join(json.dumps(x)+'\n' for x in rows))
            x=report(p,datetime(2026,9,27,13,45,tzinfo=timezone.utc),datetime(2026,9,27,14,0,tzinfo=timezone.utc))
            self.assertEqual(x['contract_count'],1);self.assertEqual(x['settlement_complete'],1)
            self.assertEqual(x['contracts'][0]['ticker'],'A')

    def test_no_hindsight_pass_becomes_win(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.jsonl'
            rows=[row('A','2026-09-27T13:45:01Z'),
                  row('A','2026-09-27T13:59:59Z',brti={'contract':'A','target':100,'final60_complete':True,'final60_count':60,'final60_side':'UP','final60_average':101})]
            p.write_text(''.join(json.dumps(x)+'\n' for x in rows))
            x=report(p,datetime(2026,9,27,13,45,tzinfo=timezone.utc),datetime(2026,9,27,14,0,tzinfo=timezone.utc))
            self.assertEqual(x['final_qualified'],0);self.assertIsNone(x['final_accuracy_pct']);self.assertEqual(x['final_pass'],1)

    def test_ground_zero_comparison_is_explicit(self):
        gz={'contract_count':1,'final_qualified':0,'final_accuracy_pct':None,'final_pass':1,
            'settlement_complete':1,'evidence_complete_pct':100.0,'final_wins':0,'final_losses':0,
            'early_qualified':0,'early_entry_count':0,'early_le_50':0,'early_ideal_25_35':0,
            'scalp_qualified':0,'profit_recorded':0,'five_minute_rows':30,'three_minute_rows':6,
            'signal_only_violations':0,'orders':0}
        full=dict(gz,contract_count=20,final_qualified=5,final_wins=5,final_accuracy_pct=100.0)
        c=comparison(gz,full)
        self.assertEqual(c['contract_count'],{'ground_zero':1,'full_run':20})
        self.assertEqual(c['final_qualified'],{'ground_zero':0,'full_run':5})
        self.assertIsNone(c['final_accuracy_pct']['ground_zero'])

    def test_signal_only_violation_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.jsonl';p.write_text(json.dumps(row('A','2026-09-27T13:45:01Z',orders=True))+'\n')
            with self.assertRaises(ValueError): report(p,datetime(2026,9,27,13,45,tzinfo=timezone.utc),datetime(2026,9,27,14,0,tzinfo=timezone.utc))
if __name__=='__main__':unittest.main()
