import unittest
import numpy as np
import pandas as pd
from prepare import backward_join, histories, close_time, CUTOFF, ROOT
from score import causal_union, attributed, first_calls, masks, wilson, oracle

class StudyTests(unittest.TestCase):
    def test_backward_join_never_takes_future(self):
        t=pd.Timestamp('2026-09-03T10:00:00Z')
        left=pd.DataFrame({'contract':['a','b'],'timestamp':[t,t],'target':[100,100]})
        right=pd.DataFrame({'contract':['a','a','b'],'timestamp':[t-pd.Timedelta(seconds=2),t+pd.Timedelta(seconds=1),t],
                            'target':[100,100,101],'value':[7,99,55]})
        out=backward_join(left,right,'f_').set_index('contract')
        self.assertEqual(out.loc['a','f_value'],7)
        self.assertEqual(out.loc['a','f_lag'],2)
        self.assertTrue(pd.isna(out.loc['b','f_value']))

    def test_causal_ladder_cannot_replace_earlier_loser(self):
        t=pd.Timestamp('2026-09-03T10:00:00Z')
        a=pd.DataFrame([dict(contract='x',timestamp=t,side='DOWN',family='A',row_id='a')])
        t1=pd.DataFrame([dict(contract='x',timestamp=t+pd.Timedelta(minutes=1),side='UP',family='T1',row_id='b')])
        self.assertEqual(causal_union([t1,a]).iloc[0].side,'DOWN')
        parts=attributed([t1,a]);self.assertEqual(len(parts[1]),0)
        self.assertEqual(sum(map(len,parts)),len(causal_union([t1,a])))

    def test_equal_time_priority_and_ambiguity(self):
        t=pd.Timestamp('2026-09-03T10:00:00Z')
        a=pd.DataFrame([dict(contract='x',timestamp=t,side='DOWN',family='A',row_id='a')])
        t1=pd.DataFrame([dict(contract='x',timestamp=t,side='UP',family='T1',row_id='b')])
        self.assertEqual(causal_union([a,t1]).iloc[0].family,'T1')
        self.assertEqual(len(first_calls(pd.concat([a,t1]))),0)

    def test_history_features_do_not_change_with_future_suffix(self):
        t=pd.date_range('2026-09-03T10:00:00Z',periods=31,freq='5s')
        d=pd.DataFrame({'contract':'x','side':'UP','timestamp':t,'price':100+np.arange(31)*.1,'fair':.5+np.arange(31)*.01,'ask':.4})
        before=histories(d.iloc[:25]);after=histories(d)
        cols=['sigma','fair_delta15','fair_delta30','ask_delta30']
        pd.testing.assert_frame_equal(before[cols],after.iloc[:25][cols])

    def test_ticker_cutoff(self):
        self.assertEqual(close_time('KXBTC15M-26SEP052300-00'),pd.Timestamp('2026-09-06T03:00:00Z'))
        self.assertGreater(close_time('KXBTC15M-26SEP210315-15'),CUTOFF)

    def test_wilson_tiny_sample(self):
        self.assertLess(wilson(5,5)[0],.85)

    def test_archived_tier1_exact_mask_parity(self):
        original=pd.read_csv(ROOT/'union_optimizer_processed_snapshot_cache.csv')
        expected=original[(original.preferred_ask<=.45)&(original.preferred_fair>=.75)&(original.edge>=.08)&
            original.remaining.between(2,10)&(original.abs_dist_target>=25)].sort_values(['snapshot_utc']).drop_duplicates('ticker')
        d=pd.read_csv(__import__('pathlib').Path(__file__).parent/'features.csv.gz',low_memory=False)
        d=d[d.cohort=='august_replay'];d['timestamp']=pd.to_datetime(d.timestamp,utc=True)
        actual=first_calls(d[masks(d)['T1']])
        self.assertEqual(set(actual.contract),set(expected.ticker))
        self.assertEqual(len(actual),38)
        left=actual.set_index('contract').ask.sort_index();right=expected.set_index('ticker').preferred_ask.sort_index()
        np.testing.assert_allclose(left,right)

    def test_oracle_bound(self):
        d=pd.DataFrame({'contract':['a','b','c'],'side':['UP','UP','UP'],'official_side':['UP','DOWN','DOWN'],
            'valid_clock':True,'valid_quote':True,'remaining':8,'ask':.4})
        m=pd.DataFrame({'contract':['a','b','c']})
        r=oracle(d,m,2)
        self.assertEqual(r['winner_affordable_contracts'],1)
        self.assertEqual(r['max_calls_at_93pct_accuracy'],1)

if __name__=='__main__':unittest.main()
