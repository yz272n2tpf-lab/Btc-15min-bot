from copy import deepcopy
import unittest
from btc15_scalp_journal_v1 import Scalp

OPEN=1791057600.
ENTRY=OPEN+300

def state(at=ENTRY,bid=.34,seq=1,side='UP'):
    q=dict(transport='timestamped_contiguous_ws',ticker='KXBTC15M-26OCT031615-15',epoch='q',
        market_id='m',sid=1,sequence=seq,source_ts_ms=int((at-.01)*1000),validated_at_ms=int(at*1000),
        up_bid=bid,up_ask=max(.35,round(bid+.01,4)),down_bid=1-max(.35,round(bid+.01,4)),down_ask=1-bid)
    if side=='DOWN':
        q.update(down_bid=bid,down_ask=max(.35,round(bid+.01,4)),up_bid=1-max(.35,round(bid+.01,4)),up_ask=1-bid)
    p=dict(schema='V81_TIMESTAMPED_INPUTS_V1',signal_only=True,orders=False,
        open_ts=OPEN,close_ts=OPEN+900,ticker=q['ticker'],target=80000.,quote=q,
        brti=dict(status='PRIMARY_OK',clean_for_qualification=True,owner_epoch='b',source_ts_ms=int((at-.1)*1000),value=80001.))
    ep=deepcopy(p)
    if at!=ENTRY:ep=state(side=side)['input_provenance']
    return dict(contract=q['ticker'],active=True,status='WATCH',primary_wait_reason='ACTIVE_SIGNAL',input_provenance=p,
        last_signal_event=dict(contract=q['ticker'],side=side,route='CORE',entry_price=.35,signal_ts=ENTRY,entry_provenance=ep))


class ScalpTests(unittest.TestCase):
    def setUp(self):
        self.s=Scalp();self.s.restore({})

    def test_entry_quote_not_later_bid(self):
        r,_,v=self.s.process(state(),ENTRY+.01)
        self.assertEqual(r['event'],'SCALP_SIGNAL');self.assertEqual(v['path']['samples'],0)
        self.assertEqual(v['origin']['original_ask'],.35)

    def test_target_stop_order_down_and_up(self):
        for side in ['UP','DOWN']:
            with self.subTest(side=side):
                self.setUp();self.s.process(state(side=side),ENTRY+.01)
                self.s.process(state(ENTRY+2,.24,2,side),ENTRY+2.01)
                r,_,v=self.s.process(state(ENTRY+3,.66,3,side),ENTRY+3.01)
                self.assertTrue(v['path']['targets']['30']['stop_first'])
                self.assertAlmostEqual(v['path']['mfe'],.31);self.assertAlmostEqual(v['path']['mae'],-.11)
                self.assertEqual(v['origin']['original_ask'],.35)
                self.assertFalse(v['path']['missing'])

    def test_target_then_stop(self):
        self.s.process(state(),ENTRY+.01)
        self.s.process(state(ENTRY+2,.46,2),ENTRY+2.01)
        _,_,v=self.s.process(state(ENTRY+3,.24,3),ENTRY+3.01)
        self.assertFalse(v['path']['targets']['10']['stop_first'])

    def test_repeated_quote_not_sample(self):
        self.s.process(state(),ENTRY+.01)
        s=state(ENTRY+2,.46,2);self.s.process(s,ENTRY+2.01)
        _,_,v=self.s.process(s,ENTRY+2.1)
        self.assertEqual(v['path']['samples'],1)

    def test_missing_and_gap_explicit(self):
        self.s.process(state(),ENTRY+.01)
        self.s.process(state(ENTRY+1,.38,2),ENTRY+1.01)
        _,_,v=self.s.process(state(ENTRY+20,.45,3),ENTRY+20.01)
        self.assertTrue(v['path']['missing'])

    def test_stale_provenance_no_bid(self):
        self.s.process(state(),ENTRY+.01)
        r,_,v=self.s.process(state(ENTRY+1,.66,2),ENTRY+9)
        self.assertEqual(v['status'],'UNAVAILABLE');self.assertNotIn('later_bid',r)

    def test_immutable_original_and_restart(self):
        _,saved,original=self.s.process(state(),ENTRY+.01)
        self.s=Scalp();self.s.restore(saved)
        r,_,v=self.s.process(state(ENTRY+2,.46,2),ENTRY+2.01)
        self.assertEqual(v['origin'],original['origin']);self.assertNotIn('event',r)
        broken=state(ENTRY+3,.47,3);broken['last_signal_event']['entry_price']=.40
        _,_,v=self.s.process(broken,ENTRY+3.01)
        self.assertEqual(v['status'],'UNAVAILABLE')

    def test_terminal_not_backdated_fill(self):
        self.s.process(state(),ENTRY+.01)
        s=state(ENTRY+181,.8,9);s['active']=False
        r,_,v=self.s.process(s,ENTRY+181.01)
        self.assertEqual(r['terminal']['status'],'HORIZON');self.assertIsNone(r['terminal']['executable_exit'])
        self.assertEqual(v['status'],'PASS')

if __name__=='__main__':unittest.main()
