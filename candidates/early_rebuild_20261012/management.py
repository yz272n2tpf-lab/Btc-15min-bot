"""Immutable entry ownership around unchanged condition management. No entry generation."""
from copy import deepcopy
from dataclasses import dataclass, asdict
from candidates.early_value_20261011.engine import CoreEngine
from .assessment import SAFETY

@dataclass(frozen=True)
class Origin:
    id: str
    setup_id: str
    ticket_id: str | None
    contract: str
    side: str
    kind: str
    entry_time: float
    observed_ask: float
    quantity: float
    evidence_id: str

class Management:
    def __init__(self, origin, history, r, x, rules):
        self.origin=origin
        self.core=CoreEngine(rules=rules)
        self.core.contract=r['contract'];self.core.close=r['time']+r['left'];self.core.target=r['target']
        self.core.history=deepcopy(history);self.core.last=deepcopy(r);self.core.guidance='HOLD'
        self.core.origin=dict(id=origin.id,contract=origin.contract,side=origin.side,time=origin.entry_time,
             decision_available=r['received'],ask=origin.observed_ask,bid=r[origin.side.lower()+'_bid'],
             left=r['left'],publication_id=r['publication_id'],features=deepcopy(x),complete=True,
             structure_btc=x['structure_btc'],structure_brti=x['structure_brti'],best_bid=r[origin.side.lower()+'_bid'])
        self.saw_strong_final=False;self.protect_latched=False;self.final_status='UNAVAILABLE'
        self.final_layer(r)
        self.last_reasons=['EXPLICIT_'+origin.kind+'_ORIGIN'];self.closed=False;self.close_event=None

    def final_layer(self,r):
        # Native FINAL gates themselves are never recreated or altered.
        f=r.get('native_frame')
        if f is None: self.final_status='UNAVAILABLE';return
        try:
            from btc15_v2_product.directional import qualify,protected_frame
            qualify(f,r['received'])
            if f['contract']!=r['contract'] or f['target']!=r['target'] or f['feature_cutoff']!=r['time']:
                raise ValueError('FINAL_ROW_BINDING_CONFLICT')
            final=protected_frame(f,r['received'])[0]['final']
            strong=final['ready'] and final['side']==self.origin.side
            opposing=final['ready'] and final['side']!=self.origin.side
            if opposing or (self.saw_strong_final and not strong): self.protect_latched=True
            self.saw_strong_final |= strong
            self.final_status='AVAILABLE'
        except (KeyError,ValueError,TypeError): self.final_status='UNAVAILABLE'

    def update(self,history,r,unavailable=None):
        if self.closed: return self.view()
        if r.get('contract')!=self.origin.contract:
            return self.unavailable('CONTRACT_ROLLOVER_NO_NEW_CONTRACT_PRICE')
        if unavailable: return self.unavailable(unavailable)
        self.final_layer(r)
        if self.core.terminal: return self.view()
        self.core.history=deepcopy(history);self.core.last=deepcopy(r)
        out=self.core.manage(r) # byte-identical imported baseline method
        self.last_reasons=out['reasons']
        return self.view()

    def unavailable(self,reason):
        self.core.history=[];self.core.streaks={};self.core.origin['complete']=False
        if not self.core.terminal:self.core.guidance='WATCH'
        self.last_reasons=['DATA_UNAVAILABLE',reason]
        return self.view()

    def view(self):
        internal=self.core.guidance
        if self.protect_latched and internal!='EXIT':internal='PROTECT'
        public='EXIT' if internal=='EXIT' else 'WATCH'
        label='existing entry weakening' if internal in ('WATCH','PROTECT') else 'existing entry stable'
        if self.origin.kind=='SIMULATED': label=label.replace('existing entry','simulation')
        return dict(**SAFETY,panel='EARLY MANAGEMENT',origin=asdict(self.origin),internal_state=internal,
                    display=public,label=label if public=='WATCH' else 'condition exit',
                    reasons=list(self.last_reasons),final_protection_status=self.final_status,
                    final_protect_latched=self.protect_latched,terminal=deepcopy(self.core.terminal),
                    closure_confirmed=self.closed,realized_profit=None,manual_fill=None,
                    confirmed_entry_event=self.origin.evidence_id if self.origin.kind=='MANUAL_CONFIRMED' else None)


class ThesisRecoveryManagement(Management):
    """EARLY-only recovery compatibility. Baseline exits and FINAL run first.

    The baseline was written for favorable-gap entries. Requiring that same gap
    to recover from a warning conflicts with an immutable pre-crossing origin.
    This changes internal recovery only; the public action remains WATCH.
    """
    policy='EARLY_PRE_CROSSING_RECOVERY_V1'

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.pre_crossing_origin=self.core.origin['features']['context']=='PRE_CROSSING'
        self.approach_recovery_since=None

    def unavailable(self,reason):
        self.approach_recovery_since=None
        return super().unavailable(reason)

    def update(self,history,r,unavailable=None):
        out=super().update(history,r,unavailable)
        if self.closed or unavailable or self.core.terminal or r.get('contract')!=self.origin.contract:
            self.approach_recovery_since=None;return out
        from .assessment import features,recognition_reasons,validate_row
        x=features(history,r,self.origin.side,self.core.rules) if history else None
        eligible=bool(self.pre_crossing_origin and not self.protect_latched and not validate_row(r) and x and
            not recognition_reasons(x,self.core.rules) and min(x['move_short'],x['brti_short'])>0 and
            (not x['context120_available'] or min(x['move_long'],x['brti_long'])>0) and
            x['quote_short']>-max(x['spread'],.01) and
            not {'EXECUTION_ROOM_LOW','SETTLEMENT_PATH_CONTRADICTION','CONFIRMED_STRUCTURE_BREAK',
                 'DATA_UNAVAILABLE','MOMENTUM_HISTORY_UNAVAILABLE'}.intersection(self.last_reasons))
        if not eligible:
            self.approach_recovery_since=None;return out
        if self.approach_recovery_since is None:self.approach_recovery_since=r['time']
        if self.core.guidance=='WATCH' and r['time']-self.approach_recovery_since>=self.core.rules.recovery_seconds:
            self.core.guidance='HOLD'
            self.last_reasons=['PRE_CROSSING_APPROACH_RECOVERED_TARGET_NOT_REQUIRED']
            self.core.emit('HOLD',r,self.last_reasons,{'management_evidence':x,'recovery_policy':self.policy})
        return self.view()
