"""Native-clock product integration of recovered EARLY/FINAL lifecycle.

Historical V4.7 entry and V4.6 FINAL gates remain separate from the native
supported-value entry policy. The recovered reduce_signal supplies immutable
EARLY origins and monotone protection. No model refit, simulated fill or order.
"""
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import time
import uuid

from btc15_v2_product.directional_authority import reduce_signal, encode_state, decode_state, manager
from btc15_ladder_journal_v1 import Worker, digest, SCHEMA
from btc15_position_context_v2 import context

CANDIDATE = 'BTC15_INTEGRATED_FINISH_20261006'
BASE_MAIN = 'abe212b513827c8cec28a2f64e0161e79296bd82'
BASE_V81 = 'b05723ec622f901a05402ecf27f4d33505753ef1'
ROOT = Path(os.getenv('BTC15_LADDER_DATA_ROOT', '/data/btc15_ladders_v2'))


def iso(at):
    return datetime.fromtimestamp(at, timezone.utc).isoformat()


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def native_frame(ns, quote, epoch, sequence, captured):
    """Copy only the complete native decision, never later provider state."""
    m, f, b = ns['market'], ns['_ec_live'], ns['_brti_contract']
    opened = ns['parse_dt'](m['open_time']).timestamp()
    closed = ns['parse_dt'](m['close_time']).timestamp()
    btc = ns['_btc_spot_provenance']
    return dict(kind='NATIVE_DECISION', candidate=CANDIDATE, native_epoch=epoch,
        native_sequence=sequence, captured_ts=captured, feature_cutoff=ns['now_ts'],
        contract=m['ticker'], official_open=opened, official_close=closed,
        target=float(ns['target']), btc_price=float(ns['btc']),
        btc_source=btc['source_utc'].timestamp(), btc_received=btc['observed_utc'].timestamp(),
        fair=deepcopy(f) if f else None, brti=deepcopy(b) if b else None,
        quote=deepcopy(quote), up_bid=ns['up_bid'], up_ask=ns['up_ask'],
        down_bid=ns['down_bid'], down_ask=ns['down_ask'],
        artifact=ns.get('_fair_model_artifact_sha256'), weights=ns.get('_fair_model_weights_sha256'))


def qualify(f, now):
    o, c, cut, at = f['official_open'], f['official_close'], f['feature_cutoff'], f['captured_ts']
    if not all(finite(v) for v in (o,c,cut,at,now,f['target'],f['btc_source'],f['btc_received'])):
        raise ValueError('NONFINITE_SOURCE')
    if c-o != 900 or o % 900 or not o <= cut <= at <= now < c:
        raise ValueError('OFFICIAL_WINDOW_OR_CAUSAL_ORDER')
    expected = datetime.fromtimestamp(c, timezone.utc).astimezone(manager.ZoneInfo('America/New_York'))
    if f['contract'] != 'KXBTC15M-' + expected.strftime('%y%b%d%H%M-%M').upper():
        raise ValueError('OFFICIAL_TICKER_MISMATCH')
    if f['target'] <= 0 or not f['btc_source'] <= f['btc_received'] <= cut or now-f['btc_source'] > 10:
        raise ValueError('BTC_SOURCE_UNAVAILABLE')
    q, b, fair = f['quote'], f['brti'], f['fair']
    if not q or not b or not fair or not f['artifact'] or not f['weights']:
        raise ValueError('DECISION_INPUT_UNAVAILABLE')
    if (q['ticker'] != f['contract'] or q['source_time'] != iso(cut)
            or q['close_ms'] != int(c*1000)
            or not o <= q['exchange_ts_ms']/1000 <= q['consumed_ms']/1000 <= at
            or now-q['exchange_ts_ms']/1000 > 6 or not q['epoch']):
        raise ValueError('QUOTE_SOURCE_UNAVAILABLE')
    if list(q['quotes']) != [f[k] for k in ('up_bid','up_ask','down_bid','down_ask')]:
        raise ValueError('QUOTE_VALUE_MISMATCH')
    prices = q['quotes']
    if not all(finite(p) and 0 <= p <= 1 for p in prices) or prices[0]>prices[1] or prices[2]>prices[3]:
        raise ValueError('INVALID_EXECUTABLE_BOOK')
    if not finite(f['btc_price']) or f['btc_price']<=0 or not finite(b.get('value')) or not 1000<b['value']<1_000_000:
        raise ValueError('SOURCE_VALUE_INVALID')
    d = b['delivery']
    if (b.get('ready') is not True or not d.get('owner_epoch')
            or not b['cf_ts'] <= d['observed_ts'] <= cut <= at <= now
            or not 0 <= now-b['cf_ts'] <= 5):
        raise ValueError('BRTI_SOURCE_UNAVAILABLE')
    if not all(finite(fair.get(k)) for k in ('up_fair','down_fair','fair','ask','edge','dist_over_range5')):
        raise ValueError('MODEL_INPUT_UNAVAILABLE')
    if not 0 <= fair['up_fair'] <= 1 or abs(fair['up_fair']+fair['down_fair']-1)>1e-9:
        raise ValueError('MODEL_PROBABILITY_INVALID')
    side = 'UP' if fair['up_fair'] >= fair['down_fair'] else 'DOWN'
    if (fair['side'] != side or fair['ask'] != f[side.lower()+'_ask']
            or abs(fair['fair']-max(fair['up_fair'],fair['down_fair']))>1e-9
            or abs(fair['edge']-(fair['fair']-fair['ask']))>1e-9):
        raise ValueError('FAIR_ENTRY_SIDE_MISMATCH')
    return min(c,b['cf_ts']+5,f['btc_source']+10,q['exchange_ts_ms']/1000+6,at+15)


def protected_frame(f, now):
    """Exact existing protected gates, evaluated once per complete native frame."""
    fair, b = f['fair'], f['brti']
    side, ask, p = fair['side'], fair['ask'], fair['fair']
    left = f['official_close']-f['captured_ts']
    gap = f['btc_price']-f['target']
    bgap = b['value']-f['target']
    early_gates = dict(ask_le45=0<ask<=.45, fair_ge75=p>=.75,
        remaining_2_to10=120<=left<=600, gap_ge25=abs(gap)>=25)
    final_gates = dict(fair_ge90=p>=.90, remaining_le8=left<=480,
        gap_ok=abs(gap)>=(75 if left>360 else 50), distance_range_ge1=fair['dist_over_range5']>=1,
        target_side=side==('UP' if gap>0 else 'DOWN' if gap<0 else None),
        brti_side=abs(bgap)>11 and side==('UP' if bgap>0 else 'DOWN'))
    raw = dict(contract=f['contract'], source_timestamp_utc=iso(f['captured_ts']),
        timer=dict(close_utc=iso(f['official_close']),seconds_left=left),
        market={k:f[k] for k in ('up_bid','up_ask','down_bid','down_ask')},
        health=dict(source_fresh=True,market_open=True,paired_quotes=True,brti_fresh=True),
        safety=dict(read_only=True,orders_enabled=False),
        early=dict(source='FROZEN_TIER1',ready=all(early_gates.values()),side=side,ask=ask,
            fair=p,edge=fair['edge'],conditions=early_gates),
        final=dict(source='FROZEN_V4_6_FINAL',ready=all(final_gates.values()),side=side,
            confidence=p,conditions=final_gates))
    qualified=dict(usable_frame=True,brti_fresh=True,
        lanes=dict(early=dict(publication_eligible=raw['early']['ready'])))
    return raw, qualified


def early_opportunity(raw):
    """Compatibility entry point; broad native analysis has no purchase ceiling."""
    from .opportunities import evaluate
    return evaluate(raw)[0]



class Directional:
    def restore(self, saved):
        self.signal_history = saved.get('signal_history', []) if saved else []
        self.terminal = saved.get('terminal') if saved else None
        self.reentry_disarmed = saved.get('reentry_disarmed', True) if saved else True
        if saved and saved.get('candidate') != CANDIDATE:
            raise ValueError('DIRECTIONAL_CHECKPOINT_CANDIDATE_MISMATCH')
        self.state = decode_state(saved['manager']) if saved else manager.State()
        self.origin = saved.get('origin') if saved else None
        self.last = saved.get('last') if saved else None
        self.prior_final = saved.get('prior_final') if saved else None
        self.position_path = saved.get('position_path', {}) if saved else {}
        position=self.state.position
        if bool(position)!=bool(self.origin):
            raise ValueError('DIRECTIONAL_CHECKPOINT_ORIGIN_MISSING')
        if self.origin:
            o=self.origin
            if (o['contract']!=position.contract_id or o['side']!=position.side or o['original_ask']!=position.entry_ask
                or datetime.fromisoformat(o['signal_timestamp_utc'])!=position.entry_timestamp
                or o['entry_provenance'].get('candidate')!=CANDIDATE
                or o['origin_id']!=digest([CANDIDATE,o['contract'],[o['native_epoch'],o['native_sequence']],o['side']])):
                raise ValueError('DIRECTIONAL_CHECKPOINT_ORIGIN_CONFLICT')
            if self.terminal:
                t=self.terminal;q=t.get('quote') or {}
                if (position.action!=manager.Action.EXIT or t.get('origin_id')!=o['origin_id'] or
                    t.get('contract')!=o['contract'] or t.get('side')!=o['side'] or
                    t.get('original_ask')!=o['original_ask'] or t.get('state')!='EXIT' or
                    t.get('actionable_exit') is not True or q.get('ticker')!=o['contract'] or
                    q.get('exchange_ts_ms',0)/1000<=position.entry_timestamp.timestamp() or
                    t.get('executable_exit_bid')!=(q.get('quotes') or [None]*4)[0 if o['side']=='UP' else 2]):
                    raise ValueError('DIRECTIONAL_CHECKPOINT_TERMINAL_CONFLICT')
            elif position.action==manager.Action.EXIT:
                raise ValueError('DIRECTIONAL_CHECKPOINT_TERMINAL_MISSING')
            self.position_path['missing'] = True
        elif self.terminal:
            raise ValueError('DIRECTIONAL_CHECKPOINT_TERMINAL_WITHOUT_ORIGIN')

        from .trade_clarity import remember
        self.signal_history=remember(self.signal_history,self.origin,'main',terminal=self.terminal)

    def checkpoint(self):
        return deepcopy(dict(candidate=CANDIDATE,manager=encode_state(self.state),origin=self.origin,last=self.last,prior_final=self.prior_final,position_path=self.position_path,terminal=self.terminal,signal_history=self.signal_history,reentry_disarmed=self.reentry_disarmed))

    def process(self, f, now):
        record = dict(schema=SCHEMA, candidate=CANDIDATE, build=os.getenv('RAILWAY_GIT_COMMIT_SHA'),
            kind=f.get('kind','UNAVAILABLE'), contract=f.get('contract'), published_ts=now,
            signal_only=True, orders=False, evidence=f)
        view = dict(candidate=CANDIDATE, build=record['build'], published_ts=now,
            contract=f.get('contract'),status='UNAVAILABLE', signal_only=True, orders=False,
            manual_execution_only=True,origin=self.origin)
        if f.get('kind') in ('SETTLEMENT','BRTI_CLOSEOUT'):
            record['settlement' if f['kind']=='SETTLEMENT' else 'brti_closeout'] = f['settlement']
            view['reason'] = 'SETTLEMENT_RECORD_ONLY'
            return record,self.checkpoint(),view
        try:
            if f.get('kind') != 'NATIVE_DECISION':
                raise ValueError(f.get('reason','NATIVE_INPUT_UNAVAILABLE'))
            expires = qualify(f,now)
            key = [f['native_epoch'],f['native_sequence']]
            if self.last and key[0] == self.last['key'][0] and key[1] <= self.last['key'][1]:
                raise ValueError('DUPLICATE_OR_OUT_OF_ORDER_DECISION')
            continuity = 'OBSERVED'
            if not self.last or self.last['key'][0]!=key[0] or f['captured_ts']-self.last['at']>15:
                continuity = 'START_OR_MISSING_INTERVAL'
            raw, qualified = protected_frame(f,now)
            from .early_entry import assess, route
            value_entry = assess(raw,f)
            raw, qualified = route(raw,qualified,value_entry)
            from .opportunities import evaluate
            opportunity, analysis = evaluate(raw, f, self.prior_final, self.origin)
            if self.origin and self.origin['contract']==f['contract'] and self.origin['target']!=f['target']:
                raise ValueError('IMMUTABLE_TARGET_CONFLICT')
            # FINAL publication is independent of EARLY manager success.
            standalone = dict(raw['final'],publication_id=digest([CANDIDATE,'FINAL',key]),
                probability_up=f['fair']['up_fair'],probability_down=f['fair']['down_fair'],
                state='FINAL_CALL' if raw['final']['ready'] else 'PASS',
                confidence=raw['final']['confidence'],lock_state='QUALIFIED' if raw['final']['ready'] else 'UNLOCKED')
            view.update(final=standalone,expires_at=expires,final_status='AVAILABLE')
            # Re-entry requires a genuine new qualifying edge after the prior
            # EXIT: observe a NOT-ready frame first, then a fresh ready frame.
            # Do not assume that the user manually filled or closed anything.
            if self.terminal and self.origin and self.origin['contract']==f['contract']:
                if not raw['early']['ready']:
                    self.reentry_disarmed = False
                elif not self.reentry_disarmed and continuity=='OBSERVED':
                    from dataclasses import replace
                    self.state = replace(self.state, position=None, buy_emitted=False)
                    self.origin = None
                    self.terminal = None
                    self.position_path = {}
                    self.reentry_disarmed = True
            next_state,event,status,frame = reduce_signal(self.state,raw,qualified,datetime.fromtimestamp(now,timezone.utc))
            origin = self.origin if self.origin and self.origin['contract']==f['contract'] else None
            if event == 'BUY':
                origin = dict(origin_id=digest([CANDIDATE,f['contract'],key,frame.early['side']]),
                    contract=f['contract'], side=frame.early['side'], original_ask=frame.early['ask'],
                    signal_timestamp_utc=iso(now), source_timestamp_utc=raw['source_timestamp_utc'],
                    native_epoch=key[0],native_sequence=key[1],target=f['target'],
                    official_open=f['official_open'],official_close=f['official_close'],
                    entry_provenance=deepcopy(f), manual_fill=None,
                    entry_policy=raw['early'].get('policy','HISTORICAL_TIER1'),
                    qualification=deepcopy(value_entry) if raw['early'].get('policy') else
                        dict(policy='HISTORICAL_TIER1',conditions=raw['early']['conditions'],ready=True))
                self.terminal = None
                self.reentry_disarmed = True
                self.position_path = dict(mfe=None,mae=None,last_quote=None,current=None,missing=False)
            elif origin is None:
                self.position_path = {}
                self.terminal = None
            final = dict(standalone, early_origin_id=origin['origin_id'] if origin else None)
            same_prior = self.prior_final and self.prior_final['contract']==f['contract']
            final['confidence_change'] = final['probability_up']-self.prior_final['probability_up'] if same_prior else None
            guidance = next_state.position.action.value if next_state.position else 'PASS'
            warning = None; linked = bool(origin); ctx = None; bid = None; movement = None
            helper = None; management = None
            if linked:
                side=origin['side']; held_p=final['probability_up'] if side=='UP' else final['probability_down']
                entry_p=origin['entry_provenance']['fair'][side.lower()+'_fair']
                prior_p=(self.prior_final['probability_up'] if side=='UP' else 1-self.prior_final['probability_up']) if same_prior else entry_p
                strong=manager._strong(frame,side)
                opposed=final['side']!=side
                flipped=bool(opposed and same_prior and self.prior_final.get('last_call_side')==side and final['ready'])
                bgap=f['brti']['value']-f['target']; gap=f['btc_price']-f['target']
                final['context_state']=('MIXED' if not final['ready'] and
                    (abs(bgap)<=11 or (bgap>0)!=(gap>0) or final['side']!=('UP' if gap>0 else 'DOWN'))
                    else 'ALIGNED' if final['ready'] else 'UNCONFIRMED')
                relation=('FLIP_ALERT' if opposed and final['ready'] else 'OPPOSING' if opposed else
                    'MIXED' if final['context_state']=='MIXED' else
                    'WEAKENING' if held_p < prior_p-1e-12 else 'STRENGTHENING' if held_p > prior_p+1e-12 else 'CONFIRMING')
                # No arbitrary probability-drop threshold: loss of established
                # FINAL qualification is the recovered material-deterioration rule.
                material=bool(self.state.position and self.state.position.saw_strong_final and not strong)
                bid=f[side.lower()+'_bid']; movement=bid-origin['original_ask']
                q=f['quote']; previous=self.position_path.get('last_quote') or origin['entry_provenance']['quote']
                signal_ts=datetime.fromisoformat(origin['signal_timestamp_utc']).timestamp()
                later_bid=False
                if (q['exchange_ts_ms']/1000>signal_ts and q['exchange_ts_ms']>previous['exchange_ts_ms'] and
                    (q['epoch']!=previous['epoch'] or (q['sid']==previous['sid'] and q['seq']>previous['seq']))):
                    later_bid=True
                    path=self.position_path
                    path['mfe']=movement if path.get('mfe') is None else max(path['mfe'],movement)
                    path['mae']=movement if path.get('mae') is None else min(path['mae'],movement)
                    path['current']=dict(ts=now,bid=bid,delta_cents=movement*100)
                    path['last_quote']=deepcopy(q)
                    if continuity!='OBSERVED' or q['epoch']!=previous['epoch']:
                        path['missing']=True
                    record['later_bid']=dict(path['current'],origin_id=origin['origin_id'],side=side,quote=q)
                ctx=context(side,f['official_close']-now,btc=f['btc_price'],brti=f['brti']['value'],target=f['target'],
                    weakening=held_p<prior_p-1e-12 or final['context_state']=='MIXED',
                    giveback=self.position_path.get('mfe') is not None and movement<self.position_path['mfe']-1e-12)
                from .early_management import decide
                management=decide(f,origin,prior_p,self.position_path,
                    next_state.position.action.value,later_bid,self.terminal)
                guidance=management['state']
                self.terminal=management['terminal']
                if guidance in ('PROTECT','EXIT'):
                    action=manager.Action(guidance)
                    if next_state.position.action!=action or management['new_exit']:
                        event=guidance
                    next_state=replace(next_state,position=replace(next_state.position,
                        action=action,reason=management['reason']))
                warning=guidance if guidance in ('PROTECT','EXIT') else 'CONFIRMED' if strong else guidance
                helper=dict(origin_id=origin['origin_id'],relation=relation,confirmed=strong,
                    probability_trend='STRENGTHENS' if held_p>prior_p+1e-12 else 'WEAKENS' if held_p<prior_p-1e-12 else 'UNCHANGED',
                    material_deterioration=material or guidance in ('PROTECT','EXIT'),clearance=strong,
                    protect_latched=guidance in ('PROTECT','EXIT'),state=guidance,
                    reason=management['reason'],policy=management['policy'],
                    executable_bid=bid,exit_authority=guidance=='EXIT',
                    evidence=management['evidence'])
                final.update(origin_side_probability=held_p,origin_probability_change=held_p-entry_p,helper=helper)
            if not linked:
                # Display context only, after the protected EARLY evaluation.
                side=raw['early']['side']
                prior=(self.prior_final['probability_up'] if side=='UP' else 1-self.prior_final['probability_up']) if same_prior else None
                held=f['fair'][side.lower()+'_fair']
                gap=f['btc_price']-f['target'];bgap=f['brti']['value']-f['target']
                mixed=(abs(bgap)<=11 or (bgap>0)!=(gap>0) or final['side']!=('UP' if gap>0 else 'DOWN'))
                relation=('OPPOSING' if final['side']!=side else 'MIXED' if mixed else
                    'WEAKENING' if prior is not None and held<prior-1e-12 else
                    'STRENGTHENING' if prior is not None and held>prior+1e-12 else 'CONFIRMING')
                final['helper']=dict(relation=relation,state='CONTEXT_ONLY',confirmed=final['ready'] and final['side']==side,
                    protect_latched=False,exit_authority=False,entry_authority=False,probability_trend=relation)
            left=f['official_close']-now
            view.update(status=status,expires_at=expires,official_open=f['official_open'],official_close=f['official_close'],
                prices={k:f[k] for k in ('up_bid','up_ask','down_bid','down_ask')},
                target=f['target'],native_epoch=key[0],native_sequence=key[1],feature_cutoff=f['feature_cutoff'],early_opportunity=opportunity,opportunity_analysis=analysis,
                source_timestamp_utc=raw['source_timestamp_utc'],origin=origin,early=dict(raw['early'],guidance=guidance,
                    pass_reasons=[k for k,v in raw['early']['conditions'].items() if not v],tier_scope='INDEPENDENT_HISTORICAL_AND_SUPPORTED_VALUE'),
                historical_early=raw['historical_early'],
                final=final,warning=warning,final_link_basis='EXPLICIT_IMMUTABLE_ORIGIN' if linked else None,
                exit_guidance='EXIT' if guidance=='EXIT' else None,
                exit_reason=management['reason'] if management else 'NO_GENUINE_EARLY_ORIGIN',
                terminal=deepcopy(self.terminal),management=management,
                executable_current_bid=bid,movement_cents=None if movement is None else movement*100,
                position_path=deepcopy(self.position_path),context=ctx,
                flip_risk_pct=100*f['fair']['down_fair' if f['btc_price']>=f['target'] else 'up_fair'],
                flip_risk_authority='MODEL_INFORMATION_ONLY',five_minute_caution=left<=300,
                three_minute_guard=left<=180,phase='3M_GUARD' if left<=180 else '5M_CAUTION' if left<=300 else 'NORMAL',
                health=dict(brti_age=now-f['brti']['cf_ts'],quote_age=now-f['quote']['exchange_ts_ms']/1000,
                            btc_age=now-f['btc_source'],causal=True),continuity=continuity,
                performance_status='CURRENT_LONG_RUN_ACCURACY_NOT_ESTABLISHED')
            record.update(event=event,origin_id=origin['origin_id'] if origin else None,final=final,
                          early=view['early'],early_opportunity=opportunity,opportunity_analysis=analysis,warning=warning,continuity=continuity,origin=deepcopy(origin) if event=='BUY' else None,
                          guidance=guidance,context=ctx,management=management,terminal=deepcopy(self.terminal),position_path=deepcopy(self.position_path))
            from .trade_clarity import remember
            self.signal_history=remember(self.signal_history,origin,'main',guidance,self.terminal,management['reason'] if management else None)
            self.state,self.origin=next_state,origin
            self.last=dict(key=key,at=f['captured_ts'])
            self.prior_final=dict(contract=f['contract'],captured_ts=f['captured_ts'],btc_price=f['btc_price'],prices={k:f[k] for k in ('up_bid','up_ask','down_bid','down_ask')},probability_up=final['probability_up'],side=final['side'],ready=final['ready'],
                last_call_side=final['side'] if final['ready'] else self.prior_final.get('last_call_side') if same_prior else None)
        except (ValueError,KeyError,TypeError) as exc:
            view['reason']=str(exc);record['unavailable_reason']=str(exc)
            if self.origin:self.position_path['missing']=True
            if view.get('final_status')=='AVAILABLE':
                view['final']['early_origin_id']=None
                view['final']['helper_unavailable']=str(exc)
                record['final']=view['final']
        from .trade_clarity import remember,project
        self.signal_history=remember(self.signal_history,self.origin,'main')
        view['trade_clarity']=project(self.signal_history,self.origin,'main',view,record.get('event'))
        return record,self.checkpoint(),view


_worker=None
_epoch=str(uuid.uuid4())
_sequence=0


def start():
    global _worker
    if _worker is None:
        _worker=Worker(ROOT,'main',Directional())
        _worker.start_settlements()


def offer(ns):
    global _sequence
    if _worker is None:
        return
    _sequence+=1
    try:
        import btc15_kalshi_quote_provenance_v1 as quotes
        provider=getattr(quotes,'_provider',None)
        quote=getattr(provider,'last_product_quote',None)
        value=native_frame(ns,quote,_epoch,_sequence,time.time())
        value['model_features']=deepcopy(ns.get('_early_model_features'))
        value['fee_schedule']=deepcopy(getattr(ns.get('_early_fee_cache'),'value',None))
    except Exception as exc:
        value=dict(kind='UNAVAILABLE',reason='NATIVE_FRAME:'+type(exc).__name__,contract=ns.get('ticker'))
    _worker.offer(value)


def settlement(ticker, value):
    if _worker is not None:
        _worker.offer(dict(kind='BRTI_CLOSEOUT',contract=ticker,settlement=value))

