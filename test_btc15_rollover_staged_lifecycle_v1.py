"""Offline regressions of the real canary and AST-extracted production selector.

No production main import, network requests, collectors, or order actions.
The get_active_market and parse_dt function bodies execute unmodified.
"""
import ast
import contextlib
import io
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import btc15_rollover_production_canary_v1 as canary

CORE = Path(__file__).with_name('bot_two_output_build_v4_13_profit_protection_shadow.py')


class StagedLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.saved_state = canary._state
        canary._state = {'staged': None, 'last_report': None}
        self.open = datetime(2026, 9, 22, 22, 15, tzinfo=timezone.utc)
        self.now = self.open - timedelta(minutes=6)
        self.previous = self.market('KXBTC15M-26SEP221815-15', -15)
        self.current = self.market('KXBTC15M-26SEP221830-30', 0)
        self.future = self.market('KXBTC15M-26SEP221845-45', 15)
        self.later = self.market('KXBTC15M-26SEP221900-00', 30)
        self.unopened = [self.current, self.future]
        self.listed = [self.previous]
        self.exact = {'market': self.current}
        self.unopened_error = self.open_error = self.exact_error = None
        self.calls = []
        self.output = io.StringIO()
        fixture = self

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixture.now

        env = {
            '__file__': str(CORE), 'Path': Path, 'datetime': Clock,
            'timezone': timezone, 'os': types.SimpleNamespace(getpid=lambda: 13),
            'rollover_canary': canary, 'kalshi_get': self.get,
            'rollover_diag': types.SimpleNamespace(
                rollover_boundary=lambda now: self.open,
                _iso=lambda dt: dt.isoformat(), emit=lambda *a, **kw: None),
        }
        tree = ast.parse(CORE.read_text())
        funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in {'parse_dt', 'get_active_market'}]
        self.assertEqual({n.name for n in funcs}, {'parse_dt', 'get_active_market'})
        exec(compile(ast.Module(body=funcs, type_ignores=[]), str(CORE), 'exec'), env)
        self.select = env['get_active_market']
        self.parse_dt = env['parse_dt']

    def tearDown(self):
        canary._state = self.saved_state

    def market(self, ticker, offset):
        op = self.open + timedelta(minutes=offset)
        return {'ticker': ticker, 'open_time': op.isoformat(),
                'close_time': (op + timedelta(minutes=15)).isoformat(),
                'status': 'initialized'}

    def get(self, path, params=None):
        self.calls.append((path, params))
        if path == '/trade-api/v2/markets':
            if params['status'] == 'unopened':
                if self.unopened_error:
                    raise self.unopened_error
                return {'markets': self.unopened}
            self.assertEqual(params['status'], 'open')
            if self.open_error:
                raise self.open_error
            return {'markets': self.listed}
        self.assertTrue(path.startswith('/trade-api/v2/markets/'))
        if self.exact_error:
            raise self.exact_error
        return self.exact

    def stage(self):
        with contextlib.redirect_stdout(self.output):
            canary.observe(self.get, self.parse_dt, self.now)
        self.assertEqual(canary._state['staged']['ticker'], self.current['ticker'])
        self.calls.clear()
        self.output.seek(0)
        self.output.truncate(0)

    def boundary(self, seconds=3.233963):
        self.stage()
        self.now = self.open + timedelta(seconds=seconds)
        self.unopened = [self.future, self.later]

    def run_select(self):
        with contextlib.redirect_stdout(self.output):
            return self.select()

    def exact_calls(self):
        return [p for p, _ in self.calls if p.startswith('/trade-api/v2/markets/')]

    def test_observe_stages_earliest_future(self):
        self.unopened = [self.later, self.future, self.current]
        self.stage()

    def test_repeated_preopen_observation_keeps_imminent(self):
        self.stage()
        self.now = self.open - timedelta(seconds=1)
        self.run_select()
        self.assertEqual(canary._state['staged']['ticker'], self.current['ticker'])
        self.assertEqual(self.exact_calls(), [])

    def test_boundary_handoff_survives_next_future_observation(self):
        self.boundary()
        self.assertIs(self.run_select(), self.current)
        self.assertEqual(self.exact_calls(), ['/trade-api/v2/markets/' + self.current['ticker']])
        self.assertEqual(canary._state['staged']['ticker'], self.future['ticker'])
        self.assertIn('ROLLOVER STAGED HANDOFF', self.output.getvalue())
        self.assertIn('+3.234s', self.output.getvalue())

    def test_exact_open_is_eligible(self):
        self.boundary(0)
        self.assertIs(self.run_select(), self.current)

    def test_preopen_is_never_handed_off(self):
        self.stage()
        self.now = self.open - timedelta(microseconds=1)
        self.assertIs(self.run_select(), self.previous)
        self.assertEqual(self.exact_calls(), [])
        self.assertNotIn('ROLLOVER STAGED HANDOFF', self.output.getvalue())

    def test_opened_contract_still_in_unopened_response(self):
        self.boundary()
        self.unopened = [self.current, self.future]
        self.assertIs(self.run_select(), self.current)
        self.assertEqual(canary._state['staged']['ticker'], self.future['ticker'])

    def test_unwrapped_exact_response(self):
        self.boundary()
        self.exact = self.current
        self.assertIs(self.run_select(), self.current)

    def test_wrong_exact_ticker_is_not_handed_off(self):
        self.boundary()
        self.exact = {'market': self.future}
        self.listed = [self.current]
        self.assertIs(self.run_select(), self.current)
        self.assertEqual(len(self.exact_calls()), 1)
        self.assertNotIn('ROLLOVER STAGED HANDOFF', self.output.getvalue())

    def test_missing_exact_ticker_is_not_handed_off(self):
        self.boundary()
        self.exact = {'market': {}}
        self.assertIsNone(self.run_select())
        self.assertEqual(len(self.exact_calls()), 1)
        self.assertNotIn('ROLLOVER STAGED HANDOFF', self.output.getvalue())

    def test_exact_fetch_error_preserves_existing_exception_policy(self):
        self.boundary()
        self.exact_error = RuntimeError('exact unavailable')
        with self.assertRaisesRegex(RuntimeError, 'exact unavailable'):
            self.run_select()
        self.assertNotIn('ROLLOVER STAGED HANDOFF', self.output.getvalue())

    def test_empty_unopened_keeps_eligible_stage(self):
        self.boundary()
        self.unopened = []
        self.assertIs(self.run_select(), self.current)

    def test_unopened_error_keeps_eligible_stage(self):
        self.boundary()
        self.unopened_error = RuntimeError('unopened unavailable')
        self.assertIs(self.run_select(), self.current)

    def test_open_list_error_preserves_existing_exception_policy(self):
        self.boundary()
        self.open_error = RuntimeError('list unavailable')
        with self.assertRaisesRegex(RuntimeError, 'list unavailable'):
            self.run_select()
        self.assertEqual(self.exact_calls(), [])

    def test_next_contract_still_stages_for_successive_boundary(self):
        self.boundary()
        self.assertIs(self.run_select(), self.current)
        self.assertEqual(canary._state['staged']['ticker'], self.future['ticker'])
        self.now = self.open + timedelta(minutes=15, seconds=4)
        self.unopened = [self.later]
        self.listed = [self.current]
        self.exact = {'market': self.future}
        self.assertIs(self.run_select(), self.future)
        self.assertEqual(canary._state['staged']['ticker'], self.later['ticker'])

    def test_expired_stage_is_not_returned(self):
        self.stage()
        self.now = self.open + timedelta(minutes=15)
        self.unopened = [self.later]
        self.listed = [self.future]
        self.assertIs(self.run_select(), self.future)
        self.assertEqual(self.exact_calls(), [])

    def test_restart_without_stage_uses_existing_list_fallback(self):
        self.now = self.open + timedelta(seconds=3)
        self.unopened = [self.future]
        self.listed = [self.current]
        self.assertIs(self.run_select(), self.current)
        self.assertEqual(self.exact_calls(), [])

    def test_no_stage_and_stale_open_list_returns_none(self):
        self.now = self.open + timedelta(seconds=3)
        self.unopened = [self.future]
        self.assertIsNone(self.run_select())
        self.assertEqual(self.exact_calls(), [])


if __name__ == '__main__':
    unittest.main()
