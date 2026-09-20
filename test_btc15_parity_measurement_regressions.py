#!/usr/bin/env python3
"""Offline parity measurement regressions. No credentials, live bot or network.

Load the actual source functions/constants with AST, excluding import-time
third-party/network dependencies and runtime data-root creation. Every I/O
boundary used by audit is explicitly replaced with deterministic fixtures.
"""
import ast
import contextlib
import csv
from datetime import datetime, timedelta, timezone
import io
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).with_name('btc15_kalshi_parity_shadow_v1.py')


def load_functions():
    nodes = []
    for node in ast.parse(SOURCE.read_text()).body:
        if isinstance(node, ast.FunctionDef):
            nodes.append(node)
        elif isinstance(node, ast.Assign):
            if not any(isinstance(t, ast.Name) and t.id in {'DATA_ROOT', 'UNIFIED', 'BRTI_LOG', 'OUT'}
                       for t in node.targets):
                nodes.append(node)
    module = types.ModuleType('parity_under_test')
    module.__dict__.update(datetime=datetime, timezone=timezone, math=math, csv=csv,
                           os=os, sys=sys, time=time, Path=Path,
                           BRTI_LOG=Path('fixture-brti'), UNIFIED=Path('fixture-unified'))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), module.__dict__)
    return module


class ParityMeasurements(unittest.TestCase):
    def setUp(self):
        self.p = load_functions()
        self.st = datetime(2026, 9, 20, 12, 0, 5, 400000, tzinfo=timezone.utc)
        self.pub = self.st - timedelta(seconds=2.4)
        self.contract = 'KXBTC15M-26SEP200815-15'
        self.bot = dict(timestamp_utc=self.st.isoformat(), contract=self.contract,
                        target=99980., direct_brti=100000., brti_timestamp_utc=self.pub.isoformat(),
                        brti_age_seconds=2.4, brti_side='UP', brti_gap_to_target=20., direct_brti_ready='True')
        self.snap = dict(_source_timestamp=self.st, _snapshot_complete=True,
                         contract=self.contract, seconds_left=894.6, btc_price=100000., btc_gap=20.,
                         up_bid=.49, up_ask=.50, down_bid=.50, down_ask=.51)
        self.market = dict(ticker=self.contract, close_time=(self.st + timedelta(seconds=894.6)).isoformat(),
                           floor_strike=99980., yes_bid_dollars=.49, yes_ask_dollars=.50,
                           no_bid_dollars=.50, no_ask_dollars=.51)
        self.ticks = [(self.pub, 100000.), (self.st - timedelta(seconds=.4), 100008.)]

    def audit(self, *, rows=None, ticks=None, error=None, now=None):
        output = []
        with patch.object(self.p, 'active_market', return_value=self.market), \
             patch.object(self.p, 'latest_unified_snapshot', return_value=self.snap), \
             patch.object(self.p, 'now_utc', return_value=now or self.st + timedelta(seconds=3)), \
             patch.object(self.p, 'direct_brti_payload', return_value=self.ticks if ticks is None else ticks, side_effect=error), \
             patch.object(self.p, 'tail_csv_rows', return_value=[self.bot] if rows is None else rows), \
             patch.object(self.p, 'append', side_effect=output.append), \
             contextlib.redirect_stdout(io.StringIO()):
            self.p.audit()
        return output[0]

    def test_different_ticks_do_not_create_a_false_eight_dollar_failure(self):
        rec = self.audit()
        self.assertEqual(rec['brti_value_delta'], 0.)
        self.assertEqual(rec['brti_time_delta_sec'], 0.)
        self.assertTrue(rec['brti_match'])
        self.assertIn('bot_publication=' + self.pub.isoformat(), rec['notes'])
        self.assertIn('BRTI_PUBLICATION_MATCH', rec['notes'])
        self.assertEqual(rec['overall_status'], 'WAIT')  # Quote parity is still unknown.

    def test_no_exact_tick_does_not_fall_back_to_a_nearby_tick(self):
        rec = self.audit(ticks=[self.ticks[1]])
        self.assertEqual(rec['overall_status'], 'WAIT')
        self.assertEqual(rec['brti_match'], '')
        self.assertTrue(math.isnan(rec['brti_value_delta']))
        self.assertIn('BRTI_PUBLICATION_MISSING_OR_AMBIGUOUS', rec['notes'])

    def test_actual_same_publication_mismatch_is_still_fail(self):
        rec = self.audit(ticks=[(self.pub, 100008.)])
        self.assertEqual(rec['overall_status'], 'FAIL')
        self.assertFalse(rec['brti_match'])
        self.assertEqual(rec['brti_value_delta'], 8.)

    def test_value_threshold_is_not_widened(self):
        at = self.audit(ticks=[(self.pub, 100002.)])
        above = self.audit(ticks=[(self.pub, 100002.0001)])
        self.assertTrue(at['brti_match'])
        self.assertFalse(above['brti_match'])
        self.assertEqual(above['overall_status'], 'FAIL')

    def test_target_crossing_by_different_ticks_is_not_transport_failure(self):
        self.market['floor_strike'] = self.bot['target'] = 100000.
        self.bot.update(direct_brti=100000.1, brti_gap_to_target=.1)
        self.snap['btc_gap'] = 0.
        rec = self.audit(ticks=[(self.pub, 100000.1), (self.ticks[1][0], 99999.9)])
        self.assertTrue(rec['brti_match'])
        self.assertEqual(rec['overall_status'], 'WAIT')

    def test_real_same_publication_side_mismatch_remains_failure(self):
        self.bot['brti_side'] = 'DOWN'
        rec = self.audit()
        self.assertEqual(rec['overall_status'], 'FAIL')
        self.assertFalse(rec['brti_match'])

    def test_flat_is_consistent_with_the_bots_raw_side_semantics(self):
        self.market['floor_strike'] = self.bot['target'] = 100000.
        self.snap['btc_gap'] = 0.
        self.bot.update(brti_side='FLAT', brti_gap_to_target=0.)
        rec = self.audit()
        self.assertTrue(rec['brti_match'])
        self.assertEqual(rec['api_brti_side_near_source'], 'FLAT')

    def test_prior_contract_finalization_cannot_contaminate_current_join(self):
        old = dict(self.bot, contract='KXBTC15M-26SEP200800-00', target=100020., brti_side='DOWN')
        self.assertTrue(self.audit(rows=[old, self.bot])['brti_match'])
        missing = self.audit(rows=[old])
        self.assertEqual(missing['brti_match'], '')
        self.assertIn('BRTI_FRAME_MISSING_OR_AMBIGUOUS', missing['notes'])

    def test_nearby_collector_frame_and_duplicate_frame_are_unverified(self):
        nearby = dict(self.bot, timestamp_utc=(self.st - timedelta(seconds=1)).isoformat())
        for rows in ([nearby], [self.bot, dict(self.bot)]):
            with self.subTest(rows=len(rows)):
                rec = self.audit(rows=rows)
                self.assertEqual(rec['brti_match'], '')
                self.assertEqual(rec['overall_status'], 'WAIT')

    def test_stale_not_ready_future_and_invalid_ages_cannot_pass(self):
        variants = [dict(direct_brti_ready='False'), dict(brti_age_seconds=5.001),
                    dict(brti_age_seconds=-.1), dict(brti_age_seconds='nan'),
                    dict(brti_age_seconds='inf'),
                    dict(brti_timestamp_utc=(self.st - timedelta(seconds=6)).isoformat(), brti_age_seconds=1.),
                    dict(brti_timestamp_utc=(self.st + timedelta(seconds=10)).isoformat())]
        for variant in variants:
            with self.subTest(variant=variant):
                rec = self.audit(rows=[dict(self.bot, **variant)])
                self.assertEqual(rec['brti_match'], '')
                self.assertEqual(rec['overall_status'], 'WAIT')
                self.assertIn('BRTI_NOT_FRESH_AT_COLLECTION', rec['notes'])

    def test_historical_match_is_allowed_when_fresh_at_collection(self):
        # Publication is 6.4s old at audit, but was 2.4s old when bot used it.
        rec = self.audit(now=self.st + timedelta(seconds=4))
        self.assertTrue(rec['brti_match'])

    def test_freshness_at_exact_five_seconds_is_not_retuned(self):
        pub = self.st - timedelta(seconds=5)
        self.bot.update(brti_timestamp_utc=pub.isoformat(), brti_age_seconds=5.)
        self.assertTrue(self.audit(ticks=[(pub, 100000.)])['brti_match'])

    def test_source_age_bounds_and_incomplete_frame_are_unknown(self):
        for age in (-.1, 12.001):
            with self.subTest(age=age):
                rec = self.audit(now=self.st + timedelta(seconds=age))
                self.assertEqual(rec['overall_status'], 'WAIT')
                self.assertIn('SOURCE_AGE_INVALID', rec['notes'])
        self.snap['_snapshot_complete'] = False
        rec = self.audit()
        self.assertEqual(rec['brti_match'], '')
        self.assertIn('SNAPSHOT_INCOMPLETE', rec['notes'])

    def test_quotes_are_unverified_for_both_zero_and_ten_cent_deltas(self):
        for shift in (0., .10):
            with self.subTest(shift=shift):
                self.market.update(yes_bid_dollars=.49+shift, yes_ask_dollars=.50+shift,
                                   no_bid_dollars=.50-shift, no_ask_dollars=.51-shift)
                rec = self.audit()
                self.assertAlmostEqual(rec['quote_max_delta'], shift)
                self.assertFalse(rec['quote_scorable'])
                self.assertEqual(rec['quote_match'], '')
                self.assertEqual(rec['overall_status'], 'WAIT')
                self.assertIn('QUOTES_ASYNC_UNVERIFIED', rec['notes'])
                if shift: self.assertIn('QUOTE_ASYNC_DRIFT', rec['notes'])

    def test_genuine_clock_target_and_log_target_failures_remain_visible(self):
        self.snap['seconds_left'] += 10.001
        self.assertEqual(self.audit()['overall_status'], 'FAIL')
        self.snap['seconds_left'] -= 10.001
        self.snap['btc_gap'] += 1.001
        self.assertEqual(self.audit()['overall_status'], 'FAIL')
        self.snap['btc_gap'] -= 1.001
        self.bot['target'] += 1.001
        rec = self.audit()
        self.assertEqual(rec['overall_status'], 'FAIL')
        self.assertIn('BRTI_LOG_TARGET', rec['notes'])

    def test_rollover_cross_contract_market_is_wait_not_false_clock_failure(self):
        self.market['ticker'] = 'KXBTC15M-26SEP200830-30'
        self.market['close_time'] = (self.st + timedelta(seconds=1794.6)).isoformat()
        rec = self.audit()
        self.assertEqual(rec['overall_status'], 'WAIT')
        self.assertIn('|CONTRACT|', rec['notes'])

    def test_reference_failure_is_unknown_and_error_detail_is_not_exposed(self):
        rec = self.audit(error=RuntimeError('sensitive simulated request detail'))
        self.assertEqual(rec['overall_status'], 'WAIT')
        self.assertEqual(rec['brti_match'], '')
        self.assertIn('BRTI_REFERENCE_UNAVAILABLE=RuntimeError', rec['notes'])
        self.assertNotIn('sensitive', rec['notes'])

    def test_conflicting_publication_values_are_not_arbitrarily_selected(self):
        rec = self.audit(ticks=[(self.pub, 100000.), (self.pub, 100003.)])
        self.assertEqual(rec['brti_match'], '')
        self.assertEqual(rec['overall_status'], 'WAIT')

    def test_exact_frame_reconstruction_never_borrows_an_old_side(self):
        up = dict(timestamp_utc=self.st.isoformat(), contract=self.contract, side='UP', side_bid=.49, side_ask=.50)
        down = dict(up, side='DOWN', side_bid=.50, side_ask=.51)
        old_down = dict(down, timestamp_utc=(self.st-timedelta(seconds=1)).isoformat())
        with patch.object(self.p, 'tail_csv_rows', return_value=[old_down, up]):
            snap = self.p.latest_unified_snapshot()
            self.assertFalse(snap['_snapshot_complete'])
            self.assertNotIn('down_bid', snap)
        with patch.object(self.p, 'tail_csv_rows', return_value=[up, down]):
            snap = self.p.latest_unified_snapshot()
            self.assertTrue(snap['_snapshot_complete'])
            self.assertEqual(snap['down_bid'], .50)

    def test_output_schema_stays_compatible_and_contains_timing_evidence(self):
        rec = self.audit()
        self.assertEqual(set(rec), set(self.p.FIELDS))
        self.assertIn('quote_request_started=', rec['notes'])
        self.assertIn('quote_response_received=', rec['notes'])
        with tempfile.TemporaryDirectory() as temp:
            self.p.OUT = Path(temp) / 'parity.csv'
            self.p.append(rec)
            self.p.append(rec)
            with self.p.OUT.open() as stream:
                reader = csv.DictReader(stream)
                self.assertEqual(reader.fieldnames, self.p.FIELDS)
                self.assertEqual(len(list(reader)), 2)

    def gateway_modules(self, point, raw):
        adapter = types.ModuleType('btc15_brti_shared_consumer_v1')
        adapter.read_shared_brti = Mock(return_value=point)
        client = types.ModuleType('btc15_brti_ws_gateway_client_v1')
        client.ticks = Mock(return_value=raw)
        return adapter, client

    def test_nonempty_tick_history_does_not_bypass_live_freshness_guard(self):
        for age, status in ((5.001, 'PRIMARY_OK'), (-1., 'PRIMARY_OK'), ('nan', 'PRIMARY_OK'), (1., 'STALE')):
            with self.subTest(age=age, status=status):
                adapter, client = self.gateway_modules(dict(age_seconds=age, status=status), [{'index_id':'BRTI'}])
                with patch.dict(os.environ, {'BTC15_USE_SHARED_BRTI':'1', 'BTC15_BRTI_TRANSPORT':'websocket_gateway'}), \
                     patch.dict(sys.modules, {adapter.__name__:adapter, client.__name__:client}):
                    with self.assertRaises(RuntimeError): self.p.direct_brti_payload()
                client.ticks.assert_not_called()

    def test_qualified_gateway_uses_true_timestamps_and_no_direct_http(self):
        source_ms = int(self.pub.timestamp()*1000)
        point = dict(status='PRIMARY_OK', age_seconds=1., source_ts_ms=source_ms, value=100000.)
        raw = [dict(index_id='BRTI', source_ts_ms=source_ms, value=100000.),
               dict(index_id='OTHER', source_ts_ms=source_ms, value=3.),
               dict(index_id='BRTI', source_ts_ms=source_ms+1000, value='nan')]
        for history in (raw, []):
            with self.subTest(empty=not history):
                adapter, client = self.gateway_modules(point, history)
                with patch.dict(os.environ, {'BTC15_USE_SHARED_BRTI':'1', 'BTC15_BRTI_TRANSPORT':'websocket_gateway'}), \
                     patch.dict(sys.modules, {adapter.__name__:adapter, client.__name__:client}), \
                     patch.object(self.p, 'kalshi_get', side_effect=AssertionError('direct HTTP forbidden')):
                    self.assertEqual(self.p.direct_brti_payload(), [(self.pub, 100000.)])
                adapter.read_shared_brti.assert_called_once()
                client.ticks.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
