"""Offline complete-loop equivalence lab. Never imported by production.

Uses the pinned PR36 loop/functions and fitted artifact, not a reimplementation
of their arithmetic. All external effects terminate in in-memory test adapters.
The immutable frame store is an engineering component, not a live publisher.
SIGNAL ONLY / NO ORDERS.
"""
import ast
from collections import deque
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import threading
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from btc15_brti_delivery_v1 import Delivery
from btc15_kalshi_quote_provenance_v1 import replay
from completion_audit.cadence_projection_probe_v1 import BOT, FROZEN_BLOB, profit_namespace
from completion_audit.fair_input_candidate import frame_at_cut, price_at_or_before
from completion_audit.frozen_model_artifact import load_verified

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_SHA = '1bf10e755fc81584bab3c3682b16103353f84582c27bb003664de883e7e7c816'
WEIGHTS_SHA = '95fc4e893c9032f29b9732d03c4a2e0cd62755ba93b36106a1d0c8c094520ba6'

# Explicitly includes state outside the visible strategy histories. A snapshot
# of model objects is private too: serial prediction is not assumed immutable.
STATE_NAMES = (
    'history', 'pending', 'last_event_created', 'active_ticker',
    '_ec_btc_ticks', '_early_hist', '_unified_hist',
    '_true_scalp_pending', '_true_scalp_last_signal', '_profit_shadow_pending',
    '_brti_samples', '_brti_conflicting_seconds', '_brti_last_error',
    '_brti_last_error_print', '_brti_fetch_epoch', '_brti_finalized_contracts',
    '_brti_failed_contracts', '_brti_pending_contracts', '_btc_spot_provenance',
    'iteration', 'running', '_fair_btc', '_fair_ready', '_fair_features',
    '_fair_rf', '_fair_sigmoid', '_fair_model_weights_sha256',
    '_fair_model_artifact_sha256', '_true_scalp_model', '_true_scalp_medians',
    '_true_scalp_ready',
)
DELIVERY_NAMES = ('states', 'statuses', 'seen', 'epoch')
FUNCTION_NAMES = {
    'parse_dt', 'num', 'extract_target', 'point_ago', 'rows_since', 'delta', 'low_high',
    'maybe_create_event', 'update_pending', 'finalize_event',
    '_ec_append_btc_tick', '_ec_live_ticks', '_live_fair_shadow',
    '_fair_build_snapshot', '_fair_parse_contract_times',
    '_early_point_ago', '_early_delta', '_candidate_flag', 'log_early_conf_shadow',
    '_unified_point_ago', '_unified_delta', '_unified_candidate_persistence',
    '_unified_reversal_state', 'log_unified_subminute',
    '_start_profit_shadow', '_profit_shadow_finalize', '_update_profit_shadow',
    '_true_scalp_live_features', '_true_scalp_probability', '_maybe_true_scalp_signal',
    '_finalize_true_scalp', '_update_true_scalp_pending',
    '_merge_brti_publications', '_retain_brti_window', '_store_brti_publications',
    '_latest_brti', '_brti_contract_snapshot', '_log_brti_parity',
    '_track_brti_contract', '_retry_brti_closeouts', '_try_finalize_brti_contract',
}


def oracle_ast():
    raw = BOT.read_bytes()
    if hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest() != FROZEN_BLOB:
        raise ValueError('PR36 oracle byte identity changed')
    return ast.parse(raw)


def stable(value):
    """Comparable snapshot including actual tree/calibrator arrays."""
    if isinstance(value, dict):
        return tuple(sorted(((stable(k), stable(v)) for k, v in value.items()), key=repr))
    if isinstance(value, (list, tuple, deque)):
        return tuple(stable(v) for v in value)
    if isinstance(value, set):
        return tuple(sorted((stable(v) for v in value), key=repr))
    if isinstance(value, pd.DataFrame):
        return (tuple(value.columns), tuple(value.index.astype(str)), stable(value.to_numpy().tolist()))
    if isinstance(value, pd.Series):
        return (tuple(value.index), stable(value.to_list()))
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        # Structured sklearn node arrays contain uninitialized alignment bytes;
        # compare every named field, never allocator padding.
        if value.dtype.names:
            return tuple((name, stable(value[name])) for name in value.dtype.names)
        return (str(value.dtype), value.shape, hashlib.sha256(value.tobytes()).hexdigest())
    if hasattr(value, 'estimators_'):
        return (stable(value.get_params()), tuple(stable(e.tree_.__getstate__()) for e in value.estimators_))
    if hasattr(value, 'coef_'):
        return stable((value.coef_, value.intercept_, value.classes_))
    if isinstance(value, float) and math.isnan(value):
        return 'NaN'
    return value


class FrozenRuntime:
    """Execute exactly one iteration of the original while loop per step.

    Only effects are adapted: network inputs, clocks, file sinks and sleep.
    Logic inside the pinned loop and its decision/lifecycle functions is intact.
    This is sequential and offline; patching modules is NOT runtime isolation.
    """
    def __init__(self, completed):
        tree = oracle_ast()
        self.tree = tree
        self.records, self.inputs, self.messages, self.diag, self.saves = [], [], [], [], []
        self.at = 0.
        self.ns = dict(pd=pd, np=np, math=math, re=re, ZoneInfo=ZoneInfo,
                       timezone=timezone, timedelta=timedelta, json=json)
        # Read literal constants from the oracle; no copied threshold table.
        for node in tree.body:
            if isinstance(node, ast.Assign):
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.ns[target.id] = deepcopy(value)
        functions = [node for node in ast.walk(tree)
                     if isinstance(node, ast.FunctionDef) and node.name in FUNCTION_NAMES]
        if {node.name for node in functions} != FUNCTION_NAMES:
            raise ValueError('Incomplete oracle function set')
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(BOT), 'exec'), self.ns)
        loop = next(node for node in tree.body if isinstance(node, ast.While)
                    and isinstance(node.test, ast.Name) and node.test.id == 'running')
        self.loop = compile(ast.Module(body=[loop], type_ignores=[]), str(BOT), 'exec')
        model = load_verified(ROOT / 'completion_audit/model_artifact/frozen_fair_candidate.joblib',
                              expected_artifact_sha256=ARTIFACT_SHA,
                              expected_weights_sha256=WEIGHTS_SHA)
        for name in ('history', '_ec_btc_ticks', '_early_hist', '_unified_hist'):
            self.ns[name] = deque()
        for name in ('pending', '_true_scalp_pending', '_profit_shadow_pending'):
            self.ns[name] = []
        for name in ('last_event_created', '_true_scalp_last_signal', '_brti_pending_contracts'):
            self.ns[name] = {}
        for name in ('_brti_conflicting_seconds', '_brti_finalized_contracts', '_brti_failed_contracts'):
            self.ns[name] = set()
        self.ns.update(
            _brti_samples=deque(maxlen=600), _brti_delivery=Delivery(),
            _brti_lock=threading.RLock(), _brti_last_error=None,
            _brti_last_error_print=0., _brti_fetch_epoch='engineering',
            BRTI_CLOSEOUT_RECOVERY_SECONDS=600, _btc_spot_provenance=None,
            active_ticker=None, iteration=0, running=True,
            _fair_btc=deepcopy(completed), _fair_ready=True,
            _fair_rf=model['forest'], _fair_sigmoid=model['sigmoid'],
            _fair_features=list(model['features']),
            _fair_model_artifact_sha256=ARTIFACT_SHA,
            _fair_model_weights_sha256=WEIGHTS_SHA,
            _fair_frame_at_cut=frame_at_cut,
            _fair_price_at_or_before=price_at_or_before,
            _fair_months={m:i+1 for i,m in enumerate(
                ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'])},
            _true_scalp_ready=False, _true_scalp_model=None, _true_scalp_medians=None,
        )
        for name in ('SNAPSHOT_LOG','EVENT_LOG','EARLY_CONF_LOG','UNIFIED_SUBMINUTE_LOG',
                     'PROFIT_SHADOW_LOG','TRUE_SCALP_LOG','BRTI_PARITY_LOG'):
            self.ns[name] = name
        self._adapters()

    def _adapters(self):
        owner = self
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                value = datetime.fromtimestamp(owner.at, timezone.utc)
                return value if tz is None else value.astimezone(tz)
        def sleep(seconds):
            self.ns['running'] = False
        self.ns.update(
            datetime=Clock,
            time=SimpleNamespace(time=lambda: self.at, sleep=sleep),
            os=SimpleNamespace(getenv=lambda key, default='': '1' if key == 'BTC15_KALSHI_QUOTE_PROVENANCE_CANARY' else default),
            print=lambda *args, **kwargs: self.messages.append(' '.join(map(str, args))),
            append_csv=lambda path, fields, row: self.records.append((str(path), deepcopy(row))),
            save_state=lambda: self.saves.append(self.ns['iteration']),
            rollover_diag=SimpleNamespace(emit=lambda *a, **k: self.diag.append((a, k))),
            _btc15_data_path=lambda path: Path('/never-written') / path,
        )

    def data_bindings(self):
        # Top-level loop temporaries are module globals, so retain them too.
        import types
        excluded = {'pd','np','math','re','ZoneInfo','timezone','timedelta','json',
                    '_brti_lock','_brti_delivery','__builtins__','os','time',
                    'rollover_diag','datetime'}
        return {name: value for name, value in self.ns.items()
                  if name not in excluded and not callable(value)
                  and not isinstance(value, (types.ModuleType, type))}

    def snapshot(self):
        result = deepcopy(self.data_bindings())
        if not set(STATE_NAMES).issubset(result):
            raise ValueError('State inventory is incomplete')
        result['_delivery'] = {name: deepcopy(getattr(self.ns['_brti_delivery'], name))
                               for name in DELIVERY_NAMES}
        return result

    def restore(self, snapshot):
        copied = deepcopy(snapshot)
        delivery = copied.pop('_delivery')
        for name in set(self.data_bindings()) - set(copied):
            del self.ns[name]
        self.ns.update(copied)
        self.ns['_brti_delivery'] = Delivery()
        for name, value in delivery.items():
            setattr(self.ns['_brti_delivery'], name, value)

    def fork(self):
        child = object.__new__(FrozenRuntime)
        child.tree, child.loop = self.tree, self.loop
        child.records, child.inputs, child.messages, child.diag, child.saves = [], [], [], [], []
        child.at = self.at
        child.ns = dict(self.ns)
        child.restore(self.snapshot())
        child.ns['_brti_lock'] = threading.RLock()
        # Rebind every function to the private namespace; deepcopy(function)
        # alone would leave its __globals__ pointing back to the legacy writer.
        import types
        for name in FUNCTION_NAMES:
            fn = self.ns[name]
            child.ns[name] = types.FunctionType(fn.__code__, child.ns, fn.__name__, fn.__defaults__)
        child._adapters()
        return child

    def step(self, inputs):
        self.at = inputs['decision']
        self.records, self.inputs, self.messages, self.diag, self.saves = [], [], [], [], []
        self.ns['running'] = True
        self.ns['get_active_market'] = lambda: deepcopy(inputs['market'])
        def spot():
            self.ns['_btc_spot_provenance'] = dict(source_utc=inputs['btc_source'],
                                                 observed_utc=inputs['btc_received'])
            return inputs['btc']
        self.ns['get_btc_spot'] = spot
        for receipt in inputs.get('brti_receipts', []):
            self.ns['_brti_delivery'].accept(*receipt)
            self.ns['_store_brti_publications']([(receipt[1], receipt[0])])
        if inputs.get('brti_error'):
            self.ns['_brti_delivery'].fail(self.at)
        def consume(ticker, source_time, close_ms):
            if inputs.get('quote_wait'):
                return None
            return replay(inputs['proof'], source_time, ticker, close_ms, int(self.at*1000))[0]
        def record_input(path, **row):
            self.inputs.append(deepcopy(row))
        with patch('btc15_kalshi_quote_provenance_v1.consume', side_effect=consume), \
                patch('btc15_decision_clock_v1.record_model_input', side_effect=record_input):
            exec(self.loop, self.ns)
        return deepcopy(dict(records=self.records, inputs=self.inputs,
                             messages=self.messages, saves=self.saves))


def newer_identity(inputs):
    """Actual source observations, never decision/poll timestamp as novelty."""
    proof = inputs['proof']
    brti = inputs.get('brti_receipts', [])
    return stable((inputs['market']['ticker'], inputs['btc_source'], inputs['btc'],
                   proof['epoch'], proof['identity'], brti[-1][0:2] + (brti[-1][3],) if brti else None))


class PhaseProjection:
    """Replacement of the latest legacy evaluation slot, never a new hit.

    Kept research-only: replacing a slot changes the interpretation of rolling
    history for extra decisions. The tests explicitly expose that limitation.
    """
    def __init__(self, runtime):
        self.runtime = runtime
        self.before = None
        self.anchor = None
        self.seen = set()

    def legacy(self, inputs):
        self.before = self.runtime.snapshot()
        self.anchor = deepcopy(inputs)
        self.seen = {newer_identity(inputs)}
        return self.runtime.step(inputs)

    def extra(self, inputs):
        if self.anchor is None or inputs['decision'] <= self.anchor['decision']:
            raise ValueError('Extra requires a strictly earlier legacy anchor')
        if inputs['market']['ticker'] != self.anchor['market']['ticker']:
            raise ValueError('Rollover belongs to legacy authority')
        identity = newer_identity(inputs)
        if identity in self.seen:
            return None
        child = self.runtime.fork()
        child.restore(self.before)
        result = child.step(inputs)
        self.seen.add(identity)
        return result, child.snapshot()


class ImmutableFrames:
    """Content-addressed atomic in-memory handoff with bounded retention.

    Readers retain bytes for their captured identity. A newer publication can
    never replace that proof. Eviction fails closed, never falls back to latest.
    Disk/network integration and independent parity transport remain separate.
    """
    def __init__(self, limit=128):
        if type(limit) is not int or limit < 1:
            raise ValueError('Positive retention bound required')
        self.limit = limit
        self.lock = threading.RLock()
        self.frames = {}
        self.latest = None

    def publish(self, frame):
        raw = json.dumps(frame, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        if len(raw) > 4*1024*1024:
            raise ValueError('Frame size bound')
        identity = hashlib.sha256(raw).hexdigest()
        with self.lock:
            self.frames[identity] = raw
            self.latest = identity
            while len(self.frames) > self.limit:
                del self.frames[next(iter(self.frames))]
        return identity

    def capture(self, identity=None):
        with self.lock:
            identity = self.latest if identity is None else identity
            raw = self.frames[identity]
        return identity, raw

    @staticmethod
    def validate(captured, checked, health=None):
        identity, raw = captured
        if hashlib.sha256(raw).hexdigest() != identity:
            raise ValueError('Frame content identity mismatch')
        frame = json.loads(raw)
        at = frame['decision']
        if not frame['opened'] <= at <= checked < frame['closed']:
            raise ValueError('Frame outside original market window')
        if frame['closed']-frame['opened'] != 900 or frame['opened'] % 900:
            raise ValueError('Official window required')
        brti = frame['brti']
        if health is None or (not health['ready'] or health['epoch'] != brti['epoch']
                              or health['observed'] > checked):
            raise ValueError('Current primary source unavailable or owner changed')
        if (not brti['ready'] or not brti['epoch']
                or not brti['source'] <= brti['received'] <= at
                or not 0 <= checked-brti['source'] <= 5):
            raise ValueError('BRTI unavailable, noncausal or expired')
        btc = frame['btc']
        if not btc['source'] <= btc['received'] <= at or checked-btc['source'] > 10:
            raise ValueError('BTC unavailable, noncausal or expired')
        proof = frame['proof']
        if proof['consumed_ms'] > at*1000 or proof['identity'][3] > at*1000:
            raise ValueError('Quote unavailable by decision')
        quotes, _ = replay(proof, datetime.fromtimestamp(at, timezone.utc).isoformat(),
                           frame['ticker'], int(frame['closed']*1000), int(checked*1000))
        if tuple(frame['quotes']) != quotes:
            raise ValueError('Quote frame mismatch')
        rows = frame['rows']
        if (len(rows) != 2 or {r['side'] for r in rows} != {'UP', 'DOWN'}
                or any(r['contract'] != frame['ticker'] or r['decision'] != at for r in rows)):
            raise ValueError('Incomplete paired decision')
        if frame['model']['artifact'] != ARTIFACT_SHA or frame['model']['weights'] != WEIGHTS_SHA:
            raise ValueError('Frozen model identity mismatch')
        return frame


class NoAppendDeque(deque):
    """Projection-only view: existing evidence ages, no current hit is added."""
    def append(self, value):
        pass

    def __deepcopy__(self, memo):
        # deque's default reconstruction calls append(), intentionally disabled
        # here. Reconstruct through the iterable constructor to retain evidence.
        copied = type(self)(deepcopy(list(self), memo))
        memo[id(self)] = copied
        return copied


class PhaseLatchProjection(PhaseProjection):
    """Separate history visibility from each emitter's persistence phase.

    Original sampled market extrema and BTC ticks remain visible. EARLY counts
    its latest committed sample; unified counts only the samples visible before
    its last legacy append. No extra sample enters either count. Lifecycle
    changes produced by the isolated loop remain counterfactual, not connected
    signals. This class intentionally does not claim that problem is solved.
    """
    def extra(self, inputs):
        if self.anchor is None or inputs['decision'] <= self.anchor['decision']:
            raise ValueError('Extra requires a strictly earlier legacy anchor')
        if inputs['market']['ticker'] != self.anchor['market']['ticker']:
            raise ValueError('Rollover belongs to legacy authority')
        identity = newer_identity(inputs)
        if identity in self.seen:
            return None
        child = self.runtime.fork()
        child.ns['_early_hist'] = NoAppendDeque(child.ns['_early_hist'])
        child.ns['_unified_hist'] = NoAppendDeque(child.ns['_unified_hist'])
        before = deepcopy(self.before['_unified_hist'])
        def persistence(contract, side, now):
            return sum(bool(row['broad_candidate']) for row in before
                       if row['contract']==contract and row['side']==side and 0<=now-row['ts']<=30)
        child.ns['_unified_candidate_persistence'] = persistence
        result = child.step(inputs)
        self.seen.add(identity)
        return result, child.snapshot()


def derive_companion_profit(origin, legacy_tape, cut):
    """Rebuild one immutable origin on ORIGINAL committed lifecycle ticks.

    This solves forgetting a companion's entry without using extra evaluations
    as lifecycle ticks. It does not solve arbitration against native cooldowns,
    nor promote the frozen SHADOW protection routine to live action authority.
    """
    if cut < origin['entry_ts']:
        raise ValueError('Origin is not yet causal')
    env = profit_namespace()
    env['_start_profit_shadow'](deepcopy(origin))
    prior = None
    for frame in legacy_tape:
        when = frame['decision']
        if prior is not None and when <= prior:
            raise ValueError('Legacy tape must have unique ordered commits')
        prior = when
        if origin['entry_ts'] < when <= cut:
            env['_update_profit_shadow'](deepcopy(frame['snap']), when, deepcopy(frame['brti']))
    return deepcopy(dict(pending=env['_profit_shadow_pending'], exits=env['rows']))
