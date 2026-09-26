"""Two-clock informational boundary. No entry/lifecycle functions or native writes.

Only immutable JSON crosses this boundary. The fitted model and pure feature
builder live in the information process. All output fields are informational;
the existing action stream is neither consumed as a trigger nor republished.
"""
import ast
from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import threading

import numpy as np
import pandas as pd

from btc15_kalshi_quote_provenance_v1 import replay, MAX_AGE as QUOTE_AGE
from completion_audit.fair_input_candidate import frame_at_cut, price_at_or_before
from completion_audit.frozen_model_artifact import load_verified

ROOT = Path(__file__).resolve().parent
BOT = ROOT / 'bot_two_output_build_v4_13_profit_protection_shadow.py'
PR36_BLOB = 'f547ab4238592910ed76fee61870cd18714d09f0'
ARTIFACT = '1bf10e755fc81584bab3c3682b16103353f84582c27bb003664de883e7e7c816'
WEIGHTS = '95fc4e893c9032f29b9732d03c4a2e0cd62755ba93b36106a1d0c8c094520ba6'
INFO = 'INFORMATIONAL_READ_ONLY'
ACTION = 'AUTHORITATIVE_ACTION_STATE'
MAX_BYTES = 3 * 1024 * 1024
HEALTH_LEASE = 1.0  # Infrastructure revocation lease, not a predictive gate.
FIELDS = ('schema authority status reason signal_only orders frame_id anchor_id '
          'native_epoch native_decision_ts evaluated_ts published_ts checked_ts '
          'expires_at display_until ticker target btc_price btc_source_ts btc_received_ts '
          'brti_value brti_source_ts brti_received_ts brti_age_seconds brti_side '
          'quote_source_ts quote_received_ts up_bid up_ask down_bid down_ask '
          'probability_up probability_down model_flip_probability '
          'probability_up_change_since_native preferred_side brti_agrees '
          'btc_gap brti_gap range5 dist_over_range5 seconds_left '
          'artifact_sha256 weights_sha256 flip_risk_pct protection_phase five_minute_caution three_minute_guard').split()
FIELD_CLASSES = {name: INFO for name in FIELDS}
# These are existing-stream concepts; this API intentionally has no such fields.
AUTHORITATIVE_FIELDS = ('entry_id entry_price entry_time early_ready scalp_ready '
                        'final_ready persistence armed cooldown position_status '
                        'hold caution protect exit flip action').split()
AUTHORITY_CLASSES = {name: ACTION for name in AUTHORITATIVE_FIELDS}


class Unavailable(ValueError):
    pass


def pack(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(raw) > MAX_BYTES:
        raise Unavailable('FRAME_TOO_LARGE')
    return raw


def unpack(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise Unavailable('INVALID_FRAME_BYTES')
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise Unavailable('DUPLICATE_FIELD')
            obj[key] = value
        return obj
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(Unavailable('NONFINITE')))


def identity(raw):
    return hashlib.sha256(raw).hexdigest()


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise Unavailable('NONFINITE_NUMBER')
    return value


def exact(obj, fields):
    if not isinstance(obj, dict) or set(obj) != set(fields.split()):
        raise Unavailable('SCHEMA_MISMATCH')


def iso(at):
    return datetime.fromtimestamp(at, timezone.utc).isoformat()


def check_anchor(a):
    exact(a, 'schema epoch decision captured ticker opened closed target btc completed ticks probability_up artifact weights')
    if a['schema'] != 'BTC15_NATIVE_INFORMATION_ANCHOR_V1' or not isinstance(a['epoch'], str) or not a['epoch']:
        raise Unavailable('ANCHOR_OWNER')
    for name in ('decision', 'captured', 'opened', 'closed', 'target', 'probability_up'):
        number(a[name])
    if (not a['opened'] <= a['decision'] <= a['captured'] < a['closed']
            or a['closed']-a['opened'] != 900 or a['opened'] % 900
            or a['target'] <= 0 or not 0 <= a['probability_up'] <= 1):
        raise Unavailable('ANCHOR_CLOCK_OR_MARKET')
    if a['artifact'] != ARTIFACT or a['weights'] != WEIGHTS:
        raise Unavailable('MODEL_IDENTITY')
    exact(a['btc'], 'value source received')
    b = a['btc']
    if not 0 < number(b['value']) or not number(b['source']) <= number(b['received']) <= a['decision']:
        raise Unavailable('ANCHOR_BTC')
    if not isinstance(a['completed'], list) or not 1 <= len(a['completed']) <= 32:
        raise Unavailable('COMPLETED_BOUND')
    previous = -math.inf
    for row in a['completed']:
        if not isinstance(row, list) or len(row) != 7:
            raise Unavailable('COMPLETED_SCHEMA')
        t, source, op, high, low, close, volume = map(number, row)
        if not previous < t <= a['decision'] or source > t or min(op, high, low, close) <= 0 or volume < 0:
            raise Unavailable('COMPLETED_CAUSALITY')
        if high < max(op, low, close) or low > min(op, high, close):
            raise Unavailable('COMPLETED_OHLC')
        previous = t
    if not isinstance(a['ticks'], list) or not 1 <= len(a['ticks']) <= 4096:
        raise Unavailable('TICK_BOUND')
    previous = -math.inf
    for row in a['ticks']:
        if not isinstance(row, list) or len(row) != 3:
            raise Unavailable('TICK_SCHEMA')
        source, received, price = map(number, row)
        if not source <= received <= a['decision'] or received < previous or price <= 0:
            raise Unavailable('TICK_CAUSALITY')
        previous = received
    if a['ticks'][-1] != [b['source'], b['received'], b['value']]:
        raise Unavailable('BTC_ANCHOR_TICK_MISMATCH')


def check_health(h, a, frame, checked):
    exact(h, 'ready observed native_epoch anchor_id ticker brti_epoch quote_epoch')
    number(checked); number(h['observed'])
    if (h['ready'] is not True or not 0 <= checked-h['observed'] <= HEALTH_LEASE
            or h['native_epoch'] != a['epoch'] or h['anchor_id'] != frame['anchor_id']
            or h['ticker'] != a['ticker'] or h['brti_epoch'] != frame['brti']['epoch']
            or h['quote_epoch'] != frame['proof']['epoch']):
        raise Unavailable('SOURCE_HEALTH_OR_OWNER_CHANGED')


def validate(raw, health, checked):
    """Validate original source clocks at capture, publication AND every read."""
    f = unpack(raw)
    exact(f, 'schema anchor anchor_id cut brti proof quote_received')
    if f['schema'] != 'BTC15_INFORMATION_INPUT_V1':
        raise Unavailable('INPUT_SCHEMA')
    a = f['anchor']; check_anchor(a)
    if identity(pack(a)) != f['anchor_id']:
        raise Unavailable('ANCHOR_IDENTITY')
    cut = number(f['cut']); checked = number(checked)
    if not a['captured'] <= cut <= checked < a['closed']:
        raise Unavailable('INPUT_CLOCK_OR_ROLLOVER')
    exact(f['brti'], 'value source received epoch')
    b = f['brti']
    if (not isinstance(b['epoch'], str) or not b['epoch'] or number(b['value']) <= 0
            or not number(b['source']) <= number(b['received']) <= cut
            or not 0 <= checked-b['source'] <= 5.0):
        raise Unavailable('BRTI_STALE_OR_NONCAUSAL')
    btc = a['btc']
    if not 0 <= checked-btc['source'] <= 10.0:
        raise Unavailable('BTC_STALE_OR_NONCAUSAL')
    p = f['proof']
    if (not number(p['identity'][3])/1000 <= number(f['quote_received']) <= cut
            or not p['identity'][3] <= number(p['consumed_ms']) <= cut*1000):
        raise Unavailable('QUOTE_NONCAUSAL')
    quotes, _ = replay(p, iso(cut), a['ticker'], int(a['closed']*1000), int(checked*1000))
    # replay uses integer milliseconds; enforce the exact floating deadline too.
    if checked-p['identity'][3]/1000 > QUOTE_AGE or checked-p['consumed_ms']/1000 > QUOTE_AGE:
        raise Unavailable('QUOTE_STALE')
    check_health(health, a, f, checked)
    return f, quotes


def source_key(f, quotes):
    a, b, p = f['anchor'], f['brti'], f['proof']
    return (a['epoch'], a['ticker'], b['epoch'], p['epoch'],
            a['btc']['source'], a['btc']['value'], b['source'], b['value'],
            p['identity'][0], p['identity'][1], p['identity'][2], p['identity'][3], tuple(quotes),
            (a['opened'],a['closed'],a['target']))


def progress(old, new):
    """No poll/receipt/health/evaluation clock is a source novelty token."""
    if old is not None and old[:2] == new[:2] and old[13] != new[13]:
        raise Unavailable('FIXED_MARKET_CHANGED')
    if old is None or old[:4] != new[:4]:
        return True
    if new[8:10] != old[8:10]:
        # A new subscription must have its own connection epoch.
        raise Unavailable('QUOTE_SESSION_WITHOUT_EPOCH')
    for stamp, value in ((4, 5), (6, 7)):
        if new[stamp] < old[stamp] or (new[stamp] == old[stamp] and new[value] != old[value]):
            raise Unavailable('SOURCE_REGRESSION_OR_CONFLICT')
    if new[10] < old[10] or new[11] < old[11]:
        raise Unavailable('QUOTE_REGRESSION')
    if new[10] == old[10] and new[11:] != old[11:]:
        raise Unavailable('QUOTE_CLOCK_RENEWAL_OR_CONFLICT')
    # Sequenced acknowledgements can advance seq without a new market
    # timestamp or changed displayed book. They cannot justify re-evaluation.
    return (new[4] > old[4] or new[6] > old[6] or new[11] > old[11]
            or new[12] != old[12])


class FairAssessment:
    """Exactly the frozen pure feature arithmetic and fitted model; no gates."""
    def __init__(self):
        raw = BOT.read_bytes()
        if hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest() != PR36_BLOB:
            raise Unavailable('FROZEN_SOURCE_CHANGED')
        nodes = [n for n in ast.walk(ast.parse(raw)) if isinstance(n, ast.FunctionDef)
                 and n.name == '_fair_build_snapshot']
        if len(nodes) != 1:
            raise Unavailable('PURE_FEATURE_FUNCTION_MISSING')
        env = dict(pd=pd, np=np, _fair_price_at_or_before=price_at_or_before)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(BOT), 'exec'), env)
        self.build = env['_fair_build_snapshot']
        self.model = load_verified(ROOT/'completion_audit/model_artifact/frozen_fair_candidate.joblib',
                                   expected_artifact_sha256=ARTIFACT, expected_weights_sha256=WEIGHTS)

    def evaluate(self, f, quotes):
        # Match PR36's UTC datetime (microsecond) clock exactly. Constructing a
        # nanosecond Timestamp directly from float seconds introduces binary
        # rounding and fails pandas searchsorted on a microsecond candle index.
        a = f['anchor']; cut = pd.Timestamp(iso(f['cut']))
        rows = a['completed']
        completed = pd.DataFrame([r[2:] for r in rows], columns=['Open','High','Low','Close','Volume'],
                                 index=pd.to_datetime([iso(r[0]) for r in rows], utc=True))
        completed['source_utc'] = pd.to_datetime([iso(r[1]) for r in rows], utc=True)
        ticks = pd.DataFrame(a['ticks'], columns=['source_utc','observed_utc','price'])
        for field in ('source_utc','observed_utc'):
            ticks[field] = pd.to_datetime(ticks[field].map(iso), utc=True, format='ISO8601')
        # Disposable derived frame only. No fast sample, candle or feature survives.
        frame = frame_at_cut(completed, ticks, cut)
        opened = pd.Timestamp(iso(a['opened']))
        frame = frame.loc[frame.index >= opened-pd.Timedelta(minutes=6)]
        features = self.build(frame, opened, a['target'], _cut=cut)
        if features is None or not all(math.isfinite(v) for v in features.values()):
            raise Unavailable('FEATURE_SUPPORT_UNAVAILABLE')
        raw = float(self.model['forest'].predict_proba(pd.DataFrame([features])[self.model['features']])[0,1])
        flip = float(np.clip(self.model['sigmoid'].predict_proba(np.array([[raw]]))[0,1], .001, .999))
        up = 1-flip if features['current_side'] == 1 else flip
        preferred = 'UP' if up >= 1-up else 'DOWN'
        brti_side = 'UP' if f['brti']['value'] >= a['target'] else 'DOWN'
        return dict(probability_up=up, probability_down=1-up, model_flip_probability=flip,
                    probability_up_change_since_native=up-a['probability_up'], preferred_side=preferred,
                    brti_side=brti_side, brti_agrees=brti_side == preferred,
                    range5=features['range5'], dist_over_range5=features['dist_over_range5'])


def wait_view(checked, reason):
    out = dict.fromkeys(FIELDS)
    out.update(schema='BTC15_INFORMATION_V1', authority=INFO, status='WAIT', reason=reason,
               signal_only=True, orders=False, checked_ts=checked)
    return out


class InformationPublisher:
    """Single worker; immutable frames retained by exact hash; readers never evaluate."""
    def __init__(self, evaluator=None, retention=32):
        if type(retention) is not int or not 1 <= retention <= 256:
            raise ValueError('Invalid retention')
        self.evaluator = evaluator or FairAssessment()
        self.retention = retention
        self.frames = OrderedDict()
        self.latest = None
        self.key = None
        self.reason = 'STARTING'
        self.lock = threading.RLock()
        self.worker_lock = threading.Lock()
        self.last_check = -math.inf

    def unavailable(self, reason='INPUT_UNAVAILABLE'):
        with self.lock:
            self.latest = None
            self.reason = reason

    def offer(self, raw, health_reader, clock):
        with self.worker_lock:
            try:
                h = health_reader(); start = clock()
                f, quotes = validate(raw, h, start)
                key = source_key(f, quotes)
                with self.lock:
                    if not progress(self.key, key):
                        return False
                values = self.evaluator.evaluate(f, quotes)
                if set(values) != set(('probability_up probability_down model_flip_probability '
                                      'probability_up_change_since_native preferred_side brti_side brti_agrees '
                                      'range5 dist_over_range5').split()):
                    raise Unavailable('ASSESSMENT_SCHEMA')
                h = health_reader(); published = clock()
                validate(raw, h, published)  # Includes inference and health-read latency.
                a = f['anchor']; b = f['brti']; p = f['proof']
                out = wait_view(published, 'QUALIFIED_INFORMATION_ONLY')
                out.update(status='AVAILABLE', anchor_id=f['anchor_id'], native_epoch=a['epoch'],
                           native_decision_ts=a['decision'], evaluated_ts=f['cut'], published_ts=published,
                           expires_at=min(a['closed'], b['source']+5, a['btc']['source']+10,
                                          p['identity'][3]/1000+QUOTE_AGE, p['consumed_ms']/1000+QUOTE_AGE),
                           ticker=a['ticker'], target=a['target'], btc_price=a['btc']['value'],
                           btc_source_ts=a['btc']['source'], btc_received_ts=a['btc']['received'],
                           brti_value=b['value'], brti_source_ts=b['source'], brti_received_ts=b['received'],
                           brti_age_seconds=published-b['source'], quote_source_ts=p['identity'][3]/1000,
                           quote_received_ts=f['quote_received'], up_bid=quotes[0], up_ask=quotes[1],
                           down_bid=quotes[2], down_ask=quotes[3], btc_gap=a['btc']['value']-a['target'],
                           brti_gap=b['value']-a['target'], seconds_left=a['closed']-published,
                           artifact_sha256=ARTIFACT, weights_sha256=WEIGHTS,
                           flip_risk_pct=100*values['model_flip_probability'],
                           protection_phase=('3M_GUARD' if a['closed']-published <= 180 else
                                             '5M_CAUTION' if a['closed']-published <= 300 else 'NORMAL'),
                           five_minute_caution=bool(a['closed']-published <= 300),
                           three_minute_guard=bool(a['closed']-published <= 180), **values)
                # Identity commits the complete immutable source bundle and evaluation.
                out['display_until'] = min(out['expires_at'], h['observed']+HEALTH_LEASE)
                frame_id = identity(pack(dict(input_sha256=identity(raw), output=out)))
                out['frame_id'] = frame_id
                encoded = pack(out)
                with self.lock:
                    self.frames[frame_id] = (raw, encoded)
                    while len(self.frames) > self.retention:
                        self.frames.popitem(last=False)
                    self.latest, self.key, self.reason = frame_id, key, 'QUALIFIED_INFORMATION_ONLY'
                return True
            except (ValueError, KeyError, TypeError, IndexError, OverflowError) as exc:
                self.unavailable(str(exc) if isinstance(exc, Unavailable) else 'INVALID_INPUT')
                return False

    def read(self, health, checked, frame_id=None):
        with self.lock:
            if checked < self.last_check:
                self.latest = None
                self.reason = 'CLOCK_REGRESSION'
                return wait_view(checked, self.reason)
            self.last_check = checked
            selected = self.latest if frame_id is None else frame_id
            saved = self.frames.get(selected)
            reason = self.reason if frame_id is None else 'FRAME_NOT_RETAINED'
        if saved is None:
            return wait_view(checked, reason)
        try:
            f, _ = validate(saved[0], health, checked)
            out = unpack(saved[1])
            if checked < out['published_ts']:
                raise Unavailable('PUBLICATION_IN_FUTURE')
            out.update(checked_ts=checked, brti_age_seconds=checked-f['brti']['source'],
                       seconds_left=f['anchor']['closed']-checked,
                       display_until=min(out['expires_at'],health['observed']+HEALTH_LEASE))
            return out
        except (ValueError, KeyError, TypeError, IndexError, OverflowError) as exc:
            return wait_view(checked, str(exc) if isinstance(exc, Unavailable) else 'INVALID_INPUT')
