"""Independent setup, expiring ticket, and explicit management-origin state machines."""
from copy import deepcopy
from dataclasses import asdict
from candidates.early_value_20261011.engine import digest
from .assessment import Rules,SAFETY,finite,validate_row,assess,source_reasons
from .management import Origin,Management

POLICY='EARLY_TWO_SIDED_REBUILD_20261012'

class Engine:
    def __init__(self,*,rules=None,permit_synthetic_support=False):
        self.rules=rules or Rules();self.permit_synthetic_support=permit_synthetic_support
        self.contract=None;self.target=None;self.close=None;self.last=None;self.history=[]
        self.seen_contracts=set();self.seen_publications=set();self.clock=None
        self.setups={};self.setup_archive=[];self.tickets=[];self.current_ticket=None
        self.managers=[];self.events=[];self.last_assessments={};self.seen_events=set()
        self.last_output=None

    def emit(self,event,now,**kw):
        self.events.append(dict(**SAFETY,event=event,time=now,**deepcopy(kw)))

    def cancel(self,now,reasons,status='CANCELED'):
        t=self.current_ticket
        if t and t['status']=='VALID':
            t.update(status=status,ended_at=now,reasons=list(reasons))
            self.emit('TICKET_'+status,now,ticket=t)
            setup=self.setups.get(t['side'])
            if setup and setup['id']==t['setup_id']:setup['confirm_since']=None

    def tick(self,now):
        if not finite(now) or (self.clock is not None and now<self.clock):
            self.cancel(self.clock,['INVALID_OR_BACKWARD_CLOCK'])
            return self.output(['INVALID_OR_BACKWARD_CLOCK'])
        self.clock=now
        t=self.current_ticket
        if t and t['status']=='VALID' and now>=t['expires_at']:
            self.cancel(now,['TICKET_EXPIRED_WITHOUT_NEW_OBSERVATION'],'EXPIRED')
        if self.last and now>=self.last['time']+self.rules.max_age:
            for setup in self.setups.values():setup['confirm_since']=None;setup['confirmed']=False;setup['reset_since']=None
            for m in self.managers:
                if not m.closed:m.unavailable('SOURCE_EXPIRED_WITHOUT_NEW_OBSERVATION')
        return self.output([])

    def output(self,reasons):
        ticket=deepcopy(self.current_ticket)
        valid=bool(ticket and ticket['status']=='VALID' and self.clock is not None and self.clock<ticket['expires_at'])
        panels=[]
        for side,a in self.last_assessments.items():
            s=self.setups.get(side)
            panels.append(dict(**deepcopy(a),setup_id=s['id'] if s else None,
                confirmed=bool(s and s.get('confirmed')),panel='EARLY BUY',
                display='BUY' if valid and ticket['side']==side else 'WATCH',
                label='qualified expiring research ticket' if valid and ticket['side']==side else 'setup developing',
                research_qualified=valid and ticket['side']==side,live_recommendation_authorized=False))
        result=dict(**SAFETY,policy=POLICY,time=self.clock,entry=panels,ticket=ticket,
                    management=[m.view() for m in self.managers],reasons=list(reasons),
                    research_qualified=valid,manual_fill=None,realized_profit=None)
        self.last_output=deepcopy(result)
        return result

    def unavailable(self,r,reasons):
        self.cancel(self.clock,reasons)
        self.history=[]
        for setup in self.setups.values():
            setup['confirm_since']=None;setup['confirmed']=False;setup['reset_since']=None
        for m in self.managers:m.update([],r,unavailable=';'.join(reasons))
        self.last_assessments={side:dict(side=side,recognized=False,recognition_blockers=list(reasons),
                execution_blockers=[],source_blockers=list(reasons),economics=dict(ready=False,status='UNESTIMATED',
                reasons=['NO_SUPPORTED_CONDITIONAL_RESALE_ESTIMATE'])) for side in ('UP','DOWN')}
        return self.output(reasons)

    def process(self,row):
        r=deepcopy(row);q=self.rules
        now=r.get('received')
        if not finite(now) or self.clock is not None and now<self.clock:
            return self.unavailable(r,['INVALID_OR_BACKWARD_RECEIPT'])
        self.tick(now)
        bad=validate_row(r)
        if bad:return self.unavailable(r,bad)
        if r['publication_id'] in self.seen_publications:
            if self.last and r==self.last:return self.output(['DUPLICATE_PUBLICATION'])
            return self.unavailable(r,['CONFLICTING_OR_REUSED_PUBLICATION'])
        if self.last and r['time']<=self.last['time']:
            return self.unavailable(r,['NONADVANCING_SOURCE_TIME'])
        close=r['time']+r['left']
        if r['contract']!=self.contract:
            if r['contract'] in self.seen_contracts or self.close is not None and close<=self.close:
                return self.unavailable(r,['OLDER_CONTRACT'])
            self.cancel(now,['CONTRACT_ROLLOVER'])
            self.setup_archive.extend(deepcopy(list(self.setups.values())))
            self.contract=r['contract'];self.target=r['target'];self.close=close
            self.seen_contracts.add(self.contract);self.history=[];self.setups={}
        if r['target']!=self.target or abs(close-self.close)>1:
            return self.unavailable(r,['CONTRACT_TARGET_CLOSE_CONFLICT'])
        gap=bool(self.last and (r['time']-self.last['time']>q.max_gap or r['source_epoch']!=self.last['source_epoch']))
        if gap:
            self.cancel(now,['SOURCE_GAP_OR_EPOCH_CHANGE'])
            self.history=[]
            for s in self.setups.values():s['confirm_since']=None;s['confirmed']=False;s['reset_since']=None
            for m in self.managers:m.unavailable('SOURCE_GAP_OR_EPOCH_CHANGE')
        self.last=r;self.seen_publications.add(r['publication_id'])
        self.history.append(r);self.history=[z for z in self.history if z['time']>=r['time']-q.lookback-q.max_gap]
        assessments={side:assess(self.history,r,side,q,self.permit_synthetic_support) for side in ('UP','DOWN')}
        for side,a in assessments.items():
            x=a['features'];s=self.setups.get(side)
            # Market reset requires adverse delivered evidence, never a cheap quote or outage.
            adverse=bool(x and max(x['move_short'],x['brti_short'])<=0 and min(x['move_short'],x['brti_short'])<0)
            if s:
                if adverse:
                    if s['reset_since'] is None:s['reset_since']=now
                    if now-s['reset_since']>=q.reset_seconds:
                        s['status']='RESET';s['reset_at']=now
                        self.setup_archive.append(deepcopy(s));del self.setups[side]
                        self.emit('SETUP_RESET',now,setup_id=s['id'],side=side)
                        if self.current_ticket and self.current_ticket['setup_id']==s['id']:self.cancel(now,['GENUINE_DIRECTIONAL_RESET'])
                        s=None
                else:s['reset_since']=None
            if a['recognized'] and s is None:
                s=dict(id=digest([POLICY,r['contract'],side,r['publication_id']]),contract=r['contract'],side=side,
                    recognized_at=now,recognition_source_time=r['time'],recognition_ask=a['ask'],
                    initial_context=x['context'],status='DEVELOPING',confirm_since=now,confirmed=False,
                    reset_since=None,consumed=False,ticket_sequence=0,last_ticket_id=None)
                self.setups[side]=s
                self.emit('SETUP_RECOGNIZED',now,setup=deepcopy(s),features=x)
            if s:
                if a['recognized']:
                    if s['confirm_since'] is None:s['confirm_since']=now
                    confirmed=now-s['confirm_since']>=q.confirm_seconds
                    if confirmed and not s['confirmed']:
                        self.emit('SETUP_CONFIRMED',now,setup_id=s['id'],side=side,ask=a['ask'],context=x['context'])
                    s['confirmed']=confirmed
                else:s['confirm_since']=None;s['confirmed']=False
            # This is a mechanism-only certificate, never an estimate or real-data backdoor.
            if self.permit_synthetic_support and r.get('evidence_class')=='SYNTHETIC_FIXTURE':
                a['economics'].update(ready=True,status='SYNTHETIC_MECHANISM_ONLY',reasons=[],
                                      support_not_empirical=True)
            a['authorization_blockers']=(a['recognition_blockers']+a['execution_blockers']+
                a['source_blockers']+a['economics']['reasons']+
                ([] if s and s['confirmed'] else ['ALGORITHMIC_CONFIRMATION_INCOMPLETE'])+
                (['SETUP_ALREADY_ENTERED'] if s and s['consumed'] else []))
        self.last_assessments=assessments
        for m in self.managers:m.update(self.history,r)
        ready=[s for s,a in assessments.items() if not a['authorization_blockers']]
        occupied=any(m.origin.kind=='MANUAL_CONFIRMED' and not m.closed for m in self.managers)
        if occupied:
            for a in assessments.values():a['authorization_blockers'].append('CONFIRMED_ENTRY_ALREADY_TRACKED_NO_ADD_HEDGE_OR_REVERSAL')
            ready=[]
        if len(ready)>1:
            for a in assessments.values():a['authorization_blockers'].append('OPPOSING_QUALIFIED_CANDIDATES_AMBIGUOUS')
            ready=[]
        t=self.current_ticket
        if t and t['status']=='VALID':
            a=assessments[t['side']]
            if t['side'] not in ready:self.cancel(now,a['authorization_blockers'] or ['QUALIFICATION_LOST'])
            else:
                t.update(current_ask=a['ask'],current_bid=a['bid'],quote_time=r['time'],
                         publication_id=r['publication_id'],expires_at=min(r['time']+q.max_age,self.close),
                         economics=deepcopy(a['economics']))
                self.emit('TICKET_REFRESHED',now,ticket_id=t['id'],setup_id=t['setup_id'],ask=a['ask'])
        if len(ready)==1 and not (self.current_ticket and self.current_ticket['status']=='VALID'):
            side=ready[0];s=self.setups[side];a=assessments[side]
            s['ticket_sequence']+=1
            t=dict(id=digest([s['id'],'TICKET',s['ticket_sequence'],r['publication_id']]),
                   setup_id=s['id'],predecessor_ticket_id=s['last_ticket_id'],sequence=s['ticket_sequence'],
                   contract=r['contract'],side=side,issued_at=now,original_ask=a['ask'],current_ask=a['ask'],
                   current_bid=a['bid'],quote_time=r['time'],publication_id=r['publication_id'],
                   expires_at=min(r['time']+q.max_age,self.close),status='VALID',reasons=[],
                   economics=deepcopy(a['economics']),**SAFETY)
            s['last_ticket_id']=t['id'];self.current_ticket=t;self.tickets.append(t)
            self.emit('RESEARCH_BUY_TICKET',now,ticket=t)
        return self.output([])

    def confirm_entry(self,event,now):
        """Explicit manual confirmation input; this method cannot place or infer an order."""
        self.tick(now);t=self.current_ticket
        fail=[]
        if not isinstance(event,dict):return dict(**SAFETY,accepted=False,reasons=['ENTRY_EVENT_REQUIRED'])
        if not event.get('id') or event['id'] in self.seen_events:fail.append('DUPLICATE_OR_MISSING_EVENT')
        if not t or t['status']!='VALID' or event.get('ticket_id')!=t['id']:fail.append('CURRENT_VALID_TICKET_REQUIRED')
        if not self.last:fail.append('CURRENT_EVIDENCE_REQUIRED')
        if not fail:
            a=self.last_assessments[t['side']]
            fail+=a['authorization_blockers']+source_reasons(self.last,now,fixture_mode=self.permit_synthetic_support)
            if now-t['issued_at']<self.rules.manual_seconds:fail.append('MANUAL_REACTION_BUDGET_NOT_ELAPSED')
            if (event.get('contract')!=t['contract'] or event.get('side')!=t['side'] or
                not finite(event.get('price')) or event['price']!=t['current_ask'] or
                not finite(event.get('quantity')) or event['quantity']<=0 or event.get('observed_at')!=now):
                fail.append('MANUAL_EVENT_IDENTITY_PRICE_SIZE_OR_CLOCK_MISMATCH')
        if fail:return dict(**SAFETY,accepted=False,reasons=fail,manual_fill=None)
        s=self.setups[t['side']]
        origin=Origin(digest([s['id'],event['id'],'MANUAL']),s['id'],t['id'],t['contract'],t['side'],
                      'MANUAL_CONFIRMED',now,event['price'],event['quantity'],event['id'])
        self.managers.append(Management(origin,self.history,self.last,a['features'],self.rules))
        self.seen_events.add(event['id']);s['consumed']=True
        t.update(status='CONSUMED_BY_EXPLICIT_EVENT',ended_at=now)
        self.emit('MANUAL_ENTRY_EVENT_ACCEPTED',now,origin=asdict(origin),
                  actual_observed_elapsed=now-t['issued_at'])
        return dict(**SAFETY,accepted=True,origin=asdict(origin),manual_fill=None,
                    basis='User-supplied confirmation event, not broker verification',actual_observed_elapsed=now-t['issued_at'])

    def start_simulation(self,side,event_id,now):
        """Explicit diagnostic entry, even with unsupported economics. Never creates a BUY ticket."""
        if not finite(now) or self.clock is not None and now<self.clock:
            return dict(**SAFETY,accepted=False,reasons=['INVALID_OR_BACKWARD_CLOCK'])
        self.tick(now)
        a=self.last_assessments.get(side);s=self.setups.get(side)
        if (not event_id or event_id in self.seen_events or not self.last or now!=self.last['received'] or
            not a or not s or not s['confirmed'] or not a['recognized'] or a['execution_blockers'] or
            any(m.origin.setup_id==s['id'] for m in self.managers)):
            return dict(**SAFETY,accepted=False,reasons=['EXPLICIT_SIMULATION_INPUT_NOT_ELIGIBLE'])
        origin=Origin(digest([s['id'],event_id,'SIMULATION']),s['id'],None,self.contract,side,
                      'SIMULATED',now,a['ask'],1,event_id)
        self.managers.append(Management(origin,self.history,self.last,a['features'],self.rules))
        self.seen_events.add(event_id)
        self.emit('EXPLICIT_SIMULATION_STARTED',now,origin=asdict(origin),economic_support=False)
        return dict(**SAFETY,accepted=True,origin=asdict(origin),manual_fill=None)

    def close_entry(self,origin_id,event_id,now):
        if not finite(now) or self.clock is not None and now<self.clock:
            return dict(**SAFETY,accepted=False)
        self.tick(now)
        if not event_id or event_id in self.seen_events:return dict(**SAFETY,accepted=False)
        m=next((m for m in self.managers if m.origin.id==origin_id and not m.closed),None)
        if m is None:return dict(**SAFETY,accepted=False)
        m.closed=True;m.close_event=event_id;self.seen_events.add(event_id)
        self.emit('EXPLICIT_ENTRY_CLOSURE',now,origin_id=origin_id,evidence_id=event_id)
        return dict(**SAFETY,accepted=True,realized_profit=None)
