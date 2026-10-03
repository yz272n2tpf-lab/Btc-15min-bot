"""V8.1 event-only chronology; consumes its existing accepted publications.

Original ask is immutable. Later bids must have a strictly later accepted
quote identity/time and the same contract/side. Movement/target races are
observations, never promised fills or a newly selected exit policy.
"""
import os
from pathlib import Path
import time

from btc15_ladder_journal_v1 import Worker,digest,SCHEMA

CANDIDATE='BTC15_LADDER_COMPLETION_20261003_V1'
ROOT=Path(os.getenv('BTC15_LADDER_DATA_ROOT','/data/btc15_ladders_v1'))
TARGETS=(8,10,15,20,30)


class Scalp:
    def restore(self,saved):
        self.origin=saved.get('origin')
        self.path=saved.get('path',{})
        self.last_at=saved.get('last_at')

    def checkpoint(self):
        return dict(origin=self.origin,path=self.path,last_at=self.last_at)

    def process(self,s,now):
        from btc15_v81_qualified_inputs_v1 import require_qualified
        event=s.get('last_signal_event') or {}
        record=dict(schema=SCHEMA,candidate=CANDIDATE,kind='SCALP_OBSERVATION',
            contract=s.get('contract'),published_ts=now,signal_only=True,orders=False)
        view=dict(candidate=CANDIDATE,published_ts=now,status='UNAVAILABLE',contract=s.get('contract'),
            build=os.getenv('RAILWAY_GIT_COMMIT_SHA'),signal_only=True,orders=False)
        try:
            p=s.get('input_provenance') or {}
            q=p.get('quote') or {}
            row=dict(q,ticker=s.get('contract'),target=p.get('target'),brti=(p.get('brti') or {}).get('value'),input_provenance=p)
            require_qualified(row,now)
            expires=min(p['close_ts'],p['brti']['source_ts_ms']/1000+5,q['source_ts_ms']/1000+6)
            at=q['validated_at_ms']/1000
            if self.last_at is not None and at<self.last_at:
                raise ValueError('OUT_OF_ORDER_ACCEPTED_QUOTE')
            continuity='OBSERVED' if self.last_at is not None and 0<=at-self.last_at<=6 else 'START_OR_MISSING_INTERVAL'
            record.update(provenance=p,continuity=continuity)
            self.last_at=at
            terminal=None
            if self.origin and (now>=self.origin['deadline'] or s.get('contract')!=self.origin['contract']):
                terminal=dict(origin=self.origin,path=self.path,status='HORIZON' if s.get('contract')==self.origin['contract'] else 'ROLLOVER',
                              executable_exit=None,complete_path=self.path.get('missing',True) is False and continuity=='OBSERVED')
                record['terminal']=terminal
                self.origin=None;self.path={}
            if s.get('active') and event:
                entry=event['entry_provenance'];side=event['side'];ts=event['signal_ts'];ask=event['entry_price']
                erow=dict(entry['quote'],ticker=event['contract'],target=entry['target'],
                          brti=entry['brti']['value'],input_provenance=entry)
                require_qualified(erow,ts)
                if (event['contract']!=s['contract'] or side not in ('UP','DOWN')
                        or ask!=entry['quote'][side.lower()+'_ask'] or not ts<=now<min(ts+180,p['close_ts'])):
                    raise ValueError('ORIGINAL_ENTRY_MISMATCH')
                oid=digest([CANDIDATE,event['contract'],side,ts,entry['quote']['epoch'],entry['quote']['sequence']])
                if self.origin is None:
                    self.origin=dict(origin_id=oid,contract=event['contract'],side=side,signal_ts=ts,
                        original_ask=ask,entry_provenance=entry,first_journal_ts=now,
                        deadline=min(ts+180,entry['close_ts']),route=event['route'],manual_fill=None)
                    self.path=dict(mfe=None,mae=None,samples=0,missing=now-ts>3.5,last_quote=None,
                        targets={str(t):None for t in TARGETS},stop=None,armed5=False,armed10=False,
                        giveback=None,terminal=None)
                    record['event']='SCALP_SIGNAL';record['origin']=self.origin
                if self.origin['origin_id']!=oid or self.origin['original_ask']!=ask:
                    raise ValueError('ACTIVE_ORIGIN_REPLACEMENT')
                originq=entry['quote'];lastq=self.path['last_quote'] or originq
                later=(q['source_ts_ms']/1000>ts and q['source_ts_ms']>lastq['source_ts_ms'] and
                    q['validated_at_ms']/1000>ts and
                    (q['epoch']!=lastq['epoch'] or (q['sid']==lastq['sid'] and q['sequence']>lastq['sequence'])))
                if (continuity!='OBSERVED' and self.path['samples']>0) or q['epoch']!=lastq['epoch']:
                    self.path['missing']=True
                if later:
                    bid=q[side.lower()+'_bid'];gain=round(bid-ask,10)
                    self.path['samples']+=1
                    self.path['mfe']=gain if self.path['mfe'] is None else max(gain,self.path['mfe'])
                    self.path['mae']=gain if self.path['mae'] is None else min(gain,self.path['mae'])
                    hit=dict(ts=at,quote_source_ts=q['source_ts_ms']/1000,bid=bid,delta_cents=gain*100,
                             seconds_since_signal=at-ts)
                    if gain<=-.10 and self.path['stop'] is None:self.path['stop']=hit
                    for t in TARGETS:
                        if gain>=t/100 and self.path['targets'][str(t)] is None:
                            self.path['targets'][str(t)]=dict(hit,stop_first=self.path['stop'] is not None)
                    self.path['armed5']|=gain>=.05;self.path['armed10']|=gain>=.10
                    self.path['giveback']=self.path['mfe']-gain
                    self.path['last_quote']=dict(q)
                    record['later_bid']=dict(hit,side=side,origin_id=oid,quote=q)
            elif self.origin and not terminal:
                self.path['missing']=True
            record.update(origin_id=(self.origin or {}).get('origin_id'),path=self.path)
            view.update(status='AVAILABLE' if self.origin else 'PASS',expires_at=expires,
                origin=self.origin,path=self.path,primary_wait_reason=s.get('primary_wait_reason'),
                movement_state=s.get('status'),entry_band=[.30,.45],target_awareness=[.25,.35],
                executable_current_bid=(q.get(self.origin['side'].lower()+'_bid') if self.origin else None),
                exit_guidance=None,exit_reason='EXISTING_180S_LIFECYCLE_NO_SELECTED_STOP_OR_TRAIL',
                signal_frequency_event=record.get('event'),continuity=continuity,
                observed_target_cents=list(TARGETS),comparison_stop_cents=10,
                observations_are_fills=False,terminal=terminal)
        except (ValueError,KeyError,TypeError) as exc:
            if self.origin:self.path['missing']=True
            record['unavailable_reason']=str(exc);view['reason']=str(exc)
        return record,self.checkpoint(),view


_worker=None

def start():
    global _worker
    if _worker is None:_worker=Worker(ROOT,'v81',Scalp())

def offer(state):
    if _worker is not None:
        # Caller supplies a detached publication; no mutable source is retained.
        _worker.offer(state)
