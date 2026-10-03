"""Offline V8.1 exit lifecycle candidates. No orders or live advice integration.

Policies are predeclared hypotheses drawn from existing research, not selected
production rules. Preserve entry direction/ask and evaluate only qualified
observations. Never turn a missing exit quote into a filled trade.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Policy:
    name: str
    arm: float | None = None
    giveback: float | None = None
    stop: float | None = None
    target: float | None = None
    horizon: float = 180.

    def __post_init__(self):
        if (self.arm is None) != (self.giveback is None):raise ValueError('Incomplete protection rule')
        for name in ('arm','giveback','stop','target','horizon'):
            value=getattr(self,name)
            if value is not None and (not math.isfinite(value) or value<=0):raise ValueError('Invalid policy')


POLICIES=(Policy('V81_BASELINE_180S'),Policy('V81_RESEARCH_PROTECT_5_2',.05,.02),
          Policy('V81_RESEARCH_RUNNER_10_4',.10,.04),
          Policy('V81_RESEARCH_CORE_TARGET8_STOP10',stop=.10,target=.08))


class Lifecycle:
    def __init__(self, policy, ticker, side, entry, entry_ts, observed_ts, close_ts):
        if side not in ('UP','DOWN') or not ticker.startswith('KXBTC15M-'):
            raise ValueError('Invalid entry identity')
        if not all(math.isfinite(x) for x in (entry,entry_ts,observed_ts,close_ts)):
            raise ValueError('Nonfinite entry')
        if not .30 <= entry <= .45 or not 0 <= observed_ts-entry_ts <= 3.5:
            raise ValueError('Entry was not freshly observed in the existing V8.1 band')
        if not entry_ts < close_ts:raise ValueError('Closed entry')
        self.policy=policy;self.ticker=ticker;self.side=side;self.entry=entry
        self.started=entry_ts;self.observed=observed_ts;self.deadline=min(entry_ts+policy.horizon,close_ts)
        self.close=close_ts;self.last=None;self.peak=None;self.trough=None;self.armed=False
        self.terminal=None;self.samples=0;self.waits=0;self.max_gap=0.

    def update(self,row):
        if self.terminal is not None:return self.terminal
        now=float(row['observed_ts'])
        if not math.isfinite(now):raise ValueError('Invalid observation clock')
        if now<self.observed or (self.last is not None and now<=self.last):return {'status':'OUT_OF_ORDER'}
        if row['ticker']!=self.ticker:
            if now>=self.deadline:return self.finish('EXPIRED_WITHOUT_SAME_CONTRACT_QUOTE',now,None)
            return {'status':'WRONG_CONTRACT_WAIT'}
        brti_source=float(row.get('brti_source_ts',math.nan))
        bid=row.get(self.side.lower()+'_bid')
        valid=(row.get('quote_validated_at_observation') is True and
               math.isfinite(brti_source) and 0<=now-brti_source<=5 and
               isinstance(bid,(int,float)) and math.isfinite(bid) and 0<=bid<=1 and now<self.close)
        if now>=self.deadline:
            # No retroactive fill at a missing horizon quote; retain actual delay.
            return self.finish('HORIZON',now,bid-self.entry if valid and now==self.deadline else None)
        if not valid:
            self.waits+=1
            return {'status':'WAIT_QUALIFICATION','orders':False}
        self.max_gap=max(self.max_gap,now-(self.last if self.last is not None else self.observed))
        self.last=now;self.samples+=1;gain=bid-self.entry
        self.peak=gain if self.peak is None else max(self.peak,gain)
        self.trough=gain if self.trough is None else min(self.trough,gain)
        p=self.policy
        if p.arm is not None and gain+1e-12>=p.arm:self.armed=True
        if p.stop is not None and gain<=-p.stop+1e-12:return self.finish('STOP',now,gain)
        if p.target is not None and gain+1e-12>=p.target:return self.finish('TARGET',now,gain)
        if self.armed and self.peak-gain+1e-12>=p.giveback:return self.finish('PROTECT',now,gain)
        return {'status':'ARMED' if self.armed else 'WATCH','orders':False}

    def finish(self,status,now,gain):
        self.terminal=dict(status=status,policy=self.policy.name,ticker=self.ticker,side=self.side,
            entry_ask=self.entry,entry_ts=self.started,entry_first_observed_ts=self.observed,
            exit_observed_ts=now,exit_bid_minus_entry_ask=gain,horizon_delay_seconds=max(0.,now-self.deadline),
            observed_mfe=self.peak,observed_mae=self.trough,qualified_samples=self.samples,
            unqualified_observations=self.waits,max_observed_gap_seconds=self.max_gap,
            complete_path=False,realized_profit=False,actual_exit_advice_published=False,orders=False)
        return self.terminal
