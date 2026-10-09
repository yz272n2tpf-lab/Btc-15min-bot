"""Focused live-entry regression coverage; deterministic offline checks only."""
from copy import deepcopy
import json,tempfile,unittest
from pathlib import Path
from test_btc15_scalp_journal_v1 import state,ENTRY
from test_btc15_trade_clarity import schedule,scalp_origin
from btc15_v2_product.scalp import Scalp
from btc15_v2_product.scalp_economics import entry_assessment
from btc15_ladder_journal_v1 import Journal,packed


def frame(at=ENTRY,ask=.60,side='UP',seq=1,spread=.01):
    f=state(at,ask-spread,seq,side);row=f['row'];p=row['input_provenance'];q=p['quote']
    k=side.lower();other='down' if side=='UP' else 'up'
    q.update({k+'_ask':ask,k+'_bid':ask-spread,other+'_bid':1-ask,other+'_ask':1-ask+spread})
    row.update({k:q[k] for k in ('up_bid','up_ask','down_bid','down_ask')})
    for proposal in f['proposals'].values():
        h=proposal['history']['30'];h['btc']=row['btc']+(-20 if side=='UP' else 20)
        h['input_provenance']['quote'].update({key:q[key] for key in ('up_bid','up_ask','down_bid','down_ask')})
    f['fee_schedule']=schedule(at)
    return f


class RestoredEntry(unittest.TestCase):
    def test_qualified_up_down_and_low_high_prices_reach_real_processor_buy(self):
        for side in ('UP','DOWN'):
            for ask in (.03,.40,.60,.80,.90):
                with self.subTest(side=side,ask=ask):
                    f=frame(ask=ask,side=side);e=Scalp();e.restore({})
                    r,s,v=e.process(f,ENTRY+.001);o=v['origin'];a=o['qualification']
                    self.assertEqual(r['event'],'SCALP_SIGNAL');self.assertEqual(v['guidance'],'ENTER')
                    self.assertEqual(o['side'],side);self.assertEqual(o['original_ask'],ask)
                    self.assertTrue(a['ready']);self.assertIsNone(a['projected_exit_bid']);self.assertIsNone(a['projected_net'])
                    self.assertIsNone(a['expected_profit']);self.assertIsNone(a['price_ceiling'])
                    self.assertTrue(v['trade_clarity']['entry_authority_current'])
                    self.assertEqual(v['trade_clarity']['records'][-1]['entry_risk'],a['entry_room'])
                    self.assertLess(len(packed(v)),65536)

    def test_cost_room_and_fee_blocks_are_conditional(self):
        cases=[('high_price',lambda f:f.update(frame(ask=.98))),
               ('wide_spread',lambda f:f.update(frame(ask=.8,spread=.25))),
               ('missing_fees',lambda f:f.update(fee_schedule=None)),
               ('old_fees',lambda f:f['fee_schedule'].update(observed_ts=ENTRY-121)),
               ('weak_momentum',lambda f:f['proposals']['UP']['history']['30'].update(btc=f['row']['btc']-2)),
               ('absent_history',lambda f:f['proposals']['UP'].update(history={}))]
        for name,mutate in cases:
            f=frame();mutate(f);e=Scalp();e.restore({});r,_,v=e.process(f,ENTRY+.001)
            self.assertNotIn('event',r,name);self.assertIsNone(v.get('origin'),name)

    def test_same_side_market_opposition_and_observation_not_forecast(self):
        for side in ('UP','DOWN'):
            f=frame(side=side);h=f['proposals'][side]['history'];q=h['30']['input_provenance']['quote'];k=side.lower()
            q[k+'_bid']+=.10;q[k+'_ask']+=.10
            a=entry_assessment(f['row'],side,f['fee_schedule'],h)
            self.assertFalse(a['ready']);self.assertEqual(a['reason'],'KALSHI_BID_OPPOSES_MOMENTUM')
            self.assertLess(a['entry_room']['observed_bid_change_30s'],0)
            q[k+'_bid']-=.20;q[k+'_ask']-=.20
            a=entry_assessment(f['row'],side,f['fee_schedule'],h)
            self.assertTrue(a['ready']);self.assertIsNone(a['projected_net'])

    def test_genuine_native_source_and_time_checks_still_apply(self):
        for mutate in (lambda f:f['row']['input_provenance']['quote'].update(ticker='OTHER'),
                       lambda f:f['row']['input_provenance']['brti'].update(source_ts_ms=int((ENTRY-6)*1000)),
                       lambda f:f['row']['input_provenance']['quote'].update(source_ts_ms=int((ENTRY-9)*1000))):
            f=frame();mutate(f);e=Scalp();e.restore({});r,_,v=e.process(f,ENTRY+.001)
            self.assertNotIn('event',r);self.assertEqual(v['status'],'UNAVAILABLE')
        f=frame(at=ENTRY+481);e=Scalp();e.restore({});r,_,v=e.process(f,ENTRY+481.001)
        self.assertNotIn('event',r);self.assertIsNone(v['origin'])

    def test_serial_reentry_reversal_restart_and_origin_binding(self):
        for side in ('UP','DOWN'):
            e=Scalp();e.restore({});r,_,v=e.process(frame(),ENTRY+.001);o=deepcopy(v['origin'])
            _,saved,v=e.process(frame(ENTRY+1,ask=.71,seq=2),ENTRY+1.001)
            self.assertEqual(v['guidance'],'PROTECT');self.assertEqual(v['origin'],o)
            e=Scalp();e.restore(saved)
            r,_,v=e.process(frame(ENTRY+2,ask=.62,seq=3),ENTRY+2.001)
            self.assertEqual(r['event'],'SCALP_EXIT');self.assertEqual(v['terminal']['exit_class'],'DEFENSIVE_RISK_EXIT')
            self.assertFalse(v['terminal']['economics']['meaningful_positive_net'])
            r,_,v=e.process(frame(ENTRY+3,side=side,seq=4),ENTRY+3.001)
            self.assertEqual(r['event'],'SCALP_SIGNAL');self.assertEqual(v['origin']['serial_index'],2)
            self.assertEqual(v['origin']['predecessor_id'],o['origin_id']);self.assertNotEqual(v['origin']['origin_id'],o['origin_id'])
            self.assertEqual(v['origin']['lane'],'REENTRY_CONTINUATION' if side=='UP' else 'REVERSAL_RECROSS')
            self.assertEqual(len(v['trade_clarity']['records']),2)
            self.assertEqual(v['trade_clarity']['records'][0]['terminal']['state'],'EXIT')

    def test_quiet_predecessor_keeps_history_without_recent_buy(self):
        from btc15_v2_product.early_origin_transfer import PREDECESSORS,transfer
        from btc15_v2_product import REVISION
        e,o=scalp_origin();saved=e.checkpoint();saved['origin']=None;saved['engine']=None;saved['path']={}
        dep,build=PREDECESSORS['v81']
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/dep/'v81.sqlite3';j=Journal(p,'v81')
            for k,v in dict(product_revision=REVISION,deployment=dep,build=build).items():j.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',(k,v))
            j.db.commit();j.commit(dict(kind='SCALP_OBSERVATION',published_ts=ENTRY+901,contract=o['contract']),saved);j.close()
            before=p.read_bytes();dest=Path(d)/'new'/'v81.sqlite3';j=Journal(dest,'v81');transfer(j,dest,ENTRY+902)
            self.assertIsNone(j.get('state')['origin']);self.assertEqual(j.get('state')['signal_history'][0]['origin_id'],o['origin_id'])
            self.assertFalse(j.get('origin_transfer')['publication_imported']);j.close();self.assertEqual(before,p.read_bytes())

    def test_eight_serial_records_fit_existing_publication_limit(self):
        e=Scalp();e.restore({})
        for i in range(9):
            at=ENTRY+i*3;seq=i*3+1
            r,_,v=e.process(frame(at,seq=seq),at+.001)
            self.assertEqual(r['event'],'SCALP_SIGNAL')
            e.process(frame(at+1,ask=.71,seq=seq+1),at+1.001)
            r,_,v=e.process(frame(at+2,ask=.62,seq=seq+2),at+2.001)
            self.assertEqual(r['event'],'SCALP_EXIT');self.assertLess(len(packed(v)),65536)
        self.assertEqual(len(v['trade_clarity']['records']),8)

if __name__=='__main__':unittest.main()
