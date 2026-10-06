"""Sept 14 generalized qualification + Sept 15 serial protected lifecycle.

The qualification thresholds are frozen at BTC30 >= $15 and >=120s left.
The existing current and historical provenance checks remain mandatory.
"""
import math
from btc15_v81_qualified_inputs_v1 import require_qualified


def proposal_for(row, side, history):
    result=dict(ok=False,route='GENERALIZED',history=history,features=None,reason='BTC30_HISTORY_REFRESHING')
    try:
        p=require_qualified(row,row['ts']);old=history['30'];hp=old['input_provenance']
        if (hp['ticker']!=p['ticker'] or hp['target']!=p['target']
                or not row['ts']-36 <= old['observed_ts'] <= row['ts']-30):
            raise ValueError('BTC30_HISTORY_UNQUALIFIED')
        require_qualified(dict(hp['quote'],ticker=hp['ticker'],target=hp['target'],
            brti=hp['brti']['value'],input_provenance=hp),old['observed_ts'])
        if side not in ('UP','DOWN') or not all(type(x) in (int,float) and math.isfinite(x) and x>0 for x in (row['btc'],old['btc'])):
            raise ValueError('BTC30_VALUE_INVALID')
        btc30=(row['btc']-old['btc'])*(1 if side=='UP' else -1)
        result['features']={'btc30':btc30}
        left=p['close_ts']-row['ts']
        result.update(ok=left>=120 and btc30>=15,
            reason='QUALIFIED' if left>=120 and btc30>=15 else 'NEW_ENTRY_REQUIRES_120S' if left<120 else 'BTC30_BELOW_15')
    except (ValueError,KeyError,TypeError):
        pass
    return result


class Lifecycle:
    """Only +5c arm / 4c peak giveback can create executable EXIT."""
    def __init__(self,policy,ticker,side,entry,entry_ts,observed_ts,close_ts):
        if side not in ('UP','DOWN') or not 0<=entry<=1 or not entry_ts<=observed_ts<close_ts:
            raise ValueError('INVALID_SCALP_ORIGIN')
        self.policy=policy;self.ticker=ticker;self.side=side;self.entry=entry
        self.started=entry_ts;self.observed=observed_ts;self.close=close_ts
        self.deadline=min(entry_ts+policy.horizon,close_ts)
        self.last=None;self.peak=None;self.armed=False;self.terminal=None

    def update(self,row):
        if self.terminal:return self.terminal
        now=row['observed_ts'];bid=row.get(self.side.lower()+'_bid')
        if (row['ticker']!=self.ticker or row.get('quote_validated_at_observation') is not True
                or not self.started<now<self.close or self.last is not None and now<=self.last
                or not 0<=now-row.get('brti_source_ts',-math.inf)<=5
                or type(bid) not in (int,float) or not math.isfinite(bid) or not 0<=bid<=1):
            return dict(status='WAIT',signal_only=True,orders=False)
        self.last=now;gain=bid-self.entry
        self.peak=gain if self.peak is None else max(self.peak,gain)
        self.armed=self.armed or gain+1e-12>=self.policy.arm
        status=('EXIT' if self.armed and self.peak-gain+1e-12>=self.policy.giveback else
            'ENDED_UNARMED' if now>=self.deadline and not self.armed else
            'PROTECT' if self.armed else 'HOLD')
        result=dict(status=status,actionable_exit=status=='EXIT',signal_only=True,orders=False)
        if status in ('EXIT','ENDED_UNARMED'):self.terminal=result
        return result
