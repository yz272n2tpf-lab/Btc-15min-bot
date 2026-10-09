"""Native value entry using existing strong directional safeguards; no orders.

This is an explicit conservative risk policy, not a promoted research result or
an assertion of calibrated live accuracy. It does not alter FINAL or Tier-1.
"""
from copy import deepcopy
import math
import time

POLICY = 'EARLY_SUPPORTED_VALUE_V1'
SOURCE = 'NATIVE_EARLY_VALUE_V1'
ARTIFACT = '1bf10e755fc81584bab3c3682b16103353f84582c27bb003664de883e7e7c816'
WEIGHTS = '95fc4e893c9032f29b9732d03c4a2e0cd62755ba93b36106a1d0c8c094520ba6'
# The existing EARLY 8-point edge requirement is now applied AFTER costs and
# spread stress. It is a risk reserve, not an estimated calibration error.
EDGE_RESERVE = .08
FEE_MAX_AGE = 120


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


class FeeCache:
    """One GET/minute on the existing metadata worker; never the decision path."""
    def __init__(self, get, clock=time.time):
        self.get, self.clock, self.next_read, self.value = get, clock, 0, None

    def refresh(self):
        now = self.clock()
        if now < self.next_read:
            return
        self.next_read = now + 60
        self.value = None
        try:
            s = self.get('/trade-api/v2/series/KXBTC15M')['series']
            if (s.get('ticker') != 'KXBTC15M' or s.get('fee_type') not in
                    ('quadratic', 'quadratic_with_maker_fees') or
                    not finite(s.get('fee_multiplier')) or s['fee_multiplier'] < 0):
                return
            self.value = dict(series='KXBTC15M',fee_type=s['fee_type'],
                multiplier=s['fee_multiplier'],observed_ts=self.clock(),
                source_updated_ts=s.get('last_updated_ts'),
                source='/trade-api/v2/series/KXBTC15M',
                basis='Published series taker schedule; one contract; verify any event/account override manually')
        except Exception:
            # Missing fees block this new route, never FINAL or existing origins.
            self.value = None


def fee_valid(f):
    s = f.get('fee_schedule') or {}
    at, cut = s.get('observed_ts'), f.get('feature_cutoff')
    return (s.get('series') == 'KXBTC15M' and
        s.get('fee_type') in ('quadratic', 'quadratic_with_maker_fees') and
        finite(s.get('multiplier')) and s['multiplier'] >= 0 and
        finite(at) and finite(cut) and 0 <= cut-at <= FEE_MAX_AGE)


def assess(raw, f, previous=None):
    """Pure native decision. Prior is a complete accepted native frame only."""
    from .opportunities import economics
    e, final, fair = raw['early'], raw['final'], f['fair']
    side, p = e['side'], e['fair']
    sign = 1 if side == 'UP' else -1
    left = raw['timer']['seconds_left']
    schedule = f.get('fee_schedule') or {}
    econ = economics(p,raw['market'][side.lower()+'_bid'],e['ask'],
                     schedule['multiplier'] if fee_valid(f) else 1.)
    gates = dict(
        verified_model=f.get('artifact')==ARTIFACT and f.get('weights')==WEIGHTS,
        fair_ge90=p>=.90,
        remaining_2_to8=120<=left<=480,
        target_gap_support=sign*(f['btc_price']-f['target']) >= (75 if left>360 else 50),
        brti_support=sign*(f['brti']['value']-f['target'])>11,
        volatility_cushion=fair['dist_over_range5']>=1,
        final_not_opposed=not final['ready'] or final['side']==side,
        current_series_fees=fee_valid(f),
        positive_settlement_upside=econ.get('win_profit_scenario',-1)>0,
        stress_edge_reserve=econ.get('stress_net_model_ev_scenario',-1)>=EDGE_RESERVE-1e-12)
    static = dict(gates)
    prior = previous or {}
    pf, pr = prior.get('frame') or {}, prior.get('assessment') or {}
    q, pq = f['quote'], pf.get('quote') or {}
    pb = pf.get('brti') or {}
    continuous = (pf.get('contract')==f['contract'] and pf.get('target')==f['target'] and
        pf.get('native_epoch')==f['native_epoch'] and
        0 < f['captured_ts']-pf.get('captured_ts',0) <= 15 and
        pf.get('native_sequence',-1)<f['native_sequence'])
    progressed = bool(continuous and q['epoch']==pq.get('epoch') and q['sid']==pq.get('sid') and
        q['market_id']==pq.get('market_id') and q['seq']>pq.get('seq',-1) and
        q['exchange_ts_ms']>pq.get('exchange_ts_ms',0) and
        f['btc_source']>pf.get('btc_source',0) and
        f['brti']['delivery']['owner_epoch']==(pb.get('delivery') or {}).get('owner_epoch') and
        f['brti']['cf_ts']>pb.get('cf_ts',0))
    prior_p=(pf.get('fair') or {}).get(side.lower()+'_fair')
    gates.update(
        two_fresh_supported_observations=bool(progressed and pr.get('side')==side and pr.get('static_ready')),
        btc_momentum_support=bool(continuous and sign*(f['btc_price']-pf['btc_price'])>0),
        brti_not_reversing=bool(continuous and sign*(f['brti']['value']-pb['value'])>=0),
        probability_not_weakening=bool(continuous and finite(prior_p) and p>=prior_p-1e-12))
    labels=dict(verified_model='The verified frozen model and calibration weights are required',
        fair_ge90='Model probability must reach the existing 90% strong-direction floor',
        remaining_2_to8='Supported value-entry runway is 2–8 minutes remaining',
        target_gap_support='BTC must support this side by $75 above 6 minutes, otherwise $50',
        brti_support='BRTI must support this side by more than $11',
        volatility_cushion='Target distance must cover at least the existing five-minute range measure',
        final_not_opposed='A qualified opposing FINAL blocks this value entry',
        current_series_fees='A current supported Kalshi series fee schedule is required',
        positive_settlement_upside='Entry plus fees leaves no positive settlement reward',
        stress_edge_reserve='At least 8 points of model edge must remain after fees and one-spread execution stress',
        two_fresh_supported_observations='Two supported native observations within 15s need advancing BTC, BRTI and same-session books',
        btc_momentum_support='Observed BTC movement must support the proposed direction',
        brti_not_reversing='BRTI must not be reversing against the proposed direction',
        probability_not_weakening='Directional probability must not weaken between confirming observations')
    missing=[labels[k] for k,v in gates.items() if not v]
    return dict(policy=POLICY,side=side,ready=all(gates.values()),static_ready=all(static.values()),
        conditions=gates,static_conditions=static,missing=missing,economics=econ,
        reason=('Strong directional evidence, advancing source confirmation and cost-adjusted value qualify'
                if not missing else '; '.join(missing)),
        fee_schedule=deepcopy(schedule),edge_reserve=EDGE_RESERVE,
        reliability='VERIFIED_MODEL_PLUS_STRONG_DIRECTIONAL_GUARDS; EXPANDED_POLICY_WIN_RATE_NOT_ESTABLISHED',
        prior_native_key=[pf.get('native_epoch'),pf.get('native_sequence')] if continuous else None,
        price_ceiling=None,signal_only=True,orders=False)


def route(raw, qualified, assessment):
    """Separate Tier-1 and value policy; no historical-price veto is inherited."""
    raw, qualified = deepcopy(raw), deepcopy(qualified)
    raw['historical_early']=deepcopy(raw['early'])
    raw['early_value_qualification']=assessment
    if not raw['early']['ready']:
        raw['early'].update(source=SOURCE,policy=POLICY,ready=assessment['ready'],
            conditions=assessment['conditions'],qualification=assessment,reason=assessment['reason'])
        qualified['lanes']['early']['publication_eligible']=assessment['ready']
    return raw, qualified
