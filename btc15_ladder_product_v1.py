"""Native-clock product integration of recovered EARLY/FINAL lifecycle.

The entry and FINAL gates are the existing V4.7/V4.6 gates. The recovered
reduce_signal supplies EARLY-only origin creation and monotone protection.
No model refit, new threshold, simulated fill, order or market poll.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import time
import uuid

from btc15_directional_signal_authority_v1 import reduce_signal, encode_state, decode_state, manager
from btc15_ladder_journal_v1 import Worker, digest, SCHEMA

CANDIDATE = 'BTC15_LADDER_COMPLETION_20261003_V1'
BASE_MAIN = 'abe212b513827c8cec28a2f64e0161e79296bd82'
BASE_V81 = 'b05723ec622f901a05402ecf27f4d33505753ef1'
ROOT = Path(os.getenv('BTC15_LADDER_DATA_ROOT', '/data/btc15_ladders_v1'))


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
        fair=dict(f) if f else None, brti=dict(b) if b else None,
        quote=quote, up_bid=ns['up_bid'], up_ask=ns['up_ask'],
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
    early_gates = dict(ask_le45=ask<=.45, fair_ge75=p>=.75, edge_ge8=fair['edge']>=.08,
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


class Directional:
    def restore(self, saved):
        self.state = decode_state(saved['manager']) if saved else manager.State()
        self.origin = saved.get('origin') if saved else None
        self.last = saved.get('last') if saved else None
        self.prior_final = saved.get('prior_final') if saved else None

    def checkpoint(self):
        return dict(manager=encode_state(self.state),origin=self.origin,last=self.last,prior_final=self.prior_final)

    def process(self, f, now):
        record = dict(schema=SCHEMA, candidate=CANDIDATE, build=os.getenv('RAILWAY_GIT_COMMIT_SHA'),
            kind=f.get('kind','UNAVAILABLE'), contract=f.get('contract'), published_ts=now,
            signal_only=True, orders=False, evidence=f)
        view = dict(candidate=CANDIDATE, build=record['build'], published_ts=now,
            contract=f.get('contract'),status='UNAVAILABLE', signal_only=True, orders=False,
            manual_execution_only=True,origin=self.origin)
        if f.get('kind') == 'SETTLEMENT':
            record['settlement'] = f['settlement']
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
            if self.origin and self.origin['contract']==f['contract'] and self.origin['target']!=f['target']:
                raise ValueError('IMMUTABLE_TARGET_CONFLICT')
            next_state,event,status,frame = reduce_signal(self.state,raw,qualified,datetime.fromtimestamp(now,timezone.utc))
            origin = self.origin if self.origin and self.origin['contract']==f['contract'] else None
            if event == 'BUY':
                origin = dict(origin_id=digest([CANDIDATE,f['contract'],key,frame.early['side']]),
                    contract=f['contract'], side=frame.early['side'], original_ask=frame.early['ask'],
                    signal_timestamp_utc=iso(now), source_timestamp_utc=raw['source_timestamp_utc'],
                    native_epoch=key[0],native_sequence=key[1],target=f['target'],
                    official_open=f['official_open'],official_close=f['official_close'],
                    entry_provenance=f, manual_fill=None)
            final = dict(raw['final'],publication_id=digest([CANDIDATE,'FINAL',key]),
                probability_up=f['fair']['up_fair'],probability_down=f['fair']['down_fair'],
                state='FINAL_CALL' if raw['final']['ready'] else 'PASS',
                early_origin_id=origin['origin_id'] if origin else None)
            final['confidence_change'] = (None if not self.prior_final or self.prior_final['contract']!=f['contract']
                else final['probability_up']-self.prior_final['probability_up'])
            guidance = next_state.position.action.value if next_state.position else 'PASS'
            linked = bool(origin)
            warning = ('PROTECT' if guidance=='PROTECT' else 'CONFIRMED' if linked and manager._strong(frame,origin['side'])
                       else 'WATCH' if linked else None)
            if linked:
                held_p = final['probability_up'] if origin['side']=='UP' else final['probability_down']
                final['origin_side_probability'] = held_p
                final['origin_probability_change'] = held_p-origin['entry_provenance']['fair'][origin['side'].lower()+'_fair']
            left=f['official_close']-now
            view.update(status=status,expires_at=expires,official_open=f['official_open'],official_close=f['official_close'],
                target=f['target'],native_epoch=key[0],native_sequence=key[1],feature_cutoff=f['feature_cutoff'],
                source_timestamp_utc=raw['source_timestamp_utc'],origin=origin,early=dict(raw['early'],guidance=guidance,
                    pass_reasons=[k for k,v in raw['early']['conditions'].items() if not v],target_ask=.50,ideal_band=[.25,.35]),
                final=final,warning=warning,final_link_basis='EXPLICIT_IMMUTABLE_ORIGIN' if linked else None,
                exit_guidance=None,exit_reason='NO_SUPPORTED_EXECUTABLE_EXIT_RULE',
                flip_risk_pct=100*f['fair']['down_fair' if f['btc_price']>=f['target'] else 'up_fair'],
                flip_risk_authority='MODEL_INFORMATION_ONLY',five_minute_caution=left<=300,
                three_minute_guard=left<=180,phase='3M_GUARD' if left<=180 else '5M_CAUTION' if left<=300 else 'NORMAL',
                health=dict(brti_age=now-f['brti']['cf_ts'],quote_age=now-f['quote']['exchange_ts_ms']/1000,
                            btc_age=now-f['btc_source'],causal=True),continuity=continuity,
                performance_status='CURRENT_LONG_RUN_ACCURACY_NOT_ESTABLISHED')
            record.update(event=event,origin_id=origin['origin_id'] if origin else None,final=final,
                          early=view['early'],warning=warning,continuity=continuity)
            self.state,self.origin=next_state,origin
            self.last=dict(key=key,at=f['captured_ts'])
            self.prior_final=dict(contract=f['contract'],probability_up=final['probability_up'])
        except (ValueError,KeyError,TypeError) as exc:
            view['reason']=str(exc);record['unavailable_reason']=str(exc)
        return record,self.checkpoint(),view


_worker=None
_epoch=str(uuid.uuid4())
_sequence=0


def start():
    global _worker
    if _worker is None:
        _worker=Worker(ROOT,'main',Directional())


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
    except Exception as exc:
        value=dict(kind='UNAVAILABLE',reason='NATIVE_FRAME:'+type(exc).__name__,contract=ns.get('ticker'))
    _worker.offer(value)


def settlement(ticker, value):
    if _worker is not None:
        _worker.offer(dict(kind='SETTLEMENT',contract=ticker,settlement=value))
