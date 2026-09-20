#!/usr/bin/env python3
"""Focused offline tests of actual collector/closeout functions. NO ORDERS.

AST loading avoids the main bot's import-time training, credentials and network.
Only I/O and wall clock are replaced; collector, joins and closeout run unchanged.
"""
import ast
from collections import deque
import contextlib
from datetime import datetime, timedelta, timezone
import io
import math
import os
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).with_name('bot_two_output_build_v4_13_profit_protection_shadow.py')
FUNCTIONS = {
    '_merge_brti_publications', '_retain_brti_window', '_store_brti_publications',
    '_collect_brti_once', '_brti_poller', '_latest_brti', '_brti_contract_snapshot',
    '_track_brti_contract', '_retry_brti_closeouts', '_try_finalize_brti_contract',
}


def load_functions():
    tree = ast.parse(SOURCE.read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in FUNCTIONS]
    assert {n.name for n in nodes} == FUNCTIONS
    module = types.ModuleType('brti_recovery_under_test')
    clock = types.SimpleNamespace(time=Mock(), sleep=Mock())
    module.__dict__.update(
        datetime=datetime, timezone=timezone, timedelta=timedelta, math=math,
        os=os, time=clock, _brti_lock=threading.Lock(), _brti_samples=deque(maxlen=600),
        _brti_conflicting_seconds=set(), _brti_pending_contracts={},
        _brti_finalized_contracts=set(), _brti_failed_contracts=set(),
        BRTI_CLOSEOUT_RECOVERY_SECONDS=600, BRTI_MAX_AGE_SECONDS=5., BRTI_POLL_SECONDS=1.,
        _brti_last_error=None, _brti_last_error_print=0., running=False,
        _fetch_direct_brti_once=Mock(), _log_brti_parity=Mock(),
    )
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), module.__dict__)
    return module


class HistoryRecovery(unittest.TestCase):
    def setUp(self):
        self.p = load_functions()
        self.close = datetime(2026, 9, 20, 12, 15, tzinfo=timezone.utc)
        self.end = self.close.timestamp()
        self.now(self.end + 3)
        self.points = [(self.end - 60 + i, 100000. + i) for i in range(60)]
        self.gateway = types.ModuleType('btc15_brti_ws_gateway_client_v1')
        self.gateway.ticks = Mock(return_value=[])
        self.output = io.StringIO()
        self.enterContext(contextlib.redirect_stdout(self.output))
        self.enterContext(patch.dict(sys.modules, btc15_brti_ws_gateway_client_v1=self.gateway))
        self.enterContext(patch.dict(os.environ, BTC15_USE_SHARED_BRTI='1', BTC15_BRTI_TRANSPORT='websocket_gateway'))

    def now(self, ts):
        self.p.time.time.return_value = ts
        return datetime.fromtimestamp(ts, timezone.utc)

    def track(self, name='A', close=None):
        self.p._track_brti_contract(name, 99990., close or self.close, 100020.)

    def ingest(self, points):
        self.p._store_brti_publications(points)

    def collect(self, history, latest=None):
        ts, val = latest or self.points[-1]
        self.p._fetch_direct_brti_once.return_value = (val, ts)
        self.gateway.ticks.return_value = [dict(index_id='BRTI', source_ts_ms=int(t*1000), value=v) for t,v in history]
        self.p._collect_brti_once()

    def retry(self, ts=None):
        self.p._retry_brti_closeouts(self.now(self.end+3 if ts is None else ts))

    def snapshot(self):
        return self.p._brti_contract_snapshot(self.close, 99990., 100020.)

    def test_skipped_latest_publications_recovered_from_gateway_history(self):
        self.track()
        self.collect(self.points, latest=self.points[-1])
        self.assertEqual(self.snapshot()['final60_count'], 60)
        self.assertIn('59 publication seconds', self.output.getvalue())
        self.retry()
        self.assertEqual(self.p._brti_finalized_contracts, {'A'})
        row = self.p._log_brti_parity.call_args.args[-1]
        self.assertEqual(row['final60_avg'], sum(v for _,v in self.points)/60)

    def test_duplicate_timestamps_and_repeated_history_count_once(self):
        self.collect(self.points * 3)
        self.collect(self.points)
        self.assertEqual(len(self.p._brti_samples), 60)
        self.assertEqual(self.snapshot()['final60_count'], 60)

    def test_multiple_real_publications_in_same_second_count_once(self):
        self.ingest(self.points + [(self.end-1+.25, 100123.)])
        self.assertEqual(self.snapshot()['final60_count'], 60)
        self.assertEqual(self.p._brti_samples[-1], (self.end-0.75, 100123.))

    def test_conflicting_same_timestamp_fails_closed_even_on_repoll(self):
        self.track()
        self.ingest(self.points + [(self.points[10][0], 999.)])
        self.ingest(self.points)
        self.retry()
        self.assertNotIn('A', self.p._brti_finalized_contracts)
        self.assertEqual(len(self.p._brti_pending_contracts['A']['samples']), 59)
        self.retry(self.end+600)
        self.assertEqual(self.p._brti_failed_contracts, {'A'})

    def test_delayed_publication_after_close_uses_source_time(self):
        self.track()
        self.collect(self.points[:-1], latest=(self.end+1, 999999.))
        self.retry()
        self.assertIn('A', self.p._brti_pending_contracts)
        self.now(self.end+7)
        self.collect(self.points, latest=(self.end+6, 999999.))
        self.retry(self.end+7)
        self.assertEqual(self.p._brti_finalized_contracts, {'A'})
        self.assertEqual(self.p._log_brti_parity.call_args.args[-1]['final60_count'], 60)

    def test_rollover_retains_previous_incomplete_contract(self):
        self.track()
        self.ingest(self.points[:-1])
        self.retry()
        self.track('B', self.close+timedelta(minutes=15))
        self.assertEqual(set(self.p._brti_pending_contracts), {'A','B'})
        self.ingest(self.points[-1:])
        self.retry(self.end+8)
        self.assertEqual(self.p._brti_finalized_contracts, {'A'})
        self.assertEqual(set(self.p._brti_pending_contracts), {'B'})

    def test_two_consecutive_rollovers_keep_each_retry_state(self):
        for i, name in enumerate(('A','B','C')):
            end = self.end+i*900
            self.now(end+3)
            self.track(name, self.close+timedelta(seconds=i*900))
            points=[(t+i*900,v) for t,v in self.points]
            self.ingest(points[:-1])
            self.retry(end+3)
            self.track(chr(ord(name)+1), self.close+timedelta(seconds=(i+1)*900))
            self.now(end+8)
            self.ingest(points[-1:])
            self.retry(end+8)
        self.assertEqual(self.p._brti_finalized_contracts, {'A','B','C'})
        self.assertEqual(set(self.p._brti_pending_contracts), {'D'})
        self.assertEqual(self.p._log_brti_parity.call_count, 3)

    def test_true_missing_second_explicitly_fails_once_at_deadline(self):
        self.track()
        self.ingest(self.points[:-1])
        self.retry(self.end+599)
        self.assertIn('A', self.p._brti_pending_contracts)
        self.retry(self.end+600)
        self.retry(self.end+601)
        self.assertFalse(self.p._brti_finalized_contracts)
        self.assertEqual(self.p._brti_failed_contracts, {'A'})
        self.assertNotIn('A', self.p._brti_pending_contracts)
        self.assertIn('59/60 readings | complete False | RECOVERY_EXPIRED', self.output.getvalue())
        self.assertEqual(self.p._log_brti_parity.call_count, 1)
        self.assertFalse(self.p._log_brti_parity.call_args.args[-1]['final60_complete'])

    def test_absent_feed_fails_closed_without_a_fake_reading(self):
        self.track()
        self.retry(self.end+600)
        self.assertEqual(self.p._brti_failed_contracts, {'A'})
        self.assertIsNone(self.p._log_brti_parity.call_args.args[-1])

    def test_next_contract_and_exact_close_never_count_for_previous(self):
        self.track()
        self.ingest(self.points[:-1]+[(self.end-61,1.), (self.end,9e9), (self.end+1,9e9)])
        self.retry()
        self.assertEqual(self.snapshot()['final60_count'], 59)
        self.assertNotIn('A', self.p._brti_finalized_contracts)
        self.ingest(self.points[-1:])
        self.retry()
        self.assertEqual(self.p._log_brti_parity.call_args.args[-1]['final60_avg'], 100029.5)

    def test_exact_60_complete_finalization_idempotent_and_grace_preserved(self):
        self.track()
        self.ingest(self.points)
        self.retry(self.end+1)
        self.assertFalse(self.p._brti_finalized_contracts)
        self.retry(self.end+2)
        self.retry(self.end+3)
        self.track()
        self.assertEqual(self.p._log_brti_parity.call_count, 1)
        self.assertFalse(self.p._brti_pending_contracts)
        self.assertTrue(self.p._log_brti_parity.call_args.args[-1]['final60_complete'])

    def test_pending_readings_survive_live_buffer_eviction(self):
        self.track()
        self.ingest(self.points[:-1])
        self.retry()
        self.now(self.end+590)
        self.ingest([(self.end+589, 123.)])
        self.assertEqual(len(self.p._brti_samples), 10)
        self.ingest(self.points[-1:])
        self.retry(self.end+590)
        self.assertEqual(self.p._brti_finalized_contracts, {'A'})
        self.assertEqual(self.p._log_brti_parity.call_args.args[-1]['final60_count'], 60)

    def test_delayed_oldest_reading_retained_before_live_buffer_pruning(self):
        self.track()
        self.ingest(self.points[1:])
        self.retry()
        self.now(self.end+599)
        self.ingest([(self.end+598, 123.)]+self.points[:1])
        self.retry(self.end+599)
        self.assertEqual(self.p._brti_finalized_contracts, {'A'})

    def test_history_failure_keeps_qualified_latest_without_http_fallback(self):
        self.p._fetch_direct_brti_once.return_value=(100123.,self.end+2)
        self.gateway.ticks.side_effect=RuntimeError('history unavailable')
        with self.assertRaises(RuntimeError): self.p._collect_brti_once()
        self.assertTrue(self.p._latest_brti()['ready'])
        self.assertEqual(self.p._latest_brti()['cf_ts'], self.end+2)

    def test_unqualified_state_cannot_trigger_history_ingestion(self):
        self.p._fetch_direct_brti_once.side_effect=RuntimeError('state not ready')
        with self.assertRaises(RuntimeError): self.p._collect_brti_once()
        self.gateway.ticks.assert_not_called()
        self.assertFalse(self.p._brti_samples)

    def test_original_publication_time_and_five_second_freshness(self):
        self.collect(self.points, latest=(self.end+2, 100123.))
        self.assertEqual(self.p._latest_brti()['cf_ts'], self.end+2)
        self.now(self.end+7)
        self.assertTrue(self.p._latest_brti()['ready'])
        self.now(self.end+7.001)
        self.assertFalse(self.p._latest_brti()['ready'])

    def test_invalid_future_and_non_brti_ticks_rejected(self):
        self.p._fetch_direct_brti_once.return_value=(100001.,self.end+2)
        self.gateway.ticks.return_value=[
            dict(index_id='OTHER',source_ts_ms=int((self.end-5)*1000),value=1.),
            dict(index_id='BRTI',source_ts_ms=int((self.end+4)*1000),value=1.),
            dict(index_id='BRTI',source_ts_ms=int((self.end-4)*1000),value=float('nan')),
            dict(index_id='BRTI',source_ts_ms='bad',value=1.), None,
        ]
        self.p._collect_brti_once()
        self.assertEqual(list(self.p._brti_samples), [(self.end+2,100001.)])

    def test_unrecoverable_previous_does_not_prevent_next_completion(self):
        self.track()
        self.ingest(self.points[:-1])
        self.track('B', self.close+timedelta(minutes=15))
        self.retry(self.end+600)
        self.now(self.end+903)
        self.ingest([(t+900,v) for t,v in self.points])
        self.retry(self.end+903)
        self.assertEqual(self.p._brti_failed_contracts, {'A'})
        self.assertEqual(self.p._brti_finalized_contracts, {'B'})

    def test_changed_contract_metadata_cannot_retarget_pending_window(self):
        self.track()
        with self.assertRaises(RuntimeError):
            self.p._track_brti_contract('A', 1., self.close, 100020.)
        with self.assertRaises(RuntimeError):
            self.track('A', self.close+timedelta(minutes=15))
        self.assertEqual(self.p._brti_pending_contracts['A']['close_dt'], self.close)

    def test_legacy_mode_does_not_call_gateway_history(self):
        with patch.dict(os.environ, BTC15_USE_SHARED_BRTI='0'):
            self.collect(self.points)
        self.gateway.ticks.assert_not_called()
        self.assertEqual(len(self.p._brti_samples), 1)

    def test_late_history_cannot_revive_explicitly_failed_closeout(self):
        self.track()
        self.ingest(self.points[:-1])
        self.retry(self.end+600)
        self.ingest(self.points)
        self.track()
        self.retry(self.end+601)
        self.assertFalse(self.p._brti_finalized_contracts)
        self.assertEqual(self.p._brti_failed_contracts, {'A'})
        self.assertFalse(self.p._brti_pending_contracts)

    def test_conflicting_late_history_invalidates_retained_second(self):
        self.track()
        self.ingest(self.points[:-1])
        self.retry()
        self.ingest([(self.points[5][0], -1.)])
        self.ingest(self.points[-1:])
        self.retry(self.end+8)
        self.assertFalse(self.p._brti_finalized_contracts)
        self.assertEqual(len(self.p._brti_pending_contracts['A']['samples']), 59)
        self.assertEqual(self.output.getvalue().count('BRTI CLOSEOUT PENDING'), 1)

    def test_real_poller_calls_coordinated_collector(self):
        self.p.running = True
        self.p._fetch_direct_brti_once.return_value = (self.points[-1][1],self.points[-1][0])
        self.gateway.ticks.return_value = [dict(index_id='BRTI',source_ts_ms=int(t*1000),value=v) for t,v in self.points]
        def stop(_): self.p.running = False
        self.p.time.sleep.side_effect = stop
        self.p._brti_poller()
        self.assertEqual(self.snapshot()['final60_count'], 60)
        self.assertIsNone(self.p._brti_last_error)

    def test_runtime_retries_before_market_fetch_and_preserves_no_orders(self):
        source=SOURCE.read_text()
        loop=source[source.index('iteration = 0'):]
        self.assertLess(loop.index('_retry_brti_closeouts('), loop.index('market = get_active_market()'))
        self.assertIn('_track_brti_contract(ticker, target, close_dt, btc)', loop)
        self.assertNotIn('_brti_last_contract_meta', source)
        for forbidden in ('requests.post(', 'requests.put(', 'requests.patch(', 'requests.delete('):
            self.assertNotIn(forbidden, source)
        self.assertIn('DIRECT_BRTI_AUTH_WAIT_DOLLARS = 11.0', source)
        self.assertIn('DIRECT_BRTI_AUTH_MAX_AGE_SECONDS = 5.0', source)
        self.assertIn('NO ORDERS', source)


if __name__ == '__main__':
    unittest.main()
