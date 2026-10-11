"""Causal condition-driven EARLY reducer. Disabled for production by construction.

Research proposals and economically supported historical admissions are distinct.
A time window measures evidence/persistence; it NEVER sets a holding duration.
"""
from copy import deepcopy
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
import math

POLICY = 'EARLY_CONDITION_RESEARCH_V1'


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def fee(p):
    """Conservative whole-cent stress, NOT a verified account/series fee quote."""
    x=Decimal(str(p))
    return float((Decimal('.07')*x*(1-x)).quantize(Decimal('.01'), rounding=ROUND_CEILING))


@dataclass(frozen=True)
class Rules:
    lookback: float = 120
    short: float = 30
    max_gap: float = 15
    max_age: float = 10
    min_left: float = 180  # Provisional entry support boundary, not a hold/exit timer.
    manual_seconds: float = 10
    max_ask: float = .80
    max_spread: float = .03
    min_confidence: float = .75
    persistence: float = .75
    efficiency: float = .30
    gap_range: float = .25
    impulse_range: float = .10
    reserve: float = .02
    confirm_seconds: float = 10
    watch_seconds: float = 10
    exit_seconds: float = 15
    recovery_seconds: float = 15
    reset_seconds: float = 30


def cell_key(r, side):
    return side + ('_LOW' if r[side.lower()+'_ask'] <= .5 else '_HIGH')


def features(history, r, side, rules):
    """Only already delivered, fresh observations from this contract."""
    cutoff=r['time']-rules.lookback
    old=next((x for x in reversed(history) if x['time']<=cutoff), None)
    if old is None or cutoff-old['time']>rules.max_gap:
        return None
    seq=[x for x in history if x['time']>=old['time']]
    if seq[-1]['time'] != r['time']:
        seq.append(r)
    if (any(not x['healthy'] or x['target'] != r['target'] or x['contract'] != r['contract'] for x in seq)
        or any(b['time']-a['time']>rules.max_gap for a,b in zip(seq,seq[1:]))):
        return None
    short=next((x for x in reversed(seq) if x['time']<=r['time']-rules.short),None)
    if short is None or r['time']-rules.short-short['time']>rules.max_gap:
        return None
    sign=1 if side=='UP' else -1
    spread=r[side.lower()+'_ask']-r[side.lower()+'_bid']
    prices=[x['btc'] for x in seq]
    scale=max(max(prices)-min(prices),r['target']*.00001)
    travel=sum(abs(b-a) for a,b in zip(prices,prices[1:]))
    weight=sum(b['time']-a['time'] for a,b in zip(seq,seq[1:]))
    supported=sum((b['time']-a['time']) for a,b in zip(seq,seq[1:])
                  if sign*(a['btc']-a['target'])>0 and sign*(a['brti']-a['target'])>0)
    # Endpoint efficiency measures directional progress vs total noisy path.
    return dict(gap=sign*(r['btc']-r['target']),brti_gap=sign*(r['brti']-r['target']),
        move_short=sign*(r['btc']-short['btc']),move_long=sign*(r['btc']-old['btc']),
        brti_short=sign*(r['brti']-short['brti']),brti_long=sign*(r['brti']-old['brti']),
        quote_short=r[side.lower()+'_bid']-short[side.lower()+'_bid'],
        quote_long=r[side.lower()+'_bid']-old[side.lower()+'_bid'],
        range=scale,efficiency=sign*(r['btc']-old['btc'])/max(travel,.000001),
        persistence=supported/max(weight,.000001),spread=spread,
        p=r['p'] if r['side']==side else 1-r['p'],
        structure_btc=min(sign*z['btc'] for z in seq if z['time']>=short['time']),
        structure_brti=min(sign*z['brti'] for z in seq if z['time']>=short['time']))


def screen(r,x,side,rules):
    if not x: return ['CAUSAL_120S_HISTORY_UNAVAILABLE']
    ask=r[side.lower()+'_ask']; bid=r[side.lower()+'_bid']
    checks=dict(
        PRICE_AND_SPREAD=0<bid<=ask<=rules.max_ask and 0<=x['spread']<=rules.max_spread+1e-9,
        ENTRY_RUNWAY=r['left']-(r['received']-r['time'])>rules.min_left+rules.manual_seconds,
        MODEL_SUPPORT=x['p']>=rules.min_confidence,
        BTC_BRTI_ALIGNMENT=min(x['gap'],x['brti_gap'])>=rules.gap_range*x['range'],
        MULTISCALE_MOMENTUM=min(x['move_long'],x['brti_long'])>0 and min(x['move_short'],x['brti_short'])>=rules.impulse_range*x['range'],
        DIRECTIONAL_PERSISTENCE=x['persistence']>=rules.persistence and x['efficiency']>=rules.efficiency,
        QUOTE_CONFIRMATION=x['quote_long']>=x['spread'] and x['quote_short']>=0,
        FINITE_PRICE_HEADROOM=1-ask-fee(ask)-fee(.5)-max(x['spread'],rules.reserve)>0)
    return [k for k,v in checks.items() if not v]


def economics(r, side, profile, rules):
    ask=r[side.lower()+'_ask'];bid=r[side.lower()+'_bid']
    cost=fee(ask)+fee(.5)+max(ask-bid,rules.reserve)
    key=cell_key(r,side);cell=(profile or {}).get('cells',{}).get(key,{})
    reasons=[]
    if not cell.get('supported'): reasons.append('NO_SUPPORTED_CONDITION_EXIT_COHORT')
    lower=cell.get('gross_gain_lower')
    if lower is None or lower<=cost:reasons.append('INSUFFICIENT_CONDITION_EXIT_NET_EVIDENCE')
    if cell.get('min_left') is None or not cell['min_left']<=r['left']<=cell['max_left']:reasons.append('OUTSIDE_OBSERVED_RUNWAY_SUPPORT')
    if cell.get('min_ask') is None or not cell['min_ask']<=ask<=cell['max_ask']:reasons.append('OUTSIDE_OBSERVED_PRICE_SUPPORT')
    return dict(cell=key,ask=ask,bid=bid,spread=ask-bid,entry_fee_stress=fee(ask),exit_fee_upper_stress=fee(.5),
                execution_reserve=max(ask-bid,rules.reserve),required_gross_gain=cost,
                condition_exit_gain_lower=lower,net_mean_lower=None if lower is None else lower-cost,
                ready=not reasons,reasons=reasons,realized_profit=None)


class Engine:
    """No runtime imports or mutable references to FINAL/SCALP.

proposal_mode executes entry/lifecycle hypotheses to construct development data.
It is explicitly unvalidated. Normal mode requires a supported empirical profile.
Neither mode can produce an actionable production recommendation.
"""
    def __init__(self, profile=None, *, proposal_mode=False, rules=None):
        self.rules=rules or Rules();self.profile=deepcopy(profile);self.proposal_mode=proposal_mode
        self.contract=None;self.close=None;self.target=None;self.history=[];self.last=None
        self.origin=None;self.closed=[];self.terminal=None;self.guidance='PASS'
        self.streaks={};self.reset_seen=False;self.buy_side=None;self.last_identity=None
        self.seen_contracts=set();self.events=[];self.gap_seen=False

    def streak(self,key,condition,t,seconds):
        if not condition:self.streaks.pop(key,None);return False
        start,count=self.streaks.get(key,(t,0));self.streaks[key]=(start,count+1)
        return count+1>=2 and t-start>=seconds

    def emit(self,event,r,reasons,extra=None):
        out=dict(policy=POLICY,mode='UNCALIBRATED_PROPOSAL' if self.proposal_mode else 'PROFILE_SCREENED_REPLAY',
            signal_only=True,orders=False,actionable=False,production_enabled=False,
            event=event,guidance=self.guidance,contract=r.get('contract'),time=r.get('time'),
            side=self.origin['side'] if self.origin else r.get('side'),reasons=reasons,
            origin_id=self.origin['id'] if self.origin else None,realized_profit=None,
            manual_fill=None,warning_owner='EARLY',**(extra or {}))
        if event:self.events.append(deepcopy(out))
        return out

    def process(self,r):
        q=self.rules;t=r['time']
        numbers=('time','received','left','target','btc','brti','p','up_bid','up_ask','down_bid','down_ask')
        if any(type(r.get(k)) not in (int,float) or not math.isfinite(r[k]) for k in numbers):
            return self.emit(None,r,['INVALID_NUMERIC'])
        if r.get('side') not in ('UP','DOWN') or r.get('p',0)<.5 or r['p']>1 or r['target']<=0:
            return self.emit(None,r,['INVALID_DIRECTION'])
        if self.last and (t<=self.last['time'] or r['received']<self.last['received']):
            return self.emit(None,r,['DUPLICATE_OR_OUT_OF_ORDER'])
        identity=r.get('publication_id')
        if not identity or identity==self.last_identity:return self.emit(None,r,['PUBLICATION_ID_REQUIRED_OR_REUSED'])
        if r['received']<t or r['received']-t>q.max_age or r['left']<=0:
            return self.unavailable(r,'DELAYED_OR_EXPIRED')
        if self.contract!=r['contract']:
            if r['contract'] in self.seen_contracts or self.close and t+r['left']<=self.close:
                return self.emit(None,r,['OLDER_CONTRACT'])
            if self.origin and not self.terminal:
                self.closed.append(dict(origin=self.origin,exit=None,censor='ROLLOVER_WITHOUT_EXIT'))
            self.contract=r['contract'];self.seen_contracts.add(self.contract)
            self.close=t+r['left'];self.target=r['target'];self.history=[]
            self.origin=None;self.terminal=None;self.streaks={};self.guidance='PASS';self.reset_seen=False
        if r['target']!=self.target or abs(t+r['left']-self.close)>1:
            return self.unavailable(r,'CONTRACT_IDENTITY_CONFLICT')
        if (not r['healthy'] or not 0<=r['up_bid']<=r['up_ask']<=1 or not 0<=r['down_bid']<=r['down_ask']<=1
            or abs(r['up_bid']+r['down_ask']-1)>1e-7 or abs(r['down_bid']+r['up_ask']-1)>1e-7):
            return self.unavailable(r,'UNHEALTHY_OR_INVALID_BOOK')
        if self.last and (t-self.last['time']>q.max_gap or r.get('source_epoch')!=self.last.get('source_epoch')):
            self.history=[];self.streaks={};self.gap_seen=True
        self.last=deepcopy(r);self.last_identity=identity
        self.history.append(deepcopy(r));self.history=[z for z in self.history if z['time']>=t-q.lookback-q.max_gap]
        side=r['side'];x=features(self.history,r,side,q);fail=screen(r,x,side,q)
        # An outage or absent profile is NOT a reset. A real failed direction is.
        if self.terminal:
            held=features(self.history,r,self.origin['side'],q)
            changed=held is not None and (held['move_long']<=0 or min(held['gap'],held['brti_gap'])<=0)
            if self.streak('reset',changed,t,q.reset_seconds):self.reset_seen=True
        if self.origin and not self.terminal:
            return self.manage(r)
        if self.terminal and not self.reset_seen:
            self.guidance='EXIT';return self.emit(None,r,['WAITING_FOR_DISTINCT_DIRECTIONAL_RESET'])
        if self.buy_side!=side:self.streaks.pop('entry',None);self.buy_side=side
        confirmed=self.streak('entry',not fail,t,q.confirm_seconds)
        econ=economics(r,side,self.profile,q)
        if confirmed and (self.proposal_mode or econ['ready']):
            self.origin=dict(id=digest([POLICY,self.contract,identity,side]),contract=self.contract,
                side=side,time=t,decision_available=r['received'],ask=r[side.lower()+'_ask'],
                bid=r[side.lower()+'_bid'],left=r['left'],publication_id=identity,features=x,economics=econ,
                evidence_class=r.get('evidence_class'),complete=True,structure_btc=x['structure_btc'],
                structure_brti=x['structure_brti'],best_bid=r[side.lower()+'_bid'])
            self.terminal=None;self.guidance='HOLD';self.reset_seen=False;self.streaks={};self.gap_seen=False
            return self.emit('BUY',r,['STRUCTURAL_PROPOSAL' if self.proposal_mode else 'EMPIRICAL_OPPORTUNITY_SUPPORTED'],{'economics':econ})
        self.guidance='PASS' if not self.terminal else 'EXIT'
        return self.emit(None,r,fail or (['CONFIRMING_NEW_SETUP'] if not confirmed else econ['reasons']),{'economics':econ})

    def unavailable(self,r,reason):
        self.history=[];self.streaks={};self.gap_seen=True
        if self.origin and not self.terminal:
            self.origin['complete']=False
            changed=self.guidance!='WATCH';self.guidance='WATCH'
            return self.emit('WATCH' if changed else None,r,['DATA_UNAVAILABLE',reason],{'executable_exit_bid':None})
        return self.emit(None,r,[reason])

    def manage(self,r):
        q=self.rules;t=r['time'];side=self.origin['side'];x=features(self.history,r,side,q)
        if not x:
            self.origin['complete']=False;changed=self.guidance!='WATCH';self.guidance='WATCH'
            return self.emit('WATCH' if changed else None,r,['MOMENTUM_HISTORY_UNAVAILABLE'])
        sign=1 if side=='UP' else -1
        weak=dict(MOMENTUM_WEAKENING=x['move_short']<=0 or x['brti_short']<=0,
            BTC_BRTI_CONFIRMATION_LOST=min(x['gap'],x['brti_gap'])<=0,
            MULTIMINUTE_REVERSAL=x['move_long']<=0 or x['brti_long']<=0,
            BID_DETERIORATION=x['quote_short']<=-max(x['spread'],.01),
            MODEL_OPPOSITION=x['p']<.5)
        # Settlement samples are supplied only by native causal binding. No interpolation.
        settlement=r.get('settlement')
        settled_adverse=bool(0<r['left']<=60 and settlement and settlement.get('verified_causal') is True and
            settlement.get('contract')==r['contract'] and settlement.get('asof')==r['time'] and
            settlement.get('hurdle') is not None and sign*(r['brti']-settlement['hurdle'])<=0)
        weak['SETTLEMENT_PATH_CONTRADICTION']=settled_adverse
        warning=sum(v for k,v in weak.items() if k!='MODEL_OPPOSITION')>=2
        # Risk exits do not require profit, a prior profit target or a FINAL confidence update.
        breakdown=(max(x['gap'],x['brti_gap'])<0 and max(x['move_short'],x['brti_short'])<0)
        reversal=(max(x['move_long'],x['brti_long'])<0 and max(x['move_short'],x['brti_short'])<0 and weak['BID_DETERIORATION'])
        settlement_break=settled_adverse and weak['MOMENTUM_WEAKENING'] and weak['BID_DETERIORATION']
        structure_break=(sign*r['btc']<self.origin['structure_btc']-q.impulse_range*x['range'] and
            sign*r['brti']<self.origin['structure_brti']-q.impulse_range*x['range'] and
            max(x['move_short'],x['brti_short'])<0 and weak['BID_DETERIORATION'])
        weak['CONFIRMED_STRUCTURE_BREAK']=structure_break
        if (r[side.lower()+'_bid']>self.origin['best_bid'] and min(x['move_short'],x['brti_short'])>0):
            self.origin['best_bid']=r[side.lower()+'_bid']
            self.origin['structure_btc']=max(self.origin['structure_btc'],x['structure_btc'])
            self.origin['structure_brti']=max(self.origin['structure_brti'],x['structure_brti'])
        exit_ready=self.streak('exit',breakdown or reversal or settlement_break or structure_break,t,q.exit_seconds)
        # Shrinking remaining execution room warns; never force a duration exit.
        reasons=[k for k,v in weak.items() if v]
        if r['left']<=q.manual_seconds+q.max_gap:reasons.append('EXECUTION_ROOM_LOW')
        if exit_ready:
            reason='CAUSAL_STRUCTURE_BREAKDOWN' if structure_break else 'SETTLEMENT_BREAKDOWN' if settlement_break else 'TARGET_THESIS_BREAKDOWN' if breakdown else 'CORROBORATED_TREND_REVERSAL'
            bid=r[side.lower()+'_bid']
            self.terminal=dict(time=t,available=r['received'],bid=bid,reason=reason,publication_id=r['publication_id'],
                origin_id=self.origin['id'],net_quote_scenario=bid-self.origin['ask']-fee(self.origin['ask'])-fee(bid)-max(x['spread'],q.reserve),
                realized_profit=None,complete=self.origin['complete'])
            self.closed.append(dict(origin=deepcopy(self.origin),exit=deepcopy(self.terminal),censor=None))
            self.guidance='EXIT';self.streaks={}
            return self.emit('EXIT',r,[reason]+reasons,{'executable_exit_bid':bid,'terminal':deepcopy(self.terminal)})
        warn_ready=self.streak('watch',warning,t,q.watch_seconds)
        recovering=self.streak('recovery',not warning and not weak['MOMENTUM_WEAKENING'] and not weak['BTC_BRTI_CONFIRMATION_LOST'] and not weak['MULTIMINUTE_REVERSAL'],t,q.recovery_seconds)
        previous=self.guidance
        if warn_ready or 'EXECUTION_ROOM_LOW' in reasons:self.guidance='WATCH'
        elif self.guidance!='WATCH' or recovering:self.guidance='HOLD'
        return self.emit(self.guidance if self.guidance!=previous else None,r,reasons if self.guidance=='WATCH' else ['DIRECTION_REMAINS_SUPPORTED'],{'management_evidence':x})

    def finish(self):
        episodes=deepcopy(self.closed)
        if self.origin and not self.terminal:episodes.append(dict(origin=deepcopy(self.origin),exit=None,censor='NO_OBSERVED_CONDITION_EXIT'))
        return episodes
