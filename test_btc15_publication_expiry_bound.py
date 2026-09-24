"""Failure-mechanism tests against unchanged production Delivery, not a fix."""
import ast
from pathlib import Path
import unittest
from btc15_brti_delivery_v1 import Delivery
from completion_audit.diagnose_brti_publication_expiry_v1 import fresh_at


class PublicationExpiryBound(unittest.TestCase):
    def actual_functions(self, names, **namespace):
        p=Path(__file__).with_name('bot_two_output_build_v4_13_profit_protection_shadow.py')
        tree=ast.parse(p.read_text())
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        self.assertEqual({n.name for n in nodes},set(names))
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),namespace)
        return namespace

    def test_plain_one_second_loop_changes_actual_persistence_counts(self):
        from collections import deque
        ns=self.actual_functions({'_unified_candidate_persistence'},_unified_hist=deque())
        counts=[]
        for cadence in (5,1):
            ns['_unified_hist'].clear()
            ns['_unified_hist'].extend(dict(contract='A',side='UP',ts=t,broad_candidate=True)
                                      for t in range(0,31,cadence))
            counts.append(ns['_unified_candidate_persistence']('A','UP',30))
        self.assertEqual(counts,[7,31])

    def test_plain_one_second_loop_changes_actual_rolling_extrema(self):
        from collections import deque
        ns=self.actual_functions({'rows_since','low_high'},history=deque())
        extrema=[]
        for cadence in (5,1):
            ns['history'].clear()
            ns['history'].extend(dict(ts=t,up_ask=.4 if t==27 else .6)
                                 for t in range(0,61,cadence))
            extrema.append(ns['low_high']('up_ask',60,60))
        self.assertEqual(extrema,[(.6,.6),(.4,.6)])

    def test_new_owner_receipts_do_not_refresh_original_decision(self):
        d=Delivery();d.accept(100000,100,101,'owner');cut=102.5
        self.assertTrue(d.select(cut,cut)['ready'])
        d.accept(100001,103,104,'owner')
        self.assertTrue(d.select(cut,105)['ready'])
        self.assertFalse(d.select(cut,105.001)['ready'])
        self.assertEqual(d.select(cut,105.001)['cf_ts'],100)
        self.assertTrue(d.select(105.001,105.001)['ready'])

    def test_republishing_repeated_sample_cannot_extend_five_seconds(self):
        for publish in (102,103,104,105,105.001,106.999):
            self.assertEqual(fresh_at(102,100,101,publish),publish<=105)

    def test_unavailable_at_original_decision_cannot_be_borrowed(self):
        self.assertFalse(fresh_at(102,101,102.001,103))
        self.assertFalse(fresh_at(102,103,103,104))
        self.assertFalse(fresh_at(102,100,101,101.999))

    def test_any_positive_source_age_forces_gap_at_five_second_cadence(self):
        for age in (.001,.610471,1,2.485909,4.478169,5):
            decision=100.;source=decision-age;next_decision=decision+5
            self.assertAlmostEqual(next_decision-(source+5),age)
            midpoint=(source+5+next_decision)/2
            self.assertFalse(fresh_at(decision,source,decision,midpoint))

    def test_jitter_cannot_extend_original_source_deadline(self):
        for interval in (4.809715,5,5.180638,10):
            deadline=100+5;next_decision=102.5+interval
            self.assertGreater(next_decision,deadline)
            self.assertFalse(fresh_at(102.5,100,101,next_decision-.000001))

    def test_transport_failure_and_recovery_do_not_requalify_old_source(self):
        d=Delivery();d.accept(100000,100,101,'owner');d.fail(102)
        self.assertFalse(d.select(101.5,102.5)['ready'])
        d.accept(100001,103,104,'owner')
        self.assertFalse(d.select(101.5,106)['ready'])
        self.assertTrue(d.select(104.5,104.5)['ready'])

    def test_owner_restart_cannot_supply_an_old_decision(self):
        d=Delivery();d.accept(100000,100,101,'a');d.accept(100001,103,104,'b')
        self.assertIsNone(d.select(102,104.5))

    def test_fast_receipt_alone_leaves_snapshot_retention_gap(self):
        d=Delivery();d.accept(100000,100,100.01,'owner')
        for source in (101,102,103,104,105):d.accept(100000+source,source,source+.01,'owner')
        original=d.select(100.02,105.01)
        self.assertFalse(original['ready']);self.assertEqual(original['cf_ts'],100)

    def test_exact_production_cadences_and_causal_cut_are_unchanged(self):
        p=Path(__file__).with_name('bot_two_output_build_v4_13_profit_protection_shadow.py')
        tree=ast.parse(p.read_text());constants={}
        for n in tree.body:
            if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
                try: constants[n.targets[0].id]=ast.literal_eval(n.value)
                except (ValueError,TypeError): pass
        self.assertEqual(constants['POLL_SECONDS'],5)
        self.assertEqual(constants['BRTI_POLL_SECONDS'],1)
        self.assertEqual(constants['BRTI_MAX_AGE_SECONDS'],5)
        loop=next(n for n in tree.body if isinstance(n,ast.While) and ast.unparse(n.test)=='running')
        calls=[n for n in ast.walk(loop) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
               and n.func.id=='_brti_contract_snapshot']
        self.assertEqual(len(calls),1)
        self.assertEqual([(k.arg,ast.unparse(k.value)) for k in calls[0].keywords],[('as_of','now')])


if __name__=='__main__': unittest.main()
