"""Focused reported-failure regressions. Offline fixtures; no shadow workloads."""
from copy import deepcopy
import ast,json,tempfile,unittest
from pathlib import Path
from test_btc15_supported_early import value_frame,step
from test_btc15_scalp_journal_v1 import state,ENTRY
from btc15_v2_product.directional import Directional
from btc15_v2_product.scalp import Scalp,CANDIDATE,POLICY
from btc15_v2_product.scalp_economics import liquidation,entry_assessment
from btc15_v2_product.trade_clarity import historical
from btc15_ladder_journal_v1 import digest,packed,Journal


def schedule(at):return dict(series='KXBTC15M',fee_type='quadratic',multiplier=1,observed_ts=at-1)


def scalp_origin(side='UP',fees=True):
    f=state(ENTRY,.59,1,side);p=f['row']['input_provenance'];q=p['quote'];at=ENTRY+.001
    o=dict(origin_id=digest([CANDIDATE,p['ticker'],side,at,q['epoch'],q['sequence']]),contract=p['ticker'],
        side=side,signal_ts=at,decision_ts=ENTRY,original_ask=q[side.lower()+'_ask'],entry_provenance=p,
        entry_features={'btc30':20},route='GENERALIZED',target=p['target'],open_ts=p['open_ts'],close_ts=p['close_ts'],
        deadline=at+POLICY.horizon,serial_index=1,predecessor_id=None,lane='FIRST',manual_fill=None)
    if fees:o['fee_schedule']=schedule(ENTRY)
    saved=dict(candidate=CANDIDATE,origin=o,contract=p['ticker'],closed=p['close_ts'],index=1,
        path=dict(mfe=None,mae=None,samples=0,missing=False,last_quote=None,targets={str(t):None for t in (8,10,15,20,30)},stop=None,giveback=None,current=None))
    e=Scalp();e.restore(saved);return e,o


class Clarity(unittest.TestCase):
    def test_buy_is_durable_event_not_renewed_entry(self):
        e=Directional();e.restore({});r,s,v=step(e,value_frame());o=v['origin'];c=v['trade_clarity']
        self.assertTrue(c['entry_authority_current']);self.assertEqual(c['records'][0]['original_ask'],.53)
        _,_,v=step(e,value_frame(2));self.assertEqual(v['trade_clarity']['display_state'],'EXISTING SIGNAL UNDER MANAGEMENT')
        self.assertFalse(v['trade_clarity']['entry_authority_current']);self.assertEqual(v['origin'],o)
        _,_,v=e.process(dict(kind='UNAVAILABLE',contract=o['contract'],reason='SOURCE_WAIT'),value_frame(3)['captured_ts'])
        self.assertEqual(v['trade_clarity']['records'][0]['side'],o['side']);self.assertIsNone(v['trade_clarity']['current_bid'])
        self.assertFalse(v['trade_clarity']['entry_authority_current'])

    def test_exit_is_completed_not_new_entry_and_direction_does_not_flip(self):
        e=Directional();e.restore({});_,_,v=step(e,value_frame());oid=v['origin']['origin_id']
        _,saved,v=step(e,value_frame(2,side='DOWN',p=.6))
        self.assertEqual(v['trade_clarity']['display_state'],'COMPLETED EXIT — NO NEW ENTRY')
        r=v['trade_clarity']['records'][-1];self.assertEqual(r['side'],'UP');self.assertEqual(r['origin_id'],oid)
        self.assertEqual(r['terminal']['observed_bid'],v['terminal']['executable_exit_bid'])
        self.assertIsNone(v['trade_clarity']['current_bid']);self.assertFalse(v['trade_clarity']['entry_authority_current'])
        e=Directional();e.restore(saved);_,_,v=step(e,value_frame(3))
        self.assertEqual(v['trade_clarity']['records'][-1]['terminal'],r['terminal'])

    def test_public_failure_retains_identity_only(self):
        e=Directional();e.restore({});_,_,v=step(e,value_frame());h=historical(v['trade_clarity'])
        self.assertIsNone(h['economics']);self.assertFalse(h['entry_authority_current']);self.assertIsNone(h['current_bid'])
        self.assertTrue(h['records'][-1]['issued_buy']);self.assertFalse(h['records'][-1]['current_action_authority'])

    def test_protected_prediction_and_final_gates_unchanged(self):
        def funcs(path):return {x.name:ast.dump(x,include_attributes=False) for x in ast.parse(Path(path).read_text()).body if isinstance(x,ast.FunctionDef)}
        a=funcs('btc15_ladder_product_v1.py');b=funcs('btc15_v2_product/directional.py')
        for n in ('qualify','protected_frame','native_frame'):self.assertEqual(a[n],b[n])

    def test_tiny_gross_and_net_not_profit_protection(self):
        s=schedule(ENTRY)
        for gain in (.01,.02,.05,.06):
            e=liquidation(.6,.6+gain,.61+gain,s,ENTRY,s,ENTRY)
            self.assertFalse(e['meaningful_positive_net'],gain)
        self.assertTrue(liquidation(.6,.69,.70,s,ENTRY,s,ENTRY)['meaningful_positive_net'])
        self.assertFalse(liquidation(.6,.8,.81,None,ENTRY,s,ENTRY)['meaningful_positive_net'])
        self.assertFalse(liquidation(.6,.8,.81,s,ENTRY,None,None)['meaningful_positive_net'])

    def test_missing_native_momentum_does_not_buy_even_with_cost_room(self):
        f=state(ENTRY,.4);f['fee_schedule']=schedule(ENTRY)
        a=entry_assessment(f['row'],'UP',f['fee_schedule'],f['proposals']['UP']['history'],management_arm=.05)
        self.assertIsNone(a['price_ceiling']);self.assertFalse(a['ready'])
        e=Scalp();e.restore({});r,_,v=e.process(f,ENTRY+.001)
        self.assertNotIn('event',r);self.assertIsNone(v['origin'])

    def test_defensive_exit_with_one_cent_gross_and_with_loss(self):
        for side in ('UP','DOWN'):
            for bid in (.61,.4):
                e,o=scalp_origin(side)
                f=state(ENTRY+1,.65,2,side);f['fee_schedule']=schedule(ENTRY+1)
                _,_,v=e.process(f,ENTRY+1.001)
                self.assertEqual(v['guidance'],'PROTECT');self.assertFalse(v['presentation']['profit_protection_qualified'])
                f=state(ENTRY+2,bid,3,side);f['fee_schedule']=schedule(ENTRY+2)
                r,saved,v=e.process(f,ENTRY+2.001)
                self.assertEqual(r['event'],'SCALP_EXIT');self.assertEqual(v['terminal']['exit_class'],'DEFENSIVE_RISK_EXIT')
                self.assertEqual(v['terminal']['executable_exit_bid'],bid)
                self.assertEqual(v['trade_clarity']['display_state'],'COMPLETED EXIT — NO NEW ENTRY')
                self.assertEqual(v['origin'],o);self.assertIsNone(v['terminal']['realized_profit'])
                restored=Scalp();restored.restore(saved);self.assertEqual(restored.origin,o)

    def test_legacy_missing_fees_does_not_suppress_risk_exit(self):
        e,o=scalp_origin(fees=False)
        e.process(state(ENTRY+1,.7,2),ENTRY+1.001)
        r,_,v=e.process(state(ENTRY+2,.4,3),ENTRY+2.001)
        self.assertEqual(r['event'],'SCALP_EXIT');self.assertIsNone(v['terminal']['economics']['net_liquidation_scenario'])

    def test_checkpoint_conflict_rejected(self):
        e,o=scalp_origin();s=e.checkpoint();s['origin']['side']='DOWN'
        with self.assertRaises(ValueError):Scalp().restore(s)

    def test_rollover_preserves_historical_origin_but_no_authority(self):
        e,o=scalp_origin();f=state(ENTRY+901,.5,2)
        p=f['row']['input_provenance'];p['open_ts']+=900;p['close_ts']+=900
        ticker='KXBTC15M-26OCT031630-30'
        f['contract']=f['row']['ticker']=p['ticker']=p['quote']['ticker']=ticker
        r,s,v=e.process(f,ENTRY+901.001)
        self.assertEqual(v['status'],'PASS');self.assertIsNone(v['origin'])
        self.assertEqual(v['trade_clarity']['records'][-1]['origin_id'],o['origin_id'])
        self.assertEqual(v['trade_clarity']['display_state'],'LAST ISSUED SIGNAL — HISTORICAL')
        self.assertFalse(v['trade_clarity']['entry_authority_current']);self.assertLess(len(packed(v)),65536)

    def test_scalp_transfer_real_journal_is_read_only(self):
        from btc15_v2_product.early_origin_transfer import PREDECESSORS,transfer
        from btc15_v2_product import REVISION
        e,o=scalp_origin();dep,build=PREDECESSORS['v81']
        with tempfile.TemporaryDirectory() as d:
            prior=Path(d)/dep/'v81.sqlite3';j=Journal(prior,'v81')
            for k,v in dict(product_revision=REVISION,deployment=dep,build=build).items():j.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',(k,v))
            j.db.commit();j.commit(dict(kind='SCALP_OBSERVATION',published_ts=ENTRY+.001,event='SCALP_SIGNAL',contract=o['contract'],origin_id=o['origin_id'],origin=o),e.checkpoint());j.close()
            before=prior.read_bytes();dest=Path(d)/'new'/'v81.sqlite3';j=Journal(dest,'v81');transfer(j,dest,ENTRY+1)
            self.assertEqual(j.get('state')['origin'],o);self.assertIsNone(j.get('handoff_view'))
            self.assertFalse(j.get('origin_transfer')['publication_imported']);j.close();self.assertEqual(before,prior.read_bytes())

if __name__=='__main__':unittest.main()
