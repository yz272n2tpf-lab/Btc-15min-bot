"""Sept 14 generalized / Sept 15 serial lifecycle on current causal provenance.

Signal only; immutable ASK, strictly later BID, +5c arm / 4c giveback EXIT.
No price band, confirmation gate, cooldown, count cap or horizon sell.
"""
from copy import deepcopy
from dataclasses import asdict
import os
from pathlib import Path

from btc15_ladder_journal_v1 import Worker, digest, SCHEMA
from btc15_recovered_exit_engine_v1 import Policy
from btc15_v2_product.scalp_policy import Lifecycle, proposal_for
from btc15_scalp_management_presentation_v1 import management_presentation
from btc15_position_context_v2 import context
from btc15_v81_qualified_inputs_v1 import require_qualified, epoch

CANDIDATE = 'BTC15_INTEGRATED_FINISH_20261006'
ROOT = Path(os.getenv('BTC15_LADDER_DATA_ROOT', '/data/btc15_ladders_v2'))
TARGETS = (8, 10, 15, 20, 30)
POLICY = Policy('GENERALIZED_SERIAL_ARM5_GIVEBACK4', arm=.05, giveback=.04)


def lane(prior_side, side, index):
    # Reused causal classification from scalp_reversal_reentry_ladder_v1._lane.
    if index <= 1 or not prior_side:
        return 'FIRST'
    return 'REENTRY_CONTINUATION' if side == prior_side else 'REVERSAL_RECROSS'


def later(q, previous, after):
    return (q['source_ts_ms']/1000 > after and q['source_ts_ms'] > previous['source_ts_ms']
            and q['validated_at_ms']/1000 > after
            and (q['epoch'] != previous['epoch'] or
                 (q['sid'] == previous['sid'] and q['sequence'] > previous['sequence'])))


class Scalp:
    def restore(self, saved):
        if saved and saved.get('candidate') != CANDIDATE:
            raise ValueError('SCALP_CHECKPOINT_CANDIDATE_MISMATCH')
        self.origin = saved.get('origin')
        self.path = saved.get('path', {})
        self.terminal = saved.get('terminal')
        self.contract = saved.get('contract')
        self.closed = saved.get('closed')
        self.last = saved.get('last')
        self.index = saved.get('index', 0)
        self.last_signal = saved.get('last_signal', {})
        self.confirm = {}  # Never carry half-confirmation across restart.
        self.engine = None
        if self.origin:
            self.path['missing'] = True
            self.engine = self._engine()
            self.engine.__dict__.update(saved.get('engine', {}))
        self.restarted = bool(saved)

    def _engine(self):
        o = self.origin
        return Lifecycle(POLICY, o['contract'], o['side'], o['original_ask'],
                         o['signal_ts'], o['signal_ts'], o['close_ts'])

    def checkpoint(self):
        engine = {k:v for k,v in self.engine.__dict__.items() if k != 'policy'} if self.engine else None
        return deepcopy(dict(candidate=CANDIDATE, origin=self.origin, path=self.path,
            terminal=self.terminal, contract=self.contract, closed=self.closed,
            last=self.last, index=self.index, last_signal=self.last_signal, engine=engine))

    def finish(self, reason, now, bid, q=None):
        o = self.origin
        self.terminal = dict(origin=deepcopy(o), path=deepcopy(self.path), reason=reason,
            state='EXIT' if reason=='ARM5_GIVEBACK4' else 'ENDED_UNARMED' if reason=='ENDED_UNARMED' else 'UNAVAILABLE',
            actionable_exit=reason=='ARM5_GIVEBACK4', signal_only=True, orders=False, ts=now,
            executable_exit_bid=bid, quote=deepcopy(q), observed_only=True,
            horizon_delay_seconds=max(0., now-o['deadline']),
            complete_path=not self.path['missing'], manual_fill=None, realized_profit=None)
        self.confirm.clear()
        return deepcopy(self.terminal)

    def process(self, f, now):
        record = dict(schema=SCHEMA, candidate=CANDIDATE, kind='SCALP_OBSERVATION',
            contract=f.get('contract'), published_ts=now, signal_only=True, orders=False)
        view = dict(candidate=CANDIDATE, build=os.getenv('RAILWAY_GIT_COMMIT_SHA'),
            published_ts=now, status='UNAVAILABLE', guidance='UNAVAILABLE',
            contract=f.get('contract'), origin=deepcopy(self.origin), signal_only=True,
            orders=False, manual_execution_only=True)
        if f.get('kind')=='SETTLEMENT':
            record.update(kind='SETTLEMENT',settlement=f['settlement'])
            return record,self.checkpoint(),view
        try:
            if f.get('kind') != 'SCALP_DECISION':
                raise ValueError(f.get('reason', 'SOURCE_UNAVAILABLE'))
            row = f['row']; p = require_qualified(row, now); q = p['quote']
            cut = row['ts']
            if not cut <= f['captured_ts'] <= now or now-cut > 3.5:
                raise ValueError('DECISION_CLOCK_UNQUALIFIED')
            require_qualified(row, cut)
            if self.last and cut <= self.last['cut']:
                raise ValueError('DUPLICATE_OR_OUT_OF_ORDER_DECISION')
            if self.last:
                prev=self.last['quote']
                if q['source_ts_ms']<prev['source_ts_ms']:
                    raise ValueError('QUOTE_TIME_ROLLBACK')
                if q['epoch']==prev['epoch']:
                    if q['sid']!=prev['sid'] or q['sequence']<prev['sequence']:
                        raise ValueError('QUOTE_SEQUENCE_ROLLBACK')
                    if q['sequence']==prev['sequence'] and any(q[k]!=prev[k] for k in ('source_ts_ms','up_bid','up_ask','down_bid','down_ask')):
                        raise ValueError('QUOTE_IDENTITY_CONFLICT')
            if self.closed and (p['close_ts'] < self.closed or
                    (p['close_ts'] == self.closed and row['ticker'] != self.contract)):
                raise ValueError('OLDER_OR_CONFLICTING_CONTRACT')
            continuity = ('OBSERVED' if self.last and not self.restarted and
                0 < cut-self.last['cut'] <= 6 else 'START_OR_MISSING_INTERVAL')
            self.restarted = False
            rollover = self.contract is not None and row['ticker'] != self.contract
            if rollover:
                if self.origin and not self.terminal:
                    self.path['missing'] = True
                    record['terminal'] = self.finish('CONTRACT_CLOSED_WITHOUT_EXECUTABLE_EXIT', now, None)
                self.origin = self.engine = self.terminal = None
                self.path = {}; self.confirm.clear(); self.index = 0; self.last_signal = {}
            self.contract, self.closed = row['ticker'], p['close_ts']
            if self.origin and self.origin['target'] != p['target']:
                raise ValueError('IMMUTABLE_TARGET_CONFLICT')
            if self.origin and not self.terminal:
                oq = self.path.get('last_quote') or self.origin['entry_provenance']['quote']
                if continuity != 'OBSERVED' or q['epoch'] != oq['epoch']:
                    self.path['missing'] = True
                if later(q, oq, self.origin['signal_ts']):
                    side = self.origin['side']; bid = q[side.lower()+'_bid']
                    gain = round(bid-self.origin['original_ask'], 10)
                    self.path['samples'] += 1
                    self.path['mfe'] = gain if self.path['mfe'] is None else max(gain, self.path['mfe'])
                    self.path['mae'] = gain if self.path['mae'] is None else min(gain, self.path['mae'])
                    hit = dict(ts=now, quote_source_ts=q['source_ts_ms']/1000, bid=bid,
                        delta_cents=gain*100, seconds_since_signal=now-self.origin['signal_ts'])
                    if gain <= -.10 and self.path['stop'] is None:
                        self.path['stop'] = dict(hit, targets_first=[t for t,h in self.path['targets'].items() if h])
                    for t in TARGETS:
                        if gain+1e-12 >= t/100 and self.path['targets'][str(t)] is None:
                            self.path['targets'][str(t)] = dict(hit, stop_first=self.path['stop'] is not None)
                    self.path.update(last_quote=deepcopy(q), current=hit,
                        giveback=max(0.,self.path['mfe']-gain))
                    record['later_bid'] = dict(hit, side=side, origin_id=self.origin['origin_id'], quote=q)
                    result = self.engine.update(dict(observed_ts=now, ticker=self.contract,
                        brti_source_ts=p['brti']['source_ts_ms']/1000,
                        quote_validated_at_observation=True, **{side.lower()+'_bid':bid}))
                    if result['status'] == 'EXIT':
                        record['terminal'] = self.finish('ARM5_GIVEBACK4', now, bid, q)
                        record['event'] = 'SCALP_EXIT'
                    elif result['status'] == 'ENDED_UNARMED':
                        record['terminal'] = self.finish('ENDED_UNARMED', now, None, q)
                        record['event'] = 'SCALP_ENDED_UNARMED'
                elif now >= self.origin['deadline'] and not self.engine.armed:
                    # A missing executable observation never completes the lane.
                    raise ValueError('HORIZON_WAITING_FOR_STRICTLY_LATER_EXECUTABLE_BID')

            # Terminal handoff requires a strictly later accepted quote. No
            # confirmation/cooldown/count cap from the V8.1 CORE/SURGE detector.
            can_enter = self.origin is None or (self.terminal and self.terminal['state'] in ('EXIT','ENDED_UNARMED'))
            after = self.terminal['ts'] if self.terminal else -1
            if can_enter and p['close_ts']-now>=120 and cut > after and q['source_ts_ms']/1000 > after:
                for side in ('UP', 'DOWN'):
                    proposal = proposal_for(row, side, f['proposals'][side].get('history', {}))
                    if not proposal['ok']:
                        continue
                    predecessor = self.terminal
                    self.index += 1
                    self.origin = dict(origin_id=digest([CANDIDATE,self.contract,side,now,q['epoch'],q['sequence']]),
                        contract=self.contract, side=side, signal_ts=now, decision_ts=cut,
                        original_ask=q[side.lower()+'_ask'], entry_provenance=deepcopy(p),
                        entry_features=deepcopy(proposal['features']), feature_provenance=deepcopy(proposal['history']), route='GENERALIZED',
                        target=p['target'], open_ts=p['open_ts'], close_ts=p['close_ts'],
                        deadline=min(now+POLICY.horizon,p['close_ts']), serial_index=self.index,
                        predecessor_id=(predecessor['origin']['origin_id'] if predecessor else None),
                        predecessor_exit_ts=(predecessor['ts'] if predecessor else None),
                        lane=lane(predecessor['origin']['side'] if predecessor else None,side,self.index), manual_fill=None)
                    self.path = dict(mfe=None, mae=None, samples=0, missing=False, last_quote=None,
                        targets={str(t):None for t in TARGETS}, stop=None, giveback=None, current=None)
                    self.terminal = None; self.engine = self._engine(); self.confirm.clear()
                    record.update(event='SCALP_SIGNAL', origin=deepcopy(self.origin), predecessor_exit=predecessor)
                    break

            guidance = 'PASS'; current_bid = None; movement = None; ctx = None; presentation = None
            if self.origin:
                side = self.origin['side']
                oq=self.origin['entry_provenance']['quote']
                current_bid = q[side.lower()+'_bid'] if later(q,oq,self.origin['signal_ts']) else None
                movement = current_bid-self.origin['original_ask'] if current_bid is not None else None
                ctx = context(side, p['close_ts']-now, btc=row['btc'], brti=row['brti'], target=p['target'],
                    giveback=bool(self.path.get('giveback',0) and self.path['giveback'] > 1e-12))
                presentation = asdict(management_presentation(state=self.terminal['state'] if self.terminal else 'ACTIVE',
                    peak_exec_gain=self.path['mfe'], exec_gain=(self.path.get('current') or {}).get('delta_cents',0)/100,
                    arm_gain=POLICY.arm, exit_giveback=POLICY.giveback))
                guidance = (('EXIT' if self.terminal['actionable_exit'] else 'PASS') if self.terminal else 'ENTER' if record.get('event') == 'SCALP_SIGNAL'
                    else 'PROTECT' if presentation['protection_armed'] else ctx['state'])
            self.last = dict(cut=cut, quote=deepcopy(q))
            record.update(provenance=p, proposals=f['proposals'] if not self.origin else None,
                origin_id=(self.origin or {}).get('origin_id'), guidance=guidance,
                path=deepcopy(self.path), continuity=continuity, context=ctx)
            view.update(status='AVAILABLE' if self.origin else 'PASS', guidance=guidance,
                origin=deepcopy(self.origin), path=deepcopy(self.path), terminal=deepcopy(self.terminal),
                contract=self.contract, target=p['target'], official_open=p['open_ts'], official_close=p['close_ts'],
                expires_at=min(p['close_ts'],q['source_ts_ms']/1000+6,p['brti']['source_ts_ms']/1000+5,
                    epoch(p['btc_source_utc'])+10, now+3.5),
                executable_current_bid=current_bid, movement_cents=None if movement is None else movement*100,
                context=ctx, presentation=presentation, policy=asdict(POLICY),
                trailing_trigger_bid=(self.origin['original_ask']+self.path['mfe']-POLICY.giveback
                    if presentation and presentation['protection_armed'] else None),
                exit_guidance=(dict(current_executable_bid=current_bid, trigger=deepcopy(self.terminal),
                    guaranteed_fill=False) if self.terminal and self.terminal['actionable_exit'] else None),
                lifecycle_state=self.terminal['state'] if self.terminal else ('ACTIVE' if self.origin else 'SCAN'),
                diagnostics=f.get('diagnostics', []), confirmation_counts={k:len(v) for k,v in self.confirm.items()},
                observed_target_cents=list(TARGETS), comparison_stop_cents=10,
                target_stop_authority='OBSERVATIONAL_ONLY', policy_evidence='SEPT14_GENERALIZED_SEPT15_SERIAL_MOVEMENT_NOT_SETTLEMENT_ACCURACY',
                continuity=continuity, input_provenance=p)
        except (ValueError, KeyError, TypeError) as exc:
            self.confirm.clear()
            if self.origin:
                self.path['missing'] = True
            record['unavailable_reason'] = str(exc); view['reason'] = str(exc)
            view['terminal'] = deepcopy(self.terminal)
        return record, self.checkpoint(), view


_worker = None

def start():
    global _worker
    if _worker is None:
        _worker = Worker(ROOT, 'v81', Scalp())
        _worker.start_settlements()

def offer(frame):
    if _worker is not None:
        return _worker.offer(deepcopy(frame))
