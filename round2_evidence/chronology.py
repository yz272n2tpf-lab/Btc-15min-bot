"""Passive validation of explicit event records; never generates trading events."""
from copy import deepcopy
from decimal import Decimal,InvalidOperation
import hashlib
from btc15_directional_signal_authority_v1 import pack,utc
from btc15_external_clock_guard_v1 import elapsed

def price(v):
    if type(v) is not str:raise ValueError('ORIGINAL_DECIMAL_REQUIRED')
    try:d=Decimal(v)
    except InvalidOperation:raise ValueError('INVALID_PRICE')
    if not d.is_finite() or not 0<=d<=1:raise ValueError('INVALID_PRICE')
    return d

def final_relation(final,origin):
    """Descriptive relation only. Not readiness, confirmation or guidance authority."""
    if not origin:return 'UNAVAILABLE_NO_EXPLICIT_ORIGIN'
    if (not isinstance(final,dict) or final.get('source')!='FROZEN_V4_6_FINAL' or type(final.get('ready')) is not bool
        or final.get('side') not in ('UP','DOWN') or type(final.get('confidence')) not in (int,float)
        or not 0<=final['confidence']<=1):return 'UNAVAILABLE_INVALID_FINAL'
    if final['side']!=origin['side']:return 'OPPOSING_READY' if final['ready'] else 'OPPOSING_NOT_READY'
    return 'SAME_SIDE_READY' if final['ready'] else 'SAME_SIDE_NOT_READY'

class EventAudit:
    """Future detached explicit event-port format. Not a live producer or manager.
    Internal maps are audit indexes; no strategy origin/state is touched.
    Rejected records leave all indexes unchanged and remain caller-owned evidence.
    """
    def __init__(self,*,producer_ids):
        self.producer_ids=dict(producer_ids);self.origins={};self.events={};self.terminals={};self.last_time={};self.population={};self.lifecycle={}
    def accept(self,event):
        e=deepcopy(event);lane=e.get('lane');kind=e.get('kind');eid=e.get('event_id');producer=e.get('producer_id')
        if lane not in ('EARLY','FINAL','SCALP','SHARED') or self.producer_ids.get(producer)!=lane:raise ValueError('EVENT_PRODUCER_BINDING')
        if not isinstance(eid,str) or not eid:raise ValueError('EVENT_ID_MISSING')
        h=hashlib.sha256(pack(e).encode()).hexdigest()
        if eid in self.events:
            if self.events[eid]!=h:raise ValueError('EVENT_ID_CONFLICT')
            return 'DUPLICATE'
        t=utc(e['observed_utc']);contract=e['contract']
        if not isinstance(contract,str) or not contract:raise ValueError('CONTRACT_ID')
        key=(producer,e['runtime_epoch']);last=self.last_time.get(key)
        if last is not None and t<last:raise ValueError('EVENT_ORDER')
        oid=e.get('origin_id');new_origin=None;terminal=False;next_lifecycle=None
        if kind in ('EARLY_ORIGIN','SCALP_ORIGIN'):
            if lane!=kind.split('_')[0] or not isinstance(oid,str) or not oid:raise ValueError('ORIGIN_OWNER')
            if oid in self.origins:raise ValueError('IMMUTABLE_ORIGIN')
            if e['side'] not in ('UP','DOWN'):raise ValueError('ORIGIN_SIDE')
            ask=price(e['original_ask']);bid=price(e['original_bid'])
            if not 0<ask or bid>ask:raise ValueError('ORIGIN_QUOTES')
            if not e.get('quote_id') or not e.get('origin_evidence_id'):raise ValueError('ORIGIN_PROVENANCE')
            if lane=='SCALP':
                if e.get('evidence_role') not in ('SHADOW','USER_GUIDANCE'):raise ValueError('SCALP_EVIDENCE_ROLE')
                if e.get('lifecycle_sequence')!=0 or not isinstance(e.get('initial_state'),str):raise ValueError('INITIAL_LIFECYCLE_STATE')
                next_lifecycle=(0,e['initial_state'])
                prior=e.get('prior_signal_id')
                if prior:
                    p=self.origins.get(prior);term=self.terminals.get(e.get('prior_terminal_event_id'))
                    if not p or p['lane']!='SCALP' or p['contract']!=contract or not term or term['origin_id']!=prior:raise ValueError('SERIAL_PREDECESSOR')
                    if p['evidence_role']!=e['evidence_role'] or term.get('evidence_role')!=e['evidence_role']:raise ValueError('SERIAL_SHADOW_GUIDANCE_CONFLICT')
                    allowed={'SCALP_PROTECTION_EXIT_GUIDANCE','SCALP_SHADOW_EXIT','SCALP_TARGET','SCALP_STOP'}
                    if e.get('serial_policy')=='ALLOW_UNARMED_RETIREMENT':allowed.add('SCALP_RETIREMENT_UNARMED')
                    if term['kind'] not in allowed or not utc(term['observed_utc'])<t:raise ValueError('SERIAL_TERMINAL_ORDER')
                    expected='CONTINUATION' if p['side']==e['side'] else 'REVERSAL'
                    if e.get('lane_label')!=expected:raise ValueError('SERIAL_LABEL')
                elif e.get('lane_label')!='FIRST':raise ValueError('SERIAL_LABEL')
                elif any(p['lane']=='SCALP' and p['contract']==contract and p.get('evidence_role')==e['evidence_role'] for p in self.origins.values()):raise ValueError('MISSING_SERIAL_PREDECESSOR')
            new_origin=e
        elif lane=='FINAL':
            if kind!='FINAL_PUBLICATION':raise ValueError('FINAL_NOT_AUTHORITY')
            if oid is not None:
                o=self.origins.get(oid)
                if not o or o['lane']!='EARLY' or o['contract']!=contract:raise ValueError('FINAL_ORIGIN_LINK')
                if not e.get('explicit_link_evidence_id'):raise ValueError('FINAL_LINK_INFERRED')
        elif lane=='SCALP' and kind not in ('SCALP_SUPPRESSED','SCALP_NO_SIGNAL','SCALP_UNAVAILABLE'):
            o=self.origins.get(oid)
            if not o or o['lane']!='SCALP' or o['contract']!=contract:raise ValueError('SCALP_OWNERSHIP')
            if e.get('evidence_role')!=o['evidence_role']:raise ValueError('SHADOW_GUIDANCE_CONFLICT')
            if kind not in ('SCALP_ARM','SCALP_PEAK','SCALP_TARGET','SCALP_STOP','SCALP_PROTECTION_EVALUATION','SCALP_PROTECTION_EXIT_GUIDANCE','SCALP_SHADOW_EXIT','SCALP_RETIREMENT_UNARMED','SCALP_RETIREMENT_EXPIRED','SCALP_ARMED_NO_EXIT','SCALP_UNQUALIFIED_ENTRY'):raise ValueError('UNKNOWN_LIFECYCLE_KIND')
            if oid in [v['origin_id'] for v in self.terminals.values()]:raise ValueError('TERMINAL_ORIGIN_MUTATION')
            seq,state=self.lifecycle[oid]
            if type(e.get('lifecycle_sequence')) is not int or e['lifecycle_sequence']!=seq+1 or e.get('prior_state')!=state or not isinstance(e.get('next_state'),str):raise ValueError('LIFECYCLE_GAP')
            next_lifecycle=(e['lifecycle_sequence'],e['next_state'])
            if kind in ('SCALP_TARGET','SCALP_STOP','SCALP_PROTECTION_EXIT_GUIDANCE','SCALP_SHADOW_EXIT'):
                if not utc(o['observed_utc'])<t or not e.get('trigger_quote_id'):raise ValueError('EXIT_QUOTE_ORDER')
                price(e['exit_bid'])
                if kind=='SCALP_SHADOW_EXIT' and e.get('user_guidance') is not False:raise ValueError('SHADOW_NOT_GUIDANCE')
                if kind=='SCALP_PROTECTION_EXIT_GUIDANCE' and (o['evidence_role']!='USER_GUIDANCE' or e.get('user_guidance') is not True):raise ValueError('GUIDANCE_NOT_ESTABLISHED')
                terminal=True
            if kind.startswith('SCALP_RETIREMENT'):
                if e.get('exit_bid') is not None or e.get('user_guidance') is not False:raise ValueError('RETIREMENT_NOT_EXIT')
                terminal=True
        elif lane=='EARLY':
            if kind not in ('EARLY_CANDIDATE','EARLY_REJECTED','EARLY_NO_SIGNAL','EARLY_UNAVAILABLE'):raise ValueError('NO_NEW_DIRECTIONAL_EXIT')
        elif lane=='SHARED':
            if kind not in ('CONTRACT_ELIGIBLE','QUOTE','GAP','WAIT','RECOVERY','RESTART','CLOSEOUT','CAPTURE_START','CAPTURE_END'):raise ValueError('SHARED_KIND')
            if kind=='QUOTE':
                for side in ('up','down'):
                    if price(e[side+'_bid'])>price(e[side+'_ask']):raise ValueError('CROSSED_QUOTE')
        if new_origin:self.origins[oid]=new_origin
        if next_lifecycle:self.lifecycle[oid]=next_lifecycle
        if terminal:self.terminals[eid]=e
        self.events[eid]=h;self.last_time[key]=t
        self.population.setdefault(contract,[]).append(eid)
        return 'RECORDED'

def later_gain(origin,quote,*,origin_bound,quote_bound):
    """Exact descriptive BID minus original ASK, only provably strictly later."""
    if origin['contract']!=quote['contract']:raise ValueError('QUOTE_CONTRACT')
    if elapsed(quote_bound.witness(quote['observed_utc']),origin_bound.witness(origin['observed_utc']))[0]<=0:raise ValueError('QUOTE_ORDER_UNAVAILABLE')
    return (price(quote[origin['side'].lower()+'_bid'])-price(origin['original_ask']))*100
