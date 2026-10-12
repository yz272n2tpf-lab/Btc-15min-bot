"""Synthetic mechanisms only. Fixture support NEVER supplies historical economics."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import unittest
from candidates.early_condition_20261011.test_engine import row
from candidates.early_value_20261011.engine import CoreEngine
from candidates.early_value_20261011.qualification import features as old_features
from .engine import Engine
from .assessment import Rules,SAFETY,assess,price_group


def fixture(t,side='UP',delta=None,ask=.45,**kw):
    return row(t,side,delta=delta,bid=ask-.01,**kw)

def warm(e=None,side='UP',pre=False,ask=.45,end=60):
    e=e or Engine()
    for t in range(0,end+1,5):e.process(fixture(t,side,delta=-300+.5*t if pre else None,ask=ask))
    return e

def manual(e,now=70):
    for t in range(int(e.last['time'])+5,now+1,5):e.process(fixture(t))
    t=e.current_ticket
    return e.confirm_entry(dict(id='manual-'+str(now),ticket_id=t['id'],contract=t['contract'],side=t['side'],
                   price=t['current_ask'],quantity=1,observed_at=now),now)

class RebuildMechanics(unittest.TestCase):
    def test_independent_both_sides_from_same_snapshot(self):
        e=warm(pre=True)
        r=fixture(65,delta=-267.5,p=.90);r['side']='DOWN' # settlement favors DOWN; momentum UP
        out=e.process(r);a={z['side']:z for z in out['entry']}
        self.assertTrue(a['UP']['recognized']);self.assertFalse(a['DOWN']['recognized'])
        self.assertAlmostEqual(a['UP']['settlement_probability'],.10)
        self.assertEqual(a['UP']['features']['context'],'PRE_CROSSING')
        self.assertFalse(out['research_qualified']);self.assertEqual(len(e.managers),0)

    def test_reflected_up_down_and_contexts(self):
        for pre in (True,False):
            a=warm(side='UP',pre=pre);b=warm(side='DOWN',pre=pre)
            xa=a.last_assessments['UP'];xb=b.last_assessments['DOWN']
            self.assertEqual({k:v for k,v in xa['features'].items() if not k.startswith('structure_')},
                             {k:v for k,v in xb['features'].items() if not k.startswith('structure_')})
            self.assertEqual(xa['features']['structure_btc']-100000,xb['features']['structure_btc']+100000)
            self.assertEqual(xa['recognition_blockers'],xb['recognition_blockers'])

    def test_cheap_weak_cannot_recognize_or_buy(self):
        e=Engine(permit_synthetic_support=True)
        for t in range(0,181,5):e.process(fixture(t,delta=1,ask=.10))
        self.assertFalse(e.last_assessments['UP']['recognized']);self.assertEqual(e.tickets,[])
        self.assertIn('SUB25_STRONGER_DIRECTIONAL_EVIDENCE_MISSING',e.last_assessments['UP']['execution_blockers'])

    def test_missing_economics_and_source_reasons_visible(self):
        e=warm();a=e.last_assessments['UP']
        self.assertTrue(a['recognized']);self.assertFalse(a['economics']['ready'])
        self.assertIn('NO_SUPPORTED_CONDITIONAL_RESALE_ESTIMATE',a['authorization_blockers'])
        self.assertIn('AUTHORITATIVE_CLOSE_BINDING_MISSING',a['source_blockers'])
        self.assertIsNone(a['economics']['expected_net_cents']);self.assertFalse(e.tickets)

    def test_fixture_switch_cannot_authorize_retained_rows(self):
        e=Engine(permit_synthetic_support=True)
        for t in range(0,81,5):
            r=fixture(t);r['evidence_class']='OBSERVATION_NO_NATIVE_RECEIPT';e.process(r)
        self.assertFalse(e.tickets)

    def test_price_bands_and_exception_support(self):
        self.assertEqual([price_group(v) for v in (.01,.25,.55,.56,.58,.59)],
                         ['SUB25','PRIMARY','PRIMARY','EXCEPTION56_58','EXCEPTION56_58','ABOVE58'])
        for ask in (.20,.56,.58):
            e=warm(ask=ask,end=180);a=e.last_assessments['UP']
            self.assertTrue(a['recognized']);self.assertFalse(e.tickets)
            self.assertTrue(any('SEPARATE_' in v for v in a['economics']['reasons']))
        e=warm(Engine(permit_synthetic_support=True),ask=.59)
        self.assertFalse(e.tickets)

    def test_sub25_requires_stronger_path_no_min_price_floor(self):
        e=warm(Engine(permit_synthetic_support=True),ask=.20,end=180)
        self.assertTrue(e.current_ticket);self.assertTrue(e.last_assessments['UP']['features']['strong_sub25'])
        e=warm(Engine(permit_synthetic_support=True),ask=.20,end=60)
        self.assertFalse(e.tickets)

    def test_proposal_has_no_origin_or_fill(self):
        e=warm(Engine(permit_synthetic_support=True))
        self.assertTrue(e.current_ticket);self.assertEqual(e.managers,[])
        self.assertIsNone(e.last_output['manual_fill']);self.assertIsNone(e.last_output['realized_profit'])

    def test_expiry_without_publication(self):
        e=warm(Engine(permit_synthetic_support=True));identity=e.current_ticket['id']
        o=e.tick(70)
        self.assertEqual(o['ticket']['status'],'EXPIRED');self.assertFalse(o['research_qualified'])
        self.assertEqual(e.current_ticket['id'],identity);self.assertEqual(len(e.managers),0)

    def test_refresh_same_ticket_then_price_cancellation(self):
        e=warm(Engine(permit_synthetic_support=True));tid=e.current_ticket['id']
        e.process(fixture(65,ask=.50));self.assertEqual(e.current_ticket['id'],tid)
        self.assertEqual(e.current_ticket['current_ask'],.50)
        e.process(fixture(70,ask=.59));self.assertEqual(e.current_ticket['status'],'CANCELED')
        self.assertEqual(e.managers,[])

    def test_canceled_ticket_does_not_monopolize_same_setup_refresh(self):
        e=warm(Engine(permit_synthetic_support=True));tid=e.current_ticket['id'];sid=e.current_ticket['setup_id']
        e.process(fixture(65,ask=.59))
        for t in range(70,121,5):e.process(fixture(t))
        self.assertEqual(e.current_ticket['status'],'VALID');self.assertNotEqual(e.current_ticket['id'],tid)
        self.assertEqual(e.current_ticket['setup_id'],sid)
        self.assertEqual(e.tickets[1]['predecessor_ticket_id'],tid)
        self.assertTrue(all(t['setup_id']==sid for t in e.tickets))
        self.assertEqual(len([x for x in e.events if x['event']=='SETUP_RECOGNIZED' and x['setup']['side']=='UP']),1)

    def test_deterioration_cancels_ticket_and_requires_reconfirmation(self):
        e=warm(Engine(permit_synthetic_support=True))
        e.process(fixture(65,delta=-100,ask=.30))
        self.assertEqual(e.current_ticket['status'],'CANCELED');self.assertEqual(e.managers,[])

    def test_manual_confirmation_checks_price_time_and_identity(self):
        e=warm(Engine(permit_synthetic_support=True));t=e.current_ticket
        event=dict(id='m',ticket_id=t['id'],contract='A',side='UP',price=.44,quantity=1,observed_at=60)
        self.assertFalse(e.confirm_entry(event,60)['accepted']);self.assertFalse(e.managers)
        result=manual(e)
        self.assertTrue(result['accepted']);self.assertEqual(result['actual_observed_elapsed'],30)
        self.assertEqual(e.managers[0].origin.kind,'MANUAL_CONFIRMED')
        self.assertIsNone(result['manual_fill'])
        with self.assertRaises(FrozenInstanceError):e.managers[0].origin.observed_ask=.1

    def test_entry_retains_management_after_ticket_cancel_and_no_adding(self):
        e=warm(Engine(permit_synthetic_support=True));manual(e)
        origin=e.managers[0].origin
        e.cancel(70,['TEST_CANCEL_AFTER_CONFIRMATION'])
        e.process(fixture(75,ask=.60))
        self.assertEqual(e.managers[0].origin,origin)
        self.assertIn('CONFIRMED_ENTRY_ALREADY_TRACKED_NO_ADD_HEDGE_OR_REVERSAL',e.last_assessments['UP']['authorization_blockers'])
        self.assertFalse(e.last_output['research_qualified'])

    def test_simulation_is_explicit_and_does_not_block_recognition(self):
        e=warm();z=e.start_simulation('UP','s1',60)
        self.assertTrue(z['accepted']);self.assertEqual(e.managers[0].origin.kind,'SIMULATED')
        for t in range(65,181,5):e.process(fixture(t,delta=50-2*(t-60)))
        self.assertIn('DOWN',e.setups);self.assertFalse(e.tickets)
        self.assertFalse(e.start_simulation('UP','s1',180)['accepted'])

    def test_duplicates_and_outage_do_not_create_setups(self):
        e=warm(Engine(permit_synthetic_support=True));ids=[s['id'] for s in e.setups.values()]
        for _ in range(4):e.process(e.last)
        self.assertEqual([s['id'] for s in e.setups.values()],ids)
        r=fixture(65);r['healthy']=False;e.process(r)
        for t in range(70,151,5):e.process(fixture(t))
        self.assertEqual([s['id'] for s in e.setups.values()],ids)

    def test_genuine_same_side_and_opposite_requalification(self):
        e=warm(Engine(permit_synthetic_support=True));first=e.setups['UP']['id']
        for t in range(65,186,5):e.process(fixture(t,delta=50-2*(t-60)))
        self.assertNotIn('UP',e.setups);self.assertIn('DOWN',e.setups)
        for t in range(190,401,5):e.process(fixture(t,delta=-200+3*(t-185)))
        self.assertIn('UP',e.setups);self.assertNotEqual(e.setups['UP']['id'],first)
        self.assertTrue(any(x['event']=='SETUP_RESET' for x in e.events))

    def test_rollover_never_transfers_entry_to_new_contract(self):
        e=warm();e.start_simulation('UP','sim',60);origin=e.managers[0].origin
        e.process(fixture(900,contract='B',close=1800))
        self.assertEqual(e.managers[0].origin,origin)
        self.assertIn('CONTRACT_ROLLOVER_NO_NEW_CONTRACT_PRICE',e.managers[0].last_reasons)
        self.assertFalse(e.setups)
        self.assertIn('OLDER_CONTRACT',e.process(fixture(905,contract='A',close=1800))['reasons'])

    def test_invalid_target_close_and_future_receipt_fail_closed(self):
        for changed in ({'target':100001},{'left':800},{'time':1000}):
            e=warm(Engine(permit_synthetic_support=True));r=fixture(65);r.update(changed)
            o=e.process(r);self.assertFalse(o['research_qualified'])

    def test_prefix_decisions_unchanged_by_future_data(self):
        seq=[fixture(t) for t in range(0,121,5)]
        a=Engine();prefix=[a.process(r) for r in seq[:13]]
        b=Engine();outputs=[b.process(r) for r in seq]
        self.assertEqual(prefix,outputs[:13])
        seq[-1]['btc']=1e9;c=Engine()
        self.assertEqual(prefix,[c.process(r) for r in seq][:13])

    def test_pre_crossing_management_baseline_exact_compatibility(self):
        for side in ('UP','DOWN'):
            e=warm(side=side,pre=True);self.assertTrue(e.start_simulation(side,'sim',60)['accepted'])
            m=e.managers[0];baseline=deepcopy(m.core)
            for t in range(65,201,5):
                r=fixture(t,side,delta=-300+.5*t)
                e.process(r);baseline.history=deepcopy(e.history);out=baseline.manage(r)
                self.assertEqual(m.core.guidance,baseline.guidance)
                self.assertEqual(m.core.terminal,baseline.terminal)
            self.assertIsNone(m.core.terminal)
            # Continued progress below target is allowed, but baseline recovery remains conservative.
            for t in range(205,331,5):e.process(fixture(t,side,delta=-200-2*(t-200),ask=.40))
            self.assertIsNotNone(m.core.terminal)

    def test_watch_recovery_and_no_fixed_exit_timer(self):
        e=warm();e.start_simulation('UP','sim',60);m=e.managers[0]
        for t in range(65,126,5):e.process(fixture(t,delta=50,ask=.45-(t-60)*.0005))
        self.assertEqual(m.core.guidance,'WATCH');self.assertIsNone(m.core.terminal)
        for t in range(130,751,5):e.process(fixture(t,delta=50+t-125))
        self.assertEqual(m.core.guidance,'HOLD');self.assertIsNone(m.core.terminal)
        self.assertGreater(e.last['time']-m.origin.entry_time,420)

    def test_pre_crossing_warning_recovery_remains_conservative(self):
        e=warm(pre=True);e.start_simulation('UP','sim',60);m=e.managers[0]
        for t in range(65,126,5):e.process(fixture(t,delta=-270))
        self.assertEqual(m.core.guidance,'WATCH')
        for t in range(130,201,5):e.process(fixture(t,delta=-270+.5*(t-125)))
        self.assertEqual(m.core.guidance,'WATCH');self.assertIsNone(m.core.terminal)

    def test_source_unavailable_never_infers_exit_or_executable_quote(self):
        e=warm();e.start_simulation('UP','sim',60);m=e.managers[0]
        e.tick(71)
        self.assertIsNone(m.core.terminal);self.assertEqual(m.view()['display'],'WATCH')
        self.assertFalse(m.core.origin['complete']);self.assertEqual(m.origin.kind,'SIMULATED')

    def test_output_mapping_preserves_protect_latch(self):
        e=warm();e.start_simulation('UP','sim',60);m=e.managers[0]
        for internal in ('HOLD','WATCH','PROTECT','EXIT'):
            m.core.guidance=internal
            self.assertEqual(m.view()['display'],'EXIT' if internal=='EXIT' else 'WATCH')
            self.assertEqual(m.core.guidance,internal)
        m.core.guidance='HOLD';m.protect_latched=True
        self.assertEqual(m.view()['internal_state'],'PROTECT');self.assertTrue(m.protect_latched)

    def test_signal_only_recursively_on_events_and_top_level(self):
        e=warm(Engine(permit_synthetic_support=True));manual(e)
        for out in e.events+[e.last_output,e.managers[0].view()]:
            for k,v in SAFETY.items():self.assertIs(out[k],v)

    def test_human_latency_is_observed_elapsed_not_exact_requested(self):
        e=warm(Engine(permit_synthetic_support=True));issued=e.current_ticket['issued_at']
        e.process(fixture(68))
        event=dict(id='late',ticket_id=e.current_ticket['id'],contract='A',side='UP',price=.45,quantity=1,observed_at=68)
        result=e.confirm_entry(event,68)
        self.assertTrue(result['accepted']);self.assertEqual(result['actual_observed_elapsed'],68-issued)

    def test_no_auto_close_or_position_netting_on_exit(self):
        e=warm(Engine(permit_synthetic_support=True));manual(e)
        for t in range(75,211,5):e.process(fixture(t,delta=55-2*(t-70),ask=.40))
        m=e.managers[0];self.assertIsNotNone(m.core.terminal);self.assertFalse(m.closed)
        self.assertFalse(e.last_output['research_qualified'])
        self.assertTrue(e.close_entry(m.origin.id,'user-close',210)['accepted'])
        self.assertIsNone(e.managers[0].view()['realized_profit'])

    def test_native_final_strong_loss_protection_and_receipt_rejection(self):
        from candidates.early_opportunity_20261011.test_candidate import value_frame
        from .management import Management,Origin
        def rfrom(f):
            return dict(contract=f['contract'],target=f['target'],time=f['feature_cutoff'],received=f['captured_ts'],
                        left=f['official_close']-f['feature_cutoff'],native_frame=f,publication_id=str(f['native_sequence']),
                        up_bid=f['up_bid'],down_bid=f['down_bid'])
        f=value_frame(p=.95);r=rfrom(f)
        origin=Origin('o','s','t',r['contract'],'UP','SIMULATED',r['received'],.53,1,'explicit')
        m=Management(origin,[],r,dict(structure_btc=80000,structure_brti=80000),Rules())
        self.assertTrue(m.saw_strong_final);self.assertFalse(m.protect_latched)
        f=value_frame(sequence=2,p=.85);m.final_layer(rfrom(f))
        self.assertTrue(m.protect_latched)
        f=value_frame(sequence=3,p=.95);m.final_layer(rfrom(f))
        self.assertTrue(m.protect_latched)
        f['quote']['ticker']='WRONG';m.final_layer(rfrom(f))
        self.assertEqual(m.final_status,'UNAVAILABLE');self.assertTrue(m.protect_latched)

    def test_simultaneous_opposing_qualification_is_not_auto_selected(self):
        from unittest.mock import patch
        from . import engine as mod
        original=mod.assess
        def both(*args,**kw):
            a=original(*args,**kw)
            if a['features']:
                a['recognized']=True;a['recognition_blockers']=[];a['execution_blockers']=[]
            return a
        with patch.object(mod,'assess',both):
            e=warm(Engine(permit_synthetic_support=True))
        self.assertFalse(e.tickets)
        for a in e.last_assessments.values():
            self.assertIn('OPPOSING_QUALIFIED_CANDIDATES_AMBIGUOUS',a['authorization_blockers'])

    def test_outage_and_backward_clock_cannot_close_or_create_simulation(self):
        e=warm();e.tick(100)
        self.assertFalse(e.start_simulation('UP','x',60)['accepted'])
        e=warm();e.start_simulation('UP','sim',60);e.tick(100)
        self.assertFalse(e.close_entry(e.managers[0].origin.id,'x',60)['accepted'])
        self.assertFalse(e.managers[0].closed)

if __name__=='__main__':unittest.main()
