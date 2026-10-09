"""Ephemeral read-only confirmation of a COMMITTED native decision. NO transitions.

Only frozen feature/model arithmetic, qualification and gate predicates run here.
No reducer, offer, journal writer, lifecycle method or upstream request is called.
The native view and its original lease remain immutable. Newer information
neither revokes nor renews authority and never latches strategy state.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from btc15_information_v1 import FairAssessment, check_anchor, pack, unpack
from .directional import qualify, protected_frame, iso
from btc15_position_context_v2 import context

SCHEMA='BTC15_READ_ONLY_REVALIDATION_R1'


def binding(v):
    # Exclude only the changing administrative health/HTTP receipt, not events.
    return hashlib.sha256(pack({k:x for k,x in v.items() if k not in ('served_ts','administrative_journal')})).hexdigest()


class InputProjection:
    """Existing native anchor + existing receipt owner + accepted quote tuple."""
    def __init__(self,export,quotes,clock=time.time):
        self.export,self.quotes,self.clock=export,quotes,clock

    def capture(self):
        selected=self.export.anchor
        if selected is None:raise ValueError('NATIVE_ANCHOR_UNAVAILABLE')
        raw,delivery=selected
        a=unpack(raw);check_anchor(a)
        # Tiny bounded copy only; never acquire the mutable quote owner's lock.
        if not delivery.lock.acquire(timeout=.01):raise TimeoutError('BRTI_OWNER_BUSY')
        try:
            if not delivery.states or not delivery.statuses or not delivery.statuses[-1][1]:
                raise ValueError('BRTI_OWNER_UNAVAILABLE')
            b=dict(delivery.states[-1]);status_at=delivery.statuses[-1][0]
            if b['owner_epoch']!=delivery.epoch:raise ValueError('BRTI_OWNER_CHANGED')
        finally:delivery.lock.release()
        q=self.quotes.capture();cut=self.clock()
        if selected is not self.export.anchor or status_at>cut:raise ValueError('ANCHOR_CHANGED')
        return dict(anchor=a,brti=b,quote=q,cut=cut)


def fresh_frame(v,source,evaluator,now):
    a,b,q,cut=(source[k] for k in ('anchor','brti','quote','cut'))
    check_anchor(a)
    ident=dict(contract=a['ticker'],target=a['target'],official_open=a['opened'],official_close=a['closed'])
    if (any(v[k]!=ident[k] for k in ident) or a['decision']!=v['feature_cutoff']
        or not a['captured']<=cut<=now or q.get('status')!='AVAILABLE'
        or any(q['official_identity'][k]!=ident[k] for k in ident)
        or not q['exchange_ts']<=q['accepted_ts']<=q['published_ts']<=q['served_ts']<=cut
        or not now<q['expires_at']<=min(a['closed'],q['exchange_ts']+6)):
        raise ValueError('REVALIDATION_IDENTITY_OR_CLOCK')
    values=[q[k] for k in ('up_bid','up_ask','down_bid','down_ask')]
    # Evaluation uses only causal, native-retained BTC history; no fast samples
    # are appended to that history, and no native model instance is touched.
    f=dict(kind='READ_ONLY_REVALIDATION',native_epoch=v['native_epoch'],native_sequence=v['native_sequence'],
        captured_ts=cut,feature_cutoff=cut,**ident,btc_price=a['btc']['value'],
        btc_source=a['btc']['source'],btc_received=a['btc']['received'],artifact=a['artifact'],weights=a['weights'],
        brti=dict(value=b['value'],cf_ts=b['cf_ts'],ready=True,delivery=dict(owner_epoch=b['owner_epoch'],observed_ts=b['observed_ts'])),
        quote=dict(ticker=a['ticker'],source_time=iso(cut),close_ms=int(a['closed']*1000),
            exchange_ts_ms=q['exchange_ts']*1000,consumed_ms=q['accepted_ts']*1000,
            epoch=q['epoch'],sid=q['sid'],seq=q['sequence'],market_id=q['market_id'],quotes=values),
        **dict(zip(('up_bid','up_ask','down_bid','down_ask'),values)))
    # Reject bad clocks before any expensive inference.
    if not (0<=now-b['cf_ts']<=5 and b['cf_ts']<=b['observed_ts']<=cut
            and a['btc']['source']<=a['btc']['received']<=a['decision'] and 0<=now-a['btc']['source']<=10):
        raise ValueError('REVALIDATION_SOURCE_EXPIRED_OR_FUTURE')
    if (b['cf_ts']+1e-6<v['published_ts']-v['health']['brti_age']
        or q['exchange_ts']+1e-6<v['published_ts']-v['health']['quote_age']):
        raise ValueError('REVALIDATION_SOURCE_BEFORE_NATIVE')
    assessment=evaluator.evaluate(dict(anchor=a,cut=cut,brti=dict(value=b['value'])),values)
    up,down=assessment['probability_up'],assessment['probability_down']
    side='UP' if up>=down else 'DOWN';p=max(up,down);ask=f[side.lower()+'_ask']
    f['fair']=dict(side=side,up_fair=up,down_fair=down,fair=p,ask=ask,edge=p-ask,
        dist_over_range5=assessment['dist_over_range5'])
    return f


def agrees(v,f,now):
    raw,_=protected_frame(f,now)
    # Compare every frozen gate, not merely the resulting PASS/ready flag.
    for lane in ('early','final'):
        native=v.get('historical_early',v[lane]) if lane=='early' else v[lane]
        for field in ('ready','side','conditions'):
            if raw[lane][field]!=native[field]:return False
    if v['early'].get('policy') in ('EARLY_SUPPORTED_VALUE_V1','EARLY_CAUSAL_VALUE_V2') or v.get('management'):
        # This independent display evaluator does not reproduce the exact causal
        # momentum features. It must not claim renewed entry/exit agreement.
        raise ValueError('NATIVE_MOMENTUM_MANAGEMENT_NOT_REVALIDATED; WAIT_FOR_NATIVE_PUBLICATION')
    o=v.get('origin')
    left=f['official_close']-now
    phase='3M_GUARD' if left<=180 else '5M_CAUTION' if left<=300 else 'NORMAL'
    if phase!=v['phase']:return False
    if not o:return v['early']['guidance']=='PASS'
    final=v['final'];h=final['helper'];side=o['side']
    strong=raw['final']['ready'] and raw['final']['side']==side
    if strong!=h['confirmed']:return False
    # Same final side + same strong flag cannot newly latch protection or
    # saw_strong_final. The existing latch is neither set nor cleared here.
    held=f['fair'][side.lower()+'_fair']
    prior_up=(final['probability_up']-final['confidence_change'] if final['confidence_change'] is not None
              else o['entry_provenance']['fair']['up_fair'])
    prior=prior_up if side=='UP' else 1-prior_up
    # Numeric model/trend labels remain explicitly native observations. Only
    # their implication for guidance/context is confirmed; no new helper event.
    bgap=f['brti']['value']-f['target'];gap=f['btc_price']-f['target']
    state=('MIXED' if not raw['final']['ready'] and (abs(bgap)<=11 or (bgap>0)!=(gap>0)
           or raw['final']['side']!=('UP' if gap>0 else 'DOWN')) else 'ALIGNED' if raw['final']['ready'] else 'UNCONFIRMED')
    if state!=final['context_state']:return False
    movement=f[side.lower()+'_bid']-o['original_ask'];mfe=v['position_path'].get('mfe')
    ctx=context(side,left,btc=f['btc_price'],brti=f['brti']['value'],target=f['target'],
        weakening=held<prior-1e-12 or state=='MIXED',giveback=mfe is not None and movement<mfe-1e-12)
    return ctx==v['context']


class Revalidator:
    def __init__(self,evaluator=None,clock=time.time):
        self.evaluator=evaluator or FairAssessment();self.clock=clock
        self.key=None;self.latest=None;self.previous_source=None

    def step(self,v,source):
        key=binding(v)
        if key!=self.key:self.key,self.previous_source=key,None
        result=dict(schema=SCHEMA,binding=key,status='REFRESHING',reason='REVALIDATION_PENDING',
            signal_only=True,orders=False,authority='PRESENTATION_CONFIRMATION_ONLY')
        try:
            if v['status'] not in ('PASS','AVAILABLE'):raise ValueError('NATIVE_UNAVAILABLE')
            f=fresh_frame(v,source,self.evaluator,self.clock())
            now=self.clock();expires=qualify(f,now)
            agreement=agrees(v,f,now)
            q=f['quote'];b=f['brti']
            progress=(b['delivery']['owner_epoch'],b['cf_ts'],b['value'],q['epoch'],q['sid'],q['seq'],q['exchange_ts_ms'],tuple(q['quotes']))
            old=self.previous_source
            if old and (old[0]!=progress[0] or old[3]!=progress[3] or old[4]!=progress[4]
                or progress[1]<old[1] or (progress[1]==old[1] and progress[2]!=old[2])
                or progress[5]<old[5] or progress[6]<old[6] or (progress[5]==old[5] and progress[6:]!=old[6:])):
                raise ValueError('REVALIDATION_OWNER_OR_SOURCE_CHANGED_WAIT_NATIVE')
            self.previous_source=progress
            # Time-gate/phase boundaries cannot be crossed on an old confirmation.
            boundaries=[f['official_close']-x for x in (600,480,360,300,180,120) if f['official_close']-x>now]
            if boundaries:expires=min(expires,min(boundaries))
            result.update(status='AGREES' if agreement else 'CHANGED',reason='FROZEN_GATES_AGREE' if agreement else 'NEWER_INFORMATION_DIFFERS',checked_ts=now,expires_at=expires,
                native_epoch=v['native_epoch'],native_sequence=v['native_sequence'],official_identity=v['official_identity'],
                source=dict(brti=b['cf_ts'],brti_received=b['delivery']['observed_ts'],brti_epoch=b['delivery']['owner_epoch'],
                    btc=f['btc_source'],btc_received=f['btc_received'],quote=q['exchange_ts_ms']/1000,
                    quote_accepted=q['consumed_ms']/1000,quote_epoch=q['epoch'],sid=q['sid'],sequence=q['seq'],market_id=q['market_id'],cut=f['feature_cutoff']),
                prices={k:f[k] for k in ('up_bid','up_ask','down_bid','down_ask')})
        except (ValueError,KeyError,TypeError) as exc:
            result['reason']=str(exc)
        self.latest=pack(result)
        return result

    def unavailable(self,v,reason):
        # No invented confirmation after source/worker failure.
        self.latest=pack(dict(schema=SCHEMA,binding=binding(v),status='REFRESHING',reason=reason,
            authority='PRESENTATION_CONFIRMATION_ONLY',signal_only=True,orders=False))


def apply(v,confirmation,now):
    """Information only. Never renew or revoke a committed native action lease."""
    out=deepcopy(v)
    info=dict(status='REFRESHING',authority='INFORMATION_ONLY',signal_only=True,orders=False)
    if (confirmation and confirmation.get('binding')==binding(v)
            and confirmation.get('schema')==SCHEMA and confirmation.get('signal_only') is True
            and confirmation.get('orders') is False):
        try:
            s=confirmation['source'];i=v['official_identity']
            if (confirmation['status'] in ('AGREES','CHANGED')
                    and confirmation['native_epoch']==v['native_epoch']
                    and confirmation['native_sequence']==v['native_sequence']
                    and confirmation['official_identity']==i
                    and v['published_ts']<=s['cut']<=confirmation['checked_ts']<=now<confirmation['expires_at']
                    and confirmation['expires_at']<=min(i['official_close'],s['brti']+5,s['btc']+10,s['quote']+6)):
                info.update(status=confirmation['status'],reason=confirmation['reason'])
        except (KeyError,TypeError,ValueError):pass
    out.update(served_ts=now,presentation_information=info)
    return out
