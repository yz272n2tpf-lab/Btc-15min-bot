"""Causal live delivery and independently failing history, through real bot code."""
from datetime import datetime, timezone, timedelta
import threading
import types
import sys
import unittest
from unittest.mock import Mock, patch
from btc15_brti_delivery_v1 import Delivery
from test_btc15_brti_history_recovery_regressions import load_functions


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.d = Delivery()
        self.d.accept(100000, 100, 101, 'owner-a')

    def test_asof_keeps_prior_receipt_when_newer_source_was_received_after_cut(self):
        self.d.accept(100010, 102, 103, 'owner-a')
        row = self.d.select(102.5, 103.1)
        self.assertEqual((row['cf_ts'], row['observed_ts'], row['decision_ts']), (100,101,102.5))
        self.assertTrue(row['ready'])

    def test_delayed_old_source_is_not_available_retroactively(self):
        self.assertIsNone(self.d.select(100.5, 101.5))

    def test_repeated_receipts_do_not_refresh_source_or_first_receipt(self):
        self.d.accept(100000, 100, 104, 'owner-a')
        row = self.d.select(104.5, 105)
        self.assertEqual(row['observed_ts'], 101)
        self.assertEqual(row['age'], 4.5)
        self.assertTrue(row['ready'])
        self.assertFalse(self.d.select(104.5,105.0001)['ready'])

    def test_error_and_recovery_apply_at_their_actual_receipts(self):
        self.d.fail(102)
        self.assertFalse(self.d.select(101.5,102.1)['ready'])
        self.d.accept(100002,102,103,'owner-a')
        self.assertFalse(self.d.select(102.5,103.1)['ready'])
        self.assertTrue(self.d.select(103,103.1)['ready'])

    def test_epoch_change_cannot_lend_new_state_to_old_decision(self):
        self.d.accept(100001,101,102,'owner-b')
        self.assertIsNone(self.d.select(101.5,102.1))
        self.assertEqual(self.d.select(102,102)['owner_epoch'],'owner-b')

    def test_history_remains_observation_only_and_keeps_first_arrival(self):
        self.d.remember([(102,100002)],103)
        self.d.remember([(102,100002)],104)
        self.assertFalse(self.d.known_at(102,100002,102.9))
        self.assertTrue(self.d.known_at(102,100002,103))
        self.assertEqual(self.d.select(103,103)['cf_ts'],100)

    def test_future_stale_conflicting_and_regressed_state_rejected(self):
        for value,source,observed in [(1,102,101),(1,95,101),(100001,100,101),(1,99,101),(1,float('nan'),101),(1,100,100.5)]:
            with self.subTest((value,source,observed)), self.assertRaises(ValueError):
                self.d.accept(value,source,observed,'owner-a')
        self.assertFalse(self.d.select(103,102)['ready'])

    def test_retention_bounded_without_source_clock_substitution(self):
        for t in range(101,1001):
            self.d.accept(100000,t,t+1,'owner-a')
            self.d.remember([(t,100000)],t+1)
        self.assertEqual(len(self.d.states),600)
        self.assertLessEqual(len(self.d.seen),600)
        self.assertEqual(self.d.states[-1]['cf_ts'],1000)


class BotIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.p = load_functions()
        self.base = datetime(2026,9,24,16,0,tzinfo=timezone.utc)
        self.t = self.base.timestamp()
        self.p.time.time.return_value = self.t+1
        self.p._fetch_direct_brti_once.return_value = (100000,self.t)
        self.gateway = types.ModuleType('btc15_brti_ws_gateway_client_v1')
        self.gateway.ticks = Mock(return_value=[])
        self.enterContext(patch.dict(sys.modules,btc15_brti_ws_gateway_client_v1=self.gateway))
        self.enterContext(patch.dict(self.p.os.environ,BTC15_USE_SHARED_BRTI='1',BTC15_BRTI_TRANSPORT='websocket_gateway'))
        self.p._collect_brti_once(include_history=False)

    def test_history_timeout_in_real_poller_does_not_poison_live_state(self):
        self.gateway.ticks.side_effect = TimeoutError('history endpoint')
        self.p.running = True
        self.p.time.sleep.side_effect = lambda _: setattr(self.p,'running',False)
        self.p._brti_history_poller()
        self.assertTrue(self.p._latest_brti(self.base+timedelta(seconds=1))['ready'])
        self.assertIsNone(self.p._brti_last_error)

    def test_blocked_history_does_not_block_next_live_state(self):
        entered, release = threading.Event(), threading.Event()
        def slow(**kwargs):
            entered.set()
            if not release.wait(2): raise TimeoutError('test wait')
            return []
        self.gateway.ticks.side_effect = slow
        thread = threading.Thread(target=self.p._recover_brti_history_once)
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            self.p.time.time.return_value=self.t+3
            self.p._fetch_direct_brti_once.return_value=(100002,self.t+2)
            self.p._collect_brti_once(include_history=False)
            self.assertEqual(self.p._latest_brti()['value'],100002)
            self.assertTrue(thread.is_alive())
        finally:
            release.set();thread.join(2)

    def test_primary_failure_still_fails_closed_despite_retained_history(self):
        self.p._fetch_direct_brti_once.side_effect=RuntimeError('primary error')
        with self.assertRaises(RuntimeError):self.p._collect_brti_once(include_history=False)
        self.p._store_brti_publications([(self.t+.5,100010)])
        self.assertFalse(self.p._latest_brti()['ready'])
        self.assertEqual(self.p._latest_brti()['cf_ts'],self.t)

    def test_same_cut_does_not_take_future_receipt_or_late_final60_history(self):
        cut = self.base+timedelta(seconds=1)
        self.p.time.time.return_value=self.t+3
        self.p._fetch_direct_brti_once.return_value=(100002,self.t+2)
        self.p._collect_brti_once(include_history=False)
        self.p._store_brti_publications([(self.t-1,100004)])
        snap = self.p._brti_contract_snapshot(self.base+timedelta(seconds=60),99990,100000,as_of=cut)
        self.assertEqual(snap['cf_ts'],self.t)
        self.assertEqual(snap['age'],1)
        self.assertEqual(snap['final60_count'],1)

    def test_retained_history_alone_never_qualifies_live_authority(self):
        self.p._brti_delivery=Delivery()
        self.assertFalse(self.p._latest_brti()['ready'])
        self.assertIsNone(self.p._latest_brti(self.base+timedelta(seconds=1)))

    def test_main_calls_snapshot_with_unchanged_original_decision(self):
        import ast
        from pathlib import Path
        tree=ast.parse(Path('bot_two_output_build_v4_13_profit_protection_shadow.py').read_text())
        loop=next(n for n in tree.body if isinstance(n,ast.While) and isinstance(n.test,ast.Name) and n.test.id=='running')
        calls=[n for n in ast.walk(loop) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_brti_contract_snapshot']
        self.assertEqual(len(calls),1)
        self.assertEqual([(k.arg,ast.unparse(k.value)) for k in calls[0].keywords],[('as_of','now')])


if __name__=='__main__':unittest.main()
