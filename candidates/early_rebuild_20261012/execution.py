"""Offline native evidence adapters. No collector, order or fill inference.

Raw book keys follow the official Kalshi WebSocket schema checked 2026-10-12.
Our receipt envelopes/fee review policies are explicit capture/review requirements,
not fields alleged to exist in historical records or exchange responses.
"""
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import math
from .assessment import SAFETY, finite
from candidates.early_value_20261011.engine import digest


def number(v):
    if isinstance(v,bool) or not isinstance(v,(str,int,float,Decimal)):raise ValueError('INVALID_DECIMAL')
    try:n=Decimal(str(v))
    except InvalidOperation:raise ValueError('INVALID_DECIMAL') from None
    if not n.is_finite():raise ValueError('NONFINITE_DECIMAL')
    return n


def timestamp(s):
    d=datetime.fromisoformat(s.replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('TIMESTAMP_ZONE_REQUIRED')
    return d.timestamp()


def bind_native(r, now):
    coverage={};errors=[];f=r.get('native_frame')
    if not isinstance(f,dict):return dict(coverage={},blockers=['NATIVE_FRAME_MISSING'])
    try:
        from btc15_v2_product.directional import qualify
        from candidates.early_opportunity_20261011.qualification import validate_quote
        from btc15_v2_product.early_management import features
        if f.get('kind')!='NATIVE_DECISION':raise ValueError('NATIVE_DECISION_REQUIRED')
        qualify(f,now);validate_quote(f)
        expected=dict(contract=f['contract'],target=f['target'],time=f['feature_cutoff'],
                      btc=f['btc_price'],brti=f['brti']['value'],side=f['fair']['side'],p=f['fair']['fair'])
        expected.update({k:f[k] for k in ('up_bid','up_ask','down_bid','down_ask')})
        if any(r.get(k)!=v for k,v in expected.items()) or abs(r['time']+r['left']-f['official_close'])>1e-6:
            raise ValueError('NATIVE_FRAME_ROW_BINDING_CONFLICT')
        if not f['captured_ts']<=r['received']<=now:raise ValueError('DECISION_RECEIPT_BINDING')
        coverage.update(contract_target_official_window=True,btc_source_and_receipt=True,
            brti_source_and_receipt=True,quote_exchange_and_consumption=True,
            native_features=features(f) is not None)
        if not coverage['native_features']:errors.append('CAUSAL_FEATURE_BINDING_NOT_COMPLETE')
        # A consumption timestamp is not the missing original WebSocket receipt.
        coverage['original_quote_receipt']=False
        s=f.get('fee_schedule') or {}
        bound=(s.get('series')=='KXBTC15M' and s.get('source')=='/trade-api/v2/series/KXBTC15M'
               and s.get('fee_type') in ('quadratic','quadratic_with_maker_fees') and
               finite(s.get('multiplier')) and s['multiplier']>=0 and
               finite(s.get('observed_ts')) and 0<=f['feature_cutoff']-s['observed_ts']<=86400)
        coverage['observed_series_fee_terms']=bound
        coverage['fee_effective_interval_and_overrides']=False
    except (KeyError,ValueError,TypeError,OverflowError) as exc:errors.append('INVALID_NATIVE_BINDING:'+str(exc))
    return dict(coverage=coverage,blockers=errors,frame_sha256=digest(f))


def bind_market(envelope, f, now):
    m=envelope['payload']['market'];received=envelope['received_ts']
    if not finite(received) or not received<=f['feature_cutoff']<=now:raise ValueError('MARKET_RECEIPT_FUTURE_OR_MISSING')
    if (m['ticker']!=f['contract'] or m['market_type']!='binary' or m['strike_type']!='greater' or
        number(m['floor_strike'])!=number(f['target']) or not m.get('rules_primary') or
        timestamp(m['open_time'])!=f['official_open'] or timestamp(m['close_time'])!=f['official_close']):
        raise ValueError('MARKET_TARGET_WINDOW_OR_DIRECTION_MISMATCH')
    if not m['event_ticker'].startswith('KXBTC15M-'):raise ValueError('SERIES_BINDING')
    return dict(contract=m['ticker'],event=m['event_ticker'],target=f['target'],
                official_close=f['official_close'],UP='yes',DOWN='no',received_ts=received)


class DepthBook:
    """Dedicated single-market subscription: snapshot followed by every seq.

    A bad event latches invalidity until an explicit fresh snapshot. Snapshot
    sending time and delta event time are distinct; neither is a local receipt.
    """
    def __init__(self, contract):
        self.contract=contract;self.valid=False;self.levels={};self.seq=None
        self.epoch=None;self.sid=None;self.market_id=None;self.received=None;self.sent=None;self.event_time=None

    def feed(self,envelope,now):
        try:
            p=envelope['payload'];m=p['msg'];rec=envelope['received_ts'];epoch=envelope['stream_epoch']
            sent=p['sending_ts_ms']/1000
            if (not epoch or not all(finite(v) for v in (now,rec,sent)) or
                not sent<=rec<=now or now-sent>6):raise ValueError('BOOK_FUTURE_OR_STALE')
            if m['market_ticker']!=self.contract or not m.get('market_id'):raise ValueError('BOOK_CONTRACT_MISMATCH')
            if type(p['sid']) is not int or type(p['seq']) is not int or min(p['sid'],p['seq'])<0:raise ValueError('BOOK_SEQUENCE_INVALID')
            if self.received is not None and rec<self.received:raise ValueError('BOOK_RECEIPT_OUT_OF_ORDER')
            if self.sent is not None and sent<self.sent:raise ValueError('BOOK_SEND_OUT_OF_ORDER')
            if p['type']=='orderbook_snapshot':
                if self.seq is not None and epoch==self.epoch and (p['sid']!=self.sid or p['seq']<=self.seq):
                    raise ValueError('NONADVANCING_SNAPSHOT')
                levels={}
                for side in ('yes','no'):
                    a={}
                    for pair in m[side+'_dollars_fp']:
                        if len(pair)!=2:raise ValueError('MALFORMED_DEPTH_LEVEL')
                        price,size=map(number,pair)
                        if not 0<price<1 or size<=0 or price in a:raise ValueError('INVALID_DEPTH_LEVEL')
                        a[price]=size
                    levels[side]=a
                event=None # snapshot schema does not provide per-level event timestamps
            elif p['type']=='orderbook_delta':
                if not self.valid:raise ValueError('SNAPSHOT_REQUIRED')
                if epoch!=self.epoch or p['sid']!=self.sid or p['seq']!=self.seq+1 or m['market_id']!=self.market_id:
                    raise ValueError('BOOK_SEQUENCE_OR_IDENTITY_GAP')
                event=m['ts_ms']/1000
                if not finite(event) or not event<=sent or (self.event_time is not None and event<self.event_time):
                    raise ValueError('BOOK_EVENT_OUT_OF_ORDER_OR_FUTURE')
                if now-event>6:raise ValueError('BOOK_EVENT_STALE')
                if self.sent is not None and sent<self.sent:raise ValueError('BOOK_SEND_OUT_OF_ORDER')
                levels=deepcopy(self.levels);side=m['side']
                if side not in levels:raise ValueError('BOOK_SIDE_INVALID')
                price=number(m['price_dollars']);delta=number(m['delta_fp'])
                if not 0<price<1:raise ValueError('BOOK_PRICE_INVALID')
                quantity=levels[side].get(price,Decimal(0))+delta
                if quantity<0:raise ValueError('NEGATIVE_DEPTH')
                if quantity:levels[side][price]=quantity
                else:levels[side].pop(price,None)
            else:raise ValueError('UNSUPPORTED_BOOK_MESSAGE')
            if levels['yes'] and levels['no'] and max(levels['yes'])+max(levels['no'])>1:
                raise ValueError('CROSSED_BOOK')
            self.levels=levels;self.seq=p['seq'];self.sid=p['sid'];self.epoch=epoch
            self.market_id=m['market_id'];self.received=rec;self.sent=sent;self.event_time=event;self.valid=True
        except (KeyError,ValueError,TypeError,InvalidOperation,OverflowError) as exc:
            self.valid=False
            raise ValueError(str(exc)) from None

    def coverage(self,side,action,quantity,limit,now):
        if not self.valid or not finite(now) or not self.received<=now or now-self.sent>6:
            raise ValueError('BOOK_UNAVAILABLE_OR_STALE')
        if side not in ('UP','DOWN') or action not in ('BUY','SELL'):raise ValueError('INVALID_SIDE_OR_ACTION')
        quantity=number(quantity);limit=number(limit)
        if quantity<=0 or not 0<limit<1:raise ValueError('INVALID_SIZE_OR_LIMIT')
        own='yes' if side=='UP' else 'no';opposite='no' if own=='yes' else 'yes'
        levels=([(Decimal(1)-p,n) for p,n in self.levels[opposite].items()] if action=='BUY'
                else list(self.levels[own].items()))
        levels=sorted(levels,reverse=action=='SELL');remaining=quantity;cost=Decimal(0);used=[]
        for p,n in levels:
            if (action=='BUY' and p>limit) or (action=='SELL' and p<limit):continue
            take=min(n,remaining);cost+=take*p;remaining-=take
            if take:used.append([str(p),str(take)])
            if not remaining:break
        if remaining:raise ValueError('INSUFFICIENT_DISPLAYED_DEPTH')
        return dict(quantity=str(quantity),limit_dollars=str(limit),vwap_dollars=str(cost/quantity),
                    levels=used,actual_fill=False,queue_position_verified=False,partial_fill_verified=False,
                    source_sending_ts=self.sent,source_event_ts=self.event_time,received_ts=self.received)


def bind_fee_changes(response,series,at):
    """Official scheduled_ts supplies an interval; it does not prove overrides."""
    rows=[]
    for x in response['series_fee_change_arr']:
        if x['series_ticker']!=series:continue
        if x['fee_type'] not in ('quadratic','quadratic_with_maker_fees'):raise ValueError('FEE_FORMULA_UNSUPPORTED')
        mult=number(x['fee_multiplier'])
        if mult<0:raise ValueError('NEGATIVE_FEE_MULTIPLIER')
        rows.append((timestamp(x['scheduled_ts']),x['id'],float(mult),x['fee_type']))
    rows.sort()
    if len({v[0] for v in rows})!=len(rows):raise ValueError('AMBIGUOUS_FEE_EFFECTIVE_TIME')
    eligible=[v for v in rows if v[0]<=at]
    if not eligible:raise ValueError('FEE_EFFECTIVE_PERIOD_UNAVAILABLE')
    v=eligible[-1];end=next((z[0] for z in rows if z[0]>at),None)
    return dict(effective_from=v[0],next_scheduled_change=end,record_id=v[1],multiplier=v[2],fee_type=v[3],
                applicable_account_fee_verified=False)


class ExecutionRegistry:
    """Reviewed evidence is hash-pinned by the caller, never healthy=True.

    No retained full packet is shipped. Fixtures cannot validate retained/native
    observations. Review policies bind evidence, not live-publication authority.
    """
    def __init__(self,packets=(),fee_policies=(),*,permit_fixtures=False):
        self.packets={digest(p):deepcopy(p) for p in packets}
        self.fees={digest(p):deepcopy(p) for p in fee_policies}
        self.permit_fixtures=permit_fixtures

    def assess(self,r,side,now,quantity):
        result=dict(**SAFETY,valid=False,coverage={},blockers=[])
        try:
            key=r.get('execution_packet_sha256');p=self.packets.get(key)
            if p is None:raise ValueError('REVIEWED_EXECUTION_PACKET_MISSING')
            fixture=p.get('evidence_class')=='SYNTHETIC_FIXTURE'
            if fixture and (not self.permit_fixtures or r.get('evidence_class')!='SYNTHETIC_FIXTURE'):
                raise ValueError('FIXTURE_CANNOT_AUTHORIZE_NATIVE_OBSERVATION')
            if not fixture and p.get('evidence_class')!='REVIEWED_RETAINED_NATIVE':raise ValueError('EXECUTION_EVIDENCE_CLASS')
            f=r['native_frame']
            if p['native_frame_sha256']!=digest(f):raise ValueError('PACKET_FRAME_MISMATCH')
            market=bind_market(p['market'],f,now)
            if number(quantity)!=number(p['intended_quantity']):raise ValueError('INTENDED_QUANTITY_MISMATCH')
            if not all(finite(p.get(k)) and p[k]>=0 for k in ('entry_delay_seconds','exit_delay_seconds')):
                raise ValueError('DECLARED_REACTION_DELAYS_REQUIRED')
            if p['entry_delay_seconds']!=10 or p['exit_delay_seconds']!=10:raise ValueError('POLICY_REACTION_DELAY_MISMATCH')
            book=DepthBook(r['contract'])
            for e in p['book_messages']:
                if e['received_ts']>f['feature_cutoff']:raise ValueError('BOOK_NOT_AVAILABLE_AT_FEATURE_CUTOFF')
                book.feed(e,e['received_ts'])
            q=f['quote']
            if book.market_id!=q['market_id']:
                raise ValueError('BOOK_NATIVE_MARKET_ID_MISMATCH')
            # Ticker and book are different streams; never equate their sequence IDs.
            for lane in ('UP','DOWN'):
                own='yes' if lane=='UP' else 'no';other='no' if own=='yes' else 'yes'
                if not book.levels[own] or not book.levels[other]:raise ValueError('TWO_SIDED_DEPTH_REQUIRED')
                if abs(float(max(book.levels[own]))-r[lane.lower()+'_bid'])>1e-9 or abs(float(1-max(book.levels[other]))-r[lane.lower()+'_ask'])>1e-9:
                    raise ValueError('BOOK_ROW_PRICE_MISMATCH')
            result['coverage']['entry_depth']=book.coverage(side,'BUY',quantity,r[side.lower()+'_ask'],now)
            result['coverage']['current_sale_depth']=book.coverage(side,'SELL',quantity,r[side.lower()+'_bid'],now)
            result['coverage']['market_binding']=market
            result['coverage']['book_receipt_chain']=dict(epoch=book.epoch,sid=book.sid,seq=book.seq,
                native_ticker_receipt_still_unavailable=True)
            policy=self.fees.get(p.get('fee_policy_sha256'))
            if policy is None:raise ValueError('REVIEWED_FEE_APPLICABILITY_MISSING')
            if policy.get('evidence_class')!=p['evidence_class']:raise ValueError('FEE_EVIDENCE_CLASS_CONFLICT')
            if not all(finite(policy.get(k)) for k in ('effective_from','effective_until','review_available_ts')):
                raise ValueError('FEE_PERIOD_INVALID')
            for key in ('override_evidence_sha256','formula_evidence_sha256','schedule_evidence_sha256'):
                h=policy.get(key)
                if not isinstance(h,str) or len(h)!=64 or any(c not in '0123456789abcdef' for c in h):
                    raise ValueError('FEE_EVIDENCE_HASH_INVALID')
            if (policy['contract']!=r['contract'] or policy['role']!='TAKER' or policy['currency']!='USD' or
                not policy['effective_from']<=now<policy['effective_until'] or policy['review_available_ts']>r['received'] or
                not policy['account_scope_reference'] or not policy['override_evidence_sha256'] or
                not policy['formula_evidence_sha256'] or not policy['schedule_evidence_sha256']):
                raise ValueError('FEE_IDENTITY_EFFECTIVE_PERIOD_OR_REVIEW_INVALID')
            mult=number(policy['multiplier'])
            if mult<0 or policy['fee_type'] not in ('quadratic','quadratic_with_maker_fees'):
                raise ValueError('FEE_FORMULA_UNSUPPORTED')
            price=number(r[side.lower()+'_ask']);n=number(quantity)
            # Hypothetical single-batch taker fee; actual partial-fill rounding unknown.
            stress=(Decimal('.07')*mult*n*price*(1-price)).quantize(Decimal('.01'),rounding=ROUND_CEILING)
            result.update(valid=True,fee_policy_sha256=digest(policy),hypothetical_entry_fee_dollars=str(stress),
                          future_exit_depth_verified=False,actual_fill=False)
        except (KeyError,TypeError,ValueError,InvalidOperation,OverflowError) as exc:result['blockers'].append(str(exc))
        return result


def execution_assessment(r,side,now,registry=None,quantity=None):
    native=bind_native(r,now)
    result=dict(**SAFETY,valid=False,coverage=native['coverage'],blockers=list(native['blockers']))
    if result['blockers']:return result
    if registry is None:
        result['blockers'] += ['ORIGINAL_QUOTE_RECEIPT_AND_SEQUENCE_CHAIN_MISSING','DEPTH_SIZE_BINDING_UNSUPPORTED',
                              'FEE_EFFECTIVE_INTERVAL_AND_OVERRIDES_UNVERIFIED']
        return result
    if quantity is None:
        result['blockers'].append('INTENDED_HYPOTHETICAL_SIZE_REQUIRED');return result
    bound=registry.assess(r,side,now,quantity)
    result['coverage'].update(bound['coverage']);result['blockers']+=bound['blockers'];result['valid']=bound['valid']
    return result
