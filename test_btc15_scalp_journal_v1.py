from copy import deepcopy
from datetime import datetime,timezone
import unittest
from btc15_scalp_journal_v1 import Scalp

OPEN=1791057600.
ENTRY=OPEN+300
TICKER='KXBTC15M-26OCT031615-15'


def state(at=ENTRY,bid=.34,seq=1,side='UP',eligible=True):
    q=dict(transport='timestamped_contiguous_ws',ticker=TICKER,epoch='q',
        market_id='m',sid=1,sequence=seq,source_ts_ms=int((at-.01)*1000),validated_at_ms=int(at*1000),
        up_bid=bid,up_ask=max(.35,round(bid+.01,4)),down_bid=1-max(.35,round(bid+.01,4)),down_ask=1-bid)
    if side=='DOWN':
        q.update(down_bid=bid,down_ask=max(.35,round(bid+.01,4)),up_bid=1-max(.35,round(bid+.01,4)),up_ask=1-bid)
    p=dict(schema='V81_TIMESTAMPED_INPUTS_V1',signal_only=True,orders=False,
        open_ts=OPEN,close_ts=OPEN+900,ticker=TICKER,target=80000.,quote=q,
        btc_source_utc=datetime.fromtimestamp(at-.1,timezone.utc).isoformat(),
        brti=dict(status='PRIMARY_OK',clean_for_qualification=True,owner_epoch='b',source_ts_ms=int((at-.1)*1000),value=80001.))
    row=dict(q,ts=at,left=OPEN+900-at,target=80000.,btc=80002.,brti=80001.,input_provenance=p)
    history={}
    for seconds in (5,15,30):
        h=deepcopy(p);h['quote']['source_ts_ms']=int((at-seconds-.01)*1000);h['quote']['validated_at_ms']=int((at-seconds)*1000)
        h['brti']['source_ts_ms']=int((at-seconds-.1)*1000)
        h['btc_source_utc']=datetime.fromtimestamp(at-seconds-.1,timezone.utc).isoformat()
        history[str(seconds)]=dict(observed_ts=at-seconds,btc=80000.,input_provenance=h)
    proposals={s:dict(ok=eligible and s==side and q[s.lower()+'_ask']<=.45,route='CORE',features={'btc5':20.},history=history) for s in ('UP','DOWN')}
    return dict(kind='SCALP_DECISION',contract=TICKER,row=row,captured_ts=at,proposals=proposals,diagnostics=[])


class ScalpTests(unittest.TestCase):
    def setUp(self):self.s=Scalp();self.s.restore({})
    def step(self,at=ENTRY,bid=.34,seq=1,side='UP',eligible=True):
        return self.s.process(state(at,bid,seq,side,eligible),at+.001)
    def enter(self,side='UP'):
        self.step(ENTRY-1,seq=1,side=side)
        return self.step(seq=2,side=side)

    def test_two_fresh_confirmations_entry_not_later_bid(self):
        _,_,v=self.step(ENTRY-1);self.assertEqual(v['guidance'],'PASS')
        r,_,v=self.step(seq=2)
        self.assertEqual(r['event'],'SCALP_SIGNAL');self.assertEqual(v['guidance'],'ENTER')
        self.assertEqual(v['path']['samples'],0);self.assertEqual(v['origin']['original_ask'],.35)

    def test_repeated_quote_cannot_confirm(self):
        self.step(ENTRY-1)
        f=state();f['row']['input_provenance']['quote'].update(sequence=1,source_ts_ms=int((ENTRY-1.01)*1000))
        _,_,v=self.s.process(f,ENTRY+.001);self.assertEqual(v['guidance'],'PASS')

    def test_arm_pullback_latched_exit_actual_bid_both_sides(self):
        for side in ('UP','DOWN'):
            with self.subTest(side=side):
                self.setUp();_,_,entry=self.enter(side)
                _,_,v=self.step(ENTRY+1,.72,3,side);self.assertEqual(v['guidance'],'PROTECT')
                self.assertAlmostEqual(v['trailing_trigger_bid'],.68)
                _,_,v=self.step(ENTRY+2,.70,4,side);self.assertEqual(v['guidance'],'PROTECT')
                r,saved,v=self.step(ENTRY+3,.68,5,side)
                self.assertEqual(r['event'],'SCALP_EXIT');self.assertEqual(v['guidance'],'EXIT')
                terminal=deepcopy(v['terminal']);self.assertEqual(terminal['executable_exit_bid'],.68)
                self.assertEqual(v['origin'],entry['origin'])
                self.s=Scalp();self.s.restore(saved)
                _,_,v=self.step(ENTRY+4,.80,6,side)
                self.assertEqual(v['guidance'],'EXIT');self.assertEqual(v['terminal'],terminal)
                self.assertEqual(v['exit_guidance']['current_executable_bid'],.80)
                self.assertEqual(v['path']['mfe'],.37)

    def test_gap_overshoot_never_fill_at_trailing_floor(self):
        self.enter();self.step(ENTRY+1,.45,3)
        _,_,v=self.step(ENTRY+20,.24,4)
        self.assertEqual(v['guidance'],'EXIT');self.assertEqual(v['terminal']['executable_exit_bid'],.24)
        self.assertTrue(v['path']['missing']);self.assertFalse(v['terminal']['complete_path'])

    def test_targets_stop_and_time_are_observational(self):
        self.enter();self.step(ENTRY+1,.24,3)
        _,_,v=self.step(ENTRY+2,.66,4)
        self.assertTrue(v['path']['targets']['30']['stop_first']);self.assertEqual(v['guidance'],'PROTECT')
        self.assertAlmostEqual(v['path']['mae'],-.11)
        self.assertGreater(v['path']['stop']['seconds_since_signal'],0)
        self.assertEqual(v['target_stop_authority'],'OBSERVATIONAL_ONLY')

    def test_target_then_stop_terminal_not_settlement(self):
        self.enter();self.step(ENTRY+1,.46,3)
        _,_,v=self.step(ENTRY+2,.24,4)
        self.assertFalse(v['path']['targets']['10']['stop_first'])
        self.assertIn('10',v['path']['stop']['targets_first'])
        self.assertEqual(v['guidance'],'EXIT');self.assertIsNone(v['terminal']['realized_profit'])

    def test_horizon_uses_current_bid_and_actual_delay(self):
        self.enter();r,_,v=self.step(ENTRY+181,.33,3)
        self.assertEqual(v['guidance'],'EXIT');self.assertEqual(r['terminal']['reason'],'HORIZON_180S')
        self.assertEqual(v['terminal']['executable_exit_bid'],.33)
        self.assertAlmostEqual(v['terminal']['horizon_delay_seconds'],1.)

    def test_stale_horizon_does_not_exit_or_release(self):
        self.enter();f=state(ENTRY+181,.33,3)
        _,_,v=self.s.process(f,ENTRY+187)
        self.assertEqual(v['guidance'],'UNAVAILABLE');self.assertIsNone(self.s.terminal)
        _,_,v=self.step(ENTRY+188,.34,4);self.assertEqual(v['guidance'],'EXIT')

    def test_serial_reentry_and_reversal_need_exit_then_two_new_observations(self):
        for side,lane in [('UP','REENTRY_CONTINUATION'),('DOWN','REVERSAL_RECROSS')]:
            with self.subTest(side=side):
                self.setUp();_,_,entry=self.enter();self.step(ENTRY+1,.45,3)
                _,_,v=self.step(ENTRY+2,.40,4)
                self.assertEqual(v['guidance'],'EXIT')
                _,_,v=self.step(ENTRY+21,.34,5,side);self.assertEqual(v['guidance'],'EXIT')
                r,_,v=self.step(ENTRY+22,.34,6,side)
                self.assertEqual(v['guidance'],'ENTER');self.assertEqual(v['origin']['lane'],lane)
                self.assertEqual(v['origin']['predecessor_id'],entry['origin']['origin_id'])
                self.assertGreater(v['origin']['signal_ts'],v['origin']['predecessor_exit_ts'])
                self.assertEqual(r['predecessor_exit']['reason'],'ARM5_GIVEBACK4')

    def test_active_origin_cannot_be_replaced_by_opposite_setup(self):
        _,_,e=self.enter();_,_,v=self.step(ENTRY+21,.34,3,'DOWN')
        self.assertEqual(v['origin'],e['origin']);self.assertNotEqual(v['guidance'],'ENTER')

    def test_caution_and_watch_have_no_exit_authority(self):
        self.enter();f=state(ENTRY+1,.36,3);f['row']['btc']=79999
        _,_,v=self.s.process(f,ENTRY+1.001)
        self.assertEqual(v['guidance'],'WATCH');self.assertFalse(v['context']['exit_authority'])
        self.setUp();f=state(OPEN+719,seq=1);self.s.process(f,OPEN+719.001)
        f=state(OPEN+720,seq=2);self.s.process(f,OPEN+720.001)
        _,_,v=self.step(OPEN+721,.36,3)
        self.assertEqual(v['guidance'],'CAUTION');self.assertEqual(v['context']['phase'],'3M_GUARD')

    def test_source_adversaries_preserve_origin_unavailable(self):
        cases=[lambda f:f['row']['input_provenance']['brti'].update(source_ts_ms=int((ENTRY-6)*1000)),
            lambda f:f['row']['input_provenance']['quote'].update(ticker='OTHER'),
            lambda f:f['row'].update(ts=ENTRY+10),
            lambda f:f['row']['input_provenance'].update(btc_source_utc=datetime.fromtimestamp(ENTRY+10,timezone.utc).isoformat()),
            lambda f:f['row']['input_provenance']['quote'].update(source_ts_ms=int((ENTRY+10)*1000)),
            lambda f:f['row'].update(up_bid=.99),
            lambda f:f['row']['input_provenance'].update(target=1)]
        for mutate in cases:
            with self.subTest(mutate=mutate):
                self.setUp();_,_,e=self.enter();f=state(ENTRY+1,.7,3);mutate(f)
                r,_,v=self.s.process(f,ENTRY+1.001)
                self.assertEqual(v['guidance'],'UNAVAILABLE');self.assertEqual(v['origin'],e['origin']);self.assertNotIn('later_bid',r)

    def test_outage_clears_half_confirmation(self):
        self.step(ENTRY-1)
        self.s.process(dict(kind='UNAVAILABLE',reason='GAP'),ENTRY-.5)
        _,_,v=self.step(seq=2);self.assertEqual(v['guidance'],'PASS')

    def test_wrong_candidate_checkpoint_rejected(self):
        with self.assertRaises(ValueError):self.s.restore({'candidate':'OLD'})

if __name__=='__main__':unittest.main()
