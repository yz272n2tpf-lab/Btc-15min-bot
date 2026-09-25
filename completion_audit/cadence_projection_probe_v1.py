"""RESEARCH ONLY: isolated-clock projection and exact-source rejection probes.

No runtime import, network, production writes, fitting or orders. The frozen
runtime is the oracle; this module does not replace its decision functions.
"""
import ast
import base64
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import math
from pathlib import Path

from btc15_brti_delivery_v1 import Delivery
from btc15_kalshi_quote_provenance_v1 import replay

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / 'bot_two_output_build_v4_13_profit_protection_shadow.py'
FROZEN_BLOB = 'f547ab4238592910ed76fee61870cd18714d09f0'


def frozen_functions(names, **env):
    raw = BOT.read_bytes()
    blob = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
    if blob != FROZEN_BLOB:
        raise ValueError('Frozen oracle changed')
    tree = ast.parse(raw)
    nodes = [n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in nodes} != set(names):
        raise ValueError('Missing frozen function')
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(BOT), 'exec'), env)
    return env


class AnchorHistory:
    """Original writer only. Projection histories cannot persist a new hit.

    Commit timestamps are supplied by the original loop; they are NOT rounded
    to a newly invented five-second grid. This matters after waits and jitter.
    """
    def __init__(self):
        self.early = deque()
        self.unified = deque()
        self.raw = deque()
        self.btc = deque()
        self.last_commit = None

    def commit(self, at, contract, *, candidate=True, ask=.4, btc=100080.):
        if self.last_commit is not None and at <= self.last_commit:
            raise ValueError('Duplicate or reversed legacy commit')
        if self.raw and self.raw[-1]['contract'] != contract:
            self.raw.clear()
        self.raw.append(dict(ts=at, contract=contract, up_ask=ask, btc=btc))
        self.early.append(dict(ts=at, contract=contract, candidate=candidate))
        self.unified.extend(dict(ts=at, contract=contract, side=s,
                                 broad_candidate=candidate) for s in ('UP', 'DOWN'))
        self.btc.append((at, at, btc))
        for records, budget in ((self.raw, 240), (self.early, 90), (self.unified, 180)):
            while records and at - records[0]['ts'] > budget:
                records.popleft()
        self.last_commit = at

    def project(self, at, contract):
        if self.last_commit is None or at < self.last_commit:
            raise ValueError('Missing or future anchor')
        return dict(
            early=sum(r['candidate'] for r in self.early
                      if r['contract'] == contract and 0 <= at-r['ts'] <= 30),
            unified={side: sum(r['broad_candidate'] for r in self.unified
                              if r['contract'] == contract and r['side'] == side
                              and 0 <= at-r['ts'] <= 30) for side in ('UP', 'DOWN')},
        )


def raw_ladders(**values):
    """Execute the three exact deployed display-gate expressions, in memory.

    This probes gate semantics only. The caller supplies model outputs; no
    synthetic probability is presented as a fitted-model performance result.
    """
    tree = ast.parse((ROOT / 'BTC15_INSTALL_LIVE_DASHBOARD_V13.py').read_text())
    payloads = next(ast.literal_eval(n.value) for n in tree.body
                    if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'PAYLOADS' for t in n.targets))
    code = gzip.decompress(base64.b64decode(payloads['BTC15_DASHBOARD_STATE_V2.py']))
    tree = ast.parse(code)
    ns = dict(math=math, **values)
    for n in tree.body:
        if isinstance(n, ast.Assign):
            try:
                value = ast.literal_eval(n.value)
            except (ValueError, TypeError):
                continue
            for target in n.targets:
                if isinstance(target, ast.Name):
                    ns[target.id] = value
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build_state')
    names = {'direct_brti_authority_ready', 'direct_brti_agrees', 'tier1_ready',
             'required_gap', 'final_ready', 'scalp_ready'}
    nodes = [n for n in fn.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'frozen_display_gates', 'exec'), ns)
    return {key: bool(ns[name]) for key, name in
            [('EARLY', 'tier1_ready'), ('FINAL', 'final_ready'), ('CORE_SCALP', 'scalp_ready')]}


def gate_inputs(**updates):
    return dict(dict(pref_side='UP', target_side='UP', pref_fair=.96,
                     pref_edge=.56, pref_ask=.40, pref_bid=.39,
                     minutes_left=5., abs_gap=80., ratio=2., brti_ready_raw=True,
                     brti_age=2., brti_gap=80., brti_side='UP'), **updates)


def quote_proof(cut_ms, source_ms, ticker='A', seq=2):
    events = [dict(type='orderbook_snapshot', sid=1, seq=seq-1,
                   msg=dict(market_ticker=ticker, market_id='M',
                            yes_dollars_fp=[['0.39', '10']], no_dollars_fp=[['0.59', '10']])),
              dict(type='orderbook_delta', sid=1, seq=seq,
                   msg=dict(market_ticker=ticker, market_id='M', side='yes',
                            price_dollars='0.39', delta_fp='1', ts_ms=source_ms))]
    return dict(source_time=datetime.fromtimestamp(cut_ms/1000, timezone.utc).isoformat(),
                ticker=ticker, epoch='synthetic-quote-epoch', consumed_ms=cut_ms,
                identity=['M', 1, seq, source_ms], events=events)


def source_availability(cadence, *, delay=1.4, duration=600, outage=None,
                        quote_wait=None, jitter=0.):
    """Synthetic engineering bound, NOT expected production availability.

    Original source/receipt clocks and all retained-decision deadlines survive.
    At each publication, select only receipts already present at its new cut.
    Omits inference cost/parity join; therefore never called a complete fix.
    """
    d = Delivery()
    frame = None
    published = 0
    qualified = 0
    checked = 0
    source = -20
    next_cut = 0.
    observations = []
    for i in range(duration*10):
        at = i/10
        while source + delay <= at:
            observed = source+delay
            if outage is None or not outage[0] <= observed < outage[1]:
                d.accept(100000.+source/100, source, observed, 'owner')
            else:
                d.fail(observed)
            source += 1
        wait = quote_wait is not None and quote_wait[0] <= at < quote_wait[1]
        if at >= next_cut:
            row = d.select(at, at)
            frame = None if wait or row is None else deepcopy(row)
            published += 1
            next_cut = at+cadence+(jitter if published % 2 else -jitter)
        ready = bool(not wait and frame and frame['ready']
                     and frame['observed_ts'] <= frame['decision_ts'] <= at
                     and 0 <= at-frame['cf_ts'] <= 5
                     and d.statuses[-1][1])
        if ready:
            observations.append((frame['cf_ts'], frame['observed_ts'], frame['decision_ts'], at))
        if at >= 20:
            qualified += ready
            checked += 1
    return dict(qualified=qualified, observed=checked, percent=100*qualified/checked,
                publication_count=published, causal_checks=observations)


def profit_namespace():
    rows = []
    env = frozen_functions(
        {'_start_profit_shadow', '_update_profit_shadow', '_profit_shadow_finalize'},
        datetime=datetime, timezone=timezone, print=lambda *a, **k: None,
        _profit_shadow_pending=[], PROFIT_SHADOW_ARM=.10, PROFIT_SHADOW_TARGET=.20,
        PROFIT_SHADOW_FLOOR=.06, PROFIT_SHADOW_TRAIL=.04,
        PROFIT_SHADOW_HORIZON_SECONDS=180., PROFIT_SHADOW_LOG='synthetic',
        PROFIT_SHADOW_FIELDS=[], append_csv=lambda p, f, r: rows.append(deepcopy(r)))
    env['rows'] = rows
    return env


def profit_counterexample(side='UP'):
    outputs = {}
    for cadence in (5, 1):
        env = profit_namespace()
        env['_start_profit_shadow'](dict(signal_id='engineering', contract='A', side=side,
                                         entry_ts=-10., signal_timestamp_utc='engineering', entry_ask=.30))
        for at in range(0, 6, cadence):
            env['_update_profit_shadow'](dict(contract='A', up_bid=.51, down_bid=.51),
                                          float(at), dict(ready=True, side=side))
        outputs[str(cadence)] = env['rows']
    return outputs


def proof_counterexample():
    # Exact same book; only the additional frame's decision identity changes.
    old = quote_proof(300000, 299000)
    fast = quote_proof(301000, 299000)
    old_result = replay(old, old['source_time'], 'A', 900000, 302000)
    try:
        replay(fast, old['source_time'], 'A', 900000, 302000)
    except ValueError as exc:
        return dict(old='PASS', faster='WAIT', reason=str(exc), old_quotes=old_result[0])
    raise AssertionError('Expected exact-frame join to fail closed')


def persistence_phase_counterexample():
    """Actual emitter reads BEFORE append; projection reads committed state.

    Avoiding extra appends alone does not preserve that evaluation phase.
    """
    env = frozen_functions(
        {'log_unified_subminute', '_unified_delta', '_unified_point_ago',
         '_unified_candidate_persistence', '_unified_reversal_state'},
        _unified_hist=deque(), UNIFIED_SUBMINUTE_LOG='synthetic',
        UNIFIED_SUBMINUTE_FIELDS=[], append_csv=lambda *a: None)
    h = AnchorHistory()
    snap = dict(up_ask=.4, down_ask=.6, up_bid=.39, down_bid=.59)
    fair = dict(up_fair=.96, down_fair=.04, side='UP', fair=.96, edge=.56)
    for at in (0, 5):
        rows = env['log_unified_subminute'](
            datetime.fromtimestamp(at, timezone.utc), at, 'A', 100000., 300.,
            100080., 80., snap, fair, None)
        h.commit(at, 'A')
    original = next(r for r in rows if r['side'] == 'UP')['candidate_persistence_30s']
    return dict(legacy_emitted_at_5=original,
                isolated_projection_at_6=h.project(6, 'A')['unified']['UP'],
                appended_micro_rows=0, new_market_information=False)


def actual_parity_counterexample(cadence):
    """Run deployed audit, with deterministic read-only adapters and clocks.

    This is a synthetic interleaving test, not a measured production incident.
    The independent BRTI read takes two seconds, crossing a candidate frame.
    """
    import btc15_kalshi_parity_shadow_v1 as parity
    from unittest.mock import patch
    ticker = 'KXBTC15M-ENGINEERING'
    stamp = lambda ts: datetime.fromtimestamp(ts, timezone.utc)
    old = quote_proof(300000, 299000, ticker)
    replacement = quote_proof(301000, 299000, ticker)
    selected = [old]
    m = dict(ticker=ticker, open_time=stamp(0).isoformat(), close_time=stamp(900).isoformat(),
             floor_strike=100000, yes_bid_dollars=.39, yes_ask_dollars=.41,
             no_bid_dollars=.59, no_ask_dollars=.61)
    row = dict(contract=ticker, _source_timestamp=stamp(300), _snapshot_complete=True,
               seconds_left=600, btc_price=100080, btc_gap=80, up_bid=.39, up_ask=.41,
               down_bid=.59, down_ask=.61)
    bot = dict(direct_brti=100080, brti_side='UP', brti_gap_to_target=80,
               target=100000, brti_timestamp_utc=stamp(299).isoformat(),
               brti_age_seconds=1, direct_brti_ready='true')
    def reference():
        if cadence == 1:
            selected[0] = replacement
        return [(stamp(299), 100080)]
    def validate(source_time, contract, close, checked):
        return replay(selected[0], source_time, contract, close, checked)
    rows = []
    with patch.dict(parity.os.environ, BTC15_KALSHI_QUOTE_PROVENANCE_CANARY='1'), \
            patch.object(parity, 'now_utc', side_effect=[stamp(300), stamp(300), stamp(302)]), \
            patch.object(parity, 'active_market', return_value=m), \
            patch.object(parity, 'latest_unified_snapshot', return_value=row), \
            patch.object(parity, 'logged_brti_at_snapshot', return_value=bot), \
            patch.object(parity, 'direct_brti_payload', side_effect=reference), \
            patch('btc15_kalshi_quote_provenance_v1.validate', side_effect=validate), \
            patch.object(parity, 'append', side_effect=lambda r: rows.append(r)), \
            patch('builtins.print'):
        parity.audit()
    return rows[0]
