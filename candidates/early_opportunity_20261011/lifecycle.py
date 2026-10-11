"""Offline EARLY reducer composed from existing pure reducers; never a worker.

FINAL is evaluated unchanged. Existing consensus/value exits stay with EARLY.
New settlement/plan warnings are descriptive WATCH episodes, not new EXIT rules.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone

from btc15_v2_product import directional as base
from btc15_v2_product.early_entry import assess, route
from btc15_v2_product.early_management import decide
from btc15_v2_product.directional_authority import reduce_signal, manager, encode_state, decode_state
from .qualification import POLICY, EvidenceRegistry, digest, qualify_opportunity, settlement_context, validate_quote


class Candidate:
    def __init__(self, registry=None):
        self.registry = registry or EvidenceRegistry()
        self.state = manager.State(); self.origin = None; self.terminal = None
        self.history = []; self.last = None; self.prior_p = None
        self.path = {}; self.reentry_reset = False; self.watch_episode = None
        self.used_evidence = set()

    def checkpoint(self):
        return deepcopy(dict(policy=POLICY, state=encode_state(self.state), origin=self.origin,
            terminal=self.terminal, history=self.history, last=self.last, prior_p=self.prior_p,
            path=self.path, reentry_reset=self.reentry_reset, watch_episode=self.watch_episode,
            used_evidence=sorted(self.used_evidence)))

    def restore(self, value):
        if value.get('policy') != POLICY:
            raise ValueError('CANDIDATE_CHECKPOINT_IDENTITY')
        state = decode_state(value['state']); origin = value['origin']; terminal = value['terminal']
        if bool(state.position) != bool(origin):
            raise ValueError('ORIGIN_CHECKPOINT_CONFLICT')
        if origin and (origin['side'] != state.position.side or
            origin['original_ask'] != state.position.entry_ask or
            origin['contract'] != state.position.contract_id or
            origin['origin_id'] != digest([POLICY, origin['contract'], origin['entry_key'], origin['side']])):
            raise ValueError('ORIGIN_CHECKPOINT_CONFLICT')
        if terminal and (not origin or terminal.get('origin_id') != origin['origin_id'] or
            terminal.get('side') != origin['side'] or terminal.get('contract') != origin['contract'] or
            terminal.get('original_ask') != origin['original_ask'] or terminal.get('state') != 'EXIT'):
            raise ValueError('TERMINAL_CHECKPOINT_CONFLICT')
        self.state = state
        for key in ('origin','terminal','history','last','prior_p','path','reentry_reset','watch_episode'):
            setattr(self,key,deepcopy(value[key]))
        self.used_evidence = set(value['used_evidence'])

    def process(self, f, now, prediction=None):
        before = self.checkpoint()
        out = dict(policy=POLICY, mode='OFFLINE_CANDIDATE', signal_only=True, orders=False,
                   actionable=False, event=None, guidance='UNAVAILABLE', final=None)
        try:
            if f.get('kind') != 'NATIVE_DECISION':
                raise ValueError('NATIVE_DECISION_REQUIRED')
            expires = base.qualify(f, now)
            key = [f['native_epoch'], f['native_sequence']]
            if self.last and (f['captured_ts'] <= self.last['at'] or
                key[0] == self.last['key'][0] and key[1] <= self.last['key'][1]):
                raise ValueError('DUPLICATE_OR_OUT_OF_ORDER_DECISION')
            raw, qualified = base.protected_frame(f, now)
            out['final'] = deepcopy(raw['final'])  # Independent unchanged gates.
            validate_quote(f)
            q=f['quote'];new_book=True
            if self.last and self.last.get('quote'):
                pq=self.last['quote']
                if q['epoch']==pq['epoch'] and q['sid']==pq['sid']:
                    if q['seq']<pq['seq'] or q['exchange_ts_ms']<pq['exchange_ts_ms']:
                        raise ValueError('QUOTE_ROLLBACK')
                    if q['seq']==pq['seq']:
                        if q['quotes']!=pq['quotes'] or q['exchange_ts_ms']!=pq['exchange_ts_ms']:
                            raise ValueError('CONFLICTING_QUOTE_SEQUENCE')
                        new_book=False
            old = assess(raw, f); native_ready = old['ready']
            raw, qualified = route(raw, qualified, old)
            opportunity = qualify_opportunity(f, now, prediction, self.registry)
            out['opportunity'] = opportunity
            raw['early']['conditions']['opportunity_integrity'] = opportunity['ready']
            raw['early']['ready'] = all(raw['early']['conditions'].values())
            if raw['early'].get('qualification'):
                raw['early']['qualification']['conditions'] = deepcopy(raw['early']['conditions'])
                raw['early']['qualification']['ready'] = raw['early']['ready']
            qualified['lanes']['early']['publication_eligible'] = raw['early']['ready']
            if self.origin and self.origin['contract'] != f['contract']:
                if f['official_close'] <= self.origin['official_close']:
                    raise ValueError('OLDER_CONTRACT')
                self.history.append(dict(origin=deepcopy(self.origin),terminal=deepcopy(self.terminal),status='HISTORICAL'))
                self.origin = None; self.terminal = None; self.path = {}; self.watch_episode = None
                self.reentry_reset = False
            if self.origin and f['target'] != self.origin['target']:
                raise ValueError('IMMUTABLE_TARGET_CONFLICT')
            continuous = bool(self.last and key[0] == self.last['key'][0] and f['captured_ts']-self.last['at'] <= 15)
            if self.terminal:
                # Outage/missing profile alone cannot manufacture a new setup.
                quality_keys=('verified_model','causal_model_features','current_series_fees',
                              'two_sided_execution','observed_execution_runway')
                native_reset = not native_ready and all(old['conditions'][k] for k in quality_keys)
                if native_reset:
                    self.reentry_reset = True
                if (raw['early']['ready'] and self.reentry_reset and continuous and new_book and
                    opportunity.get('prediction_sha256') not in self.used_evidence):
                    self.history.append(dict(origin=deepcopy(self.origin),terminal=deepcopy(self.terminal),status='CLOSED_RECOMMENDATION'))
                    self.state = replace(self.state,position=None,buy_emitted=False)
                    self.origin = None; self.terminal = None; self.path = {}; self.watch_episode = None
                    self.reentry_reset = False
            next_state, event, status, _ = reduce_signal(self.state, raw, qualified, datetime.fromtimestamp(now,timezone.utc))
            if event == 'BUY':
                side = raw['early']['side']
                self.origin = dict(origin_id=digest([POLICY,f['contract'],key,side]),entry_key=key,
                    contract=f['contract'], target=f['target'], official_close=f['official_close'],
                    side=side, original_ask=f[side.lower()+'_ask'], signal_ts=now,
                    entry_provenance=deepcopy(f), qualification=deepcopy(old),
                    opportunity=deepcopy(opportunity), manual_fill=None, realized_profit=None)
                self.path = dict(mfe=None,last_quote=deepcopy(f['quote']))
                self.prior_p = f['fair'][side.lower()+'_fair']
                self.used_evidence.add(opportunity['prediction_sha256'])
                self.reentry_reset = False
            guidance = 'PASS'; management = None
            if self.origin:
                o = self.origin; side=o['side']; q=f['quote']; previous=self.path['last_quote']
                later = (q['exchange_ts_ms']/1000 > o['signal_ts'] and q['exchange_ts_ms'] > previous['exchange_ts_ms'] and
                         q['epoch'] == previous['epoch'] and q['sid'] == previous['sid'] and q['seq'] > previous['seq'])
                if q['epoch'] != previous['epoch'] or q['sid'] != previous['sid']:
                    # Rebase continuity; this first post-gap quote cannot create EXIT.
                    self.path['last_quote'] = deepcopy(q)
                if later:
                    movement=f[side.lower()+'_bid']-o['original_ask']
                    self.path['mfe']=movement if self.path['mfe'] is None else max(self.path['mfe'],movement)
                    self.path['last_quote']=deepcopy(q)
                management=decide(f,o,self.prior_p,self.path,next_state.position.action.value,later,self.terminal)
                self.terminal=management['terminal']; guidance=management['state']
                ev=management['evidence']
                corroboration=(ev['model_opposes'] or ev['btc_held_side_gap']<=0 or
                    ev['brti_held_side_gap']<=0 or ev['recent_momentum_adverse'] or
                    ev['trend_adverse'] or ev['observed_bid_giveback'] or
                    not ev['causal_momentum_available'])
                if guidance=='WATCH' and ev['probability_weakening'] and not corroboration:
                    guidance='HOLD'
                    management['candidate_context']='MODEL_SOFTENING_WITHOUT_CORROBORATED_THESIS_WARNING'
                current_p=f['fair'][side.lower()+'_fair']
                extra=[]
                if now >= o['opportunity']['horizon_end']:
                    extra.append('ORIGINAL_OPPORTUNITY_HORIZON_ENDED_REASSESS')
                if f['official_close']-now <= o['opportunity']['execution_budget_seconds']:
                    extra.append('MANUAL_EXECUTION_RUNWAY_EXHAUSTED')
                try:
                    settlement=settlement_context(f); out['settlement']=settlement
                    if settlement['phase']=='AVERAGING':
                        # Arithmetic can challenge a thesis, never prove future settlement.
                        sign=1 if side=='UP' else -1
                        hurdle=settlement['raw_unknown_mean_hurdle']
                        if hurdle is None or sign*(f['brti']['value']-float(hurdle)) <= 0:
                            extra.append('ACCUMULATED_SETTLEMENT_CHALLENGES_THESIS')
                except (ValueError,KeyError,TypeError) as exc:
                    extra.append('SETTLEMENT_EVIDENCE_UNAVAILABLE:'+str(exc))
                if guidance in ('WATCH','PROTECT') or extra:
                    if not self.watch_episode:
                        self.watch_episode=dict(anchor_p=self.prior_p,opened_ts=now)
                    if guidance not in ('EXIT','PROTECT'):
                        guidance='WATCH'
                elif self.watch_episode and guidance=='HOLD':
                    # Natural recovery to pre-warning support, no invented drop threshold.
                    if later and current_p >= self.watch_episode['anchor_p']:
                        self.watch_episode=None
                    else:
                        guidance='WATCH'
                management['candidate_warning_reasons']=extra
                management['candidate_state']=guidance
                if guidance in ('EXIT','PROTECT'):
                    action=manager.Action(guidance)
                    if next_state.position.action != action or management['new_exit']:
                        event=guidance
                    next_state=replace(next_state,position=replace(next_state.position,action=action,reason=management['reason']))
                if guidance=='WATCH' and before.get('watch_episode') is None:
                    event='WATCH'
                self.prior_p=current_p
            self.state=next_state; self.last=dict(key=key,at=f['captured_ts'],quote=deepcopy(f['quote']))
            out.update(event=event,guidance='BUY' if event=='BUY' else guidance,status=status,
                origin=deepcopy(self.origin), terminal=deepcopy(self.terminal), management=management,
                expires_at=expires, history=deepcopy(self.history),
                warning_owner='EARLY',final_role='INDEPENDENT_SETTLEMENT_EVIDENCE',
                visible_signal='EXIT' if guidance=='EXIT' else 'WATCH (could flip)' if guidance in ('WATCH','PROTECT') else 'BUY' if self.origin else None,
                realized_profit=None)
        except (ValueError,KeyError,TypeError) as exc:
            self.restore(before)
            out.update(reason=str(exc),origin=deepcopy(self.origin),terminal=deepcopy(self.terminal),history=deepcopy(self.history))
        return out
