import unittest
from copy import deepcopy
from replay import measure,early_signals,build_serial,value_entry,scalp_lane,continuous,read_source

def candidate(cid,t,ask=.30,bid=.29,side='UP',btc=110,target=100):
    return {'contract':'C','candidate_id':cid,'_t':t,'side':side,'seconds_left':'600','btc30':'15',
            'entry_ask':str(ask),'entry_bid':str(bid),'btc':str(btc),'target':str(target)}
def path(t,bid,ask=None):
    return {'_t':t,'current_bid':str(bid),'current_ask':str(bid+.01 if ask is None else ask),'seconds_left':'500'}
def early_fixture():
    prices=[100,100,100,100,100,100,110,108,109,111]
    return [{'_t':i*5.,'btc_price':str(p),'seconds_left':str(650-i*5),
             'btc_move_15s':'10' if i>=6 else '0','up_ask':'.30','up_bid':'.29','down_ask':'.71','down_bid':'.70'} for i,p in enumerate(prices)]

class Invariants(unittest.TestCase):
    def test_entry_spread_in_mae_but_preentry_bid_not_mfe(self):
        m=measure(10,.30,.28,[(9,.90),(10,.90),(11,.31)])
        self.assertAlmostEqual(m['mae_c'],-2);self.assertAlmostEqual(m['mfe_c'],1);self.assertFalse(m['hit5'])
    def test_first_giveback_and_postexit_mfe_are_distinct(self):
        m=measure(0,.30,.29,[(1,.36),(2,.32),(3,.60)])
        self.assertEqual(m['exit_time'],2);self.assertAlmostEqual(m['exit_gain_c'],2)
        self.assertAlmostEqual(m['pre_exit_mfe_c'],6);self.assertAlmostEqual(m['mfe_c'],30)
    def test_cent_boundary_float_tolerance(self):
        m=measure(0,.54,.53,[(1,.59),(2,.55)])
        self.assertTrue(m['hit5']);self.assertEqual(m['exit_time'],2)
    def test_ended_unarmed_resumes_serial(self):
        cs=[candidate('a',0),candidate('b',15)]
        ps={('C','a'):[path(5,.29),path(10,.30)],('C','b'):[path(20,.30)]}
        rs={('C','a'):{'_t':10},('C','b'):{'_t':20}}
        o=build_serial(cs,ps,rs)
        self.assertEqual(len(o),2);self.assertEqual(o[0]['status'],'ENDED_UNARMED')
    def test_armed_result_never_resets(self):
        cs=[candidate('a',0),candidate('b',15)]
        o=build_serial(cs,{('C','a'):[path(5,.35),path(10,.34)]},{('C','a'):{'_t':10}})
        self.assertEqual(len(o),1);self.assertEqual(o[0]['status'],'ARMED_NO_EXIT_BLOCKING')
    def test_missing_path_never_resets(self):
        cs=[candidate('a',0),candidate('b',15)]
        o=build_serial(cs,{}, {('C','a'):{'_t':10}})
        self.assertEqual(len(o),1);self.assertEqual(o[0]['status'],'INCOMPLETE_BLOCKING')
    def test_terminal_equal_timestamp_not_reentry(self):
        cs=[candidate('a',0),candidate('b',10),candidate('c',11)]
        o=build_serial(cs,{('C','a'):[path(5,.36),path(10,.32)]},{('C','a'):{'_t':10}})
        self.assertEqual([x['candidate_id'] for x in o],['a','c'])
    def test_thirty_second_value_boundary_actual_ask(self):
        o={'candidate':candidate('a',0,.6,.59),'contract':'C','candidate_id':'a','opportunity_index':1,
           'paths':[path(29,.51,.52),path(30,.49,.50),path(35,.55,.56)],'result':{'_t':35},'status':'EXIT'}
        q=value_entry(o);self.assertEqual(q['time'],30);self.assertEqual(q['ask'],.50)
        o['paths'][1]['_t']=30.01;self.assertIsNone(value_entry(o))
    def test_target_gap_down_sign_and_price_second(self):
        c=candidate('a',0,.30,.29,'DOWN',90,100)
        o={'candidate':c,'contract':'C','candidate_id':'a','opportunity_index':1,
           'paths':[path(5,.40),path(10,.35)],'result':{'_t':10},'status':'EXIT'}
        qs,_=scalp_lane([o],True,{'C':0});self.assertEqual(qs[0]['target_gap_side'],10)
        c['btc']='110';qs,_=scalp_lane([o],True,{'C':0});self.assertEqual(qs,[])
    def test_early_requires_ordered_pullback_and_reclaim(self):
        rs=early_fixture();q=early_signals(rs)[0]
        self.assertEqual(q['time'],45);self.assertEqual(q['episode_start'],30);self.assertEqual(q['retest_time'],35)
        rs[7]['btc_price']='112';rs[8]['btc_price']='113';rs[9]['btc_price']='114'
        self.assertEqual(early_signals(rs),[])
    def test_early_rejects_broken_support_or_repriced_ask(self):
        rs=early_fixture();rs[7]['btc_price']='99';self.assertEqual(early_signals(rs),[])
        rs=early_fixture();rs[-1]['up_ask']='.33';self.assertEqual(early_signals(rs),[])
    def test_early_signal_is_prefix_causal(self):
        rs=early_fixture();q=early_signals(rs)
        extra=deepcopy(rs[-1]);extra['_t']=50;extra['btc_price']='1';extra['future_gain']='999'
        self.assertEqual(early_signals(rs+[extra]),q)
    def test_data_gap_prevents_continuity_and_retest(self):
        self.assertFalse(continuous(0,[(5,.3),(20,.4)],20))
        rs=early_fixture();rs[-1]['_t']=70;self.assertEqual(early_signals(rs),[])
    def test_unallowlisted_data_denied(self):
        with self.assertRaises(AssertionError):read_source(None,'clean.csv')

if __name__=='__main__':unittest.main()
