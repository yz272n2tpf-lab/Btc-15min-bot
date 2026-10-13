"""Native value entry using causal model features and market corroboration; no orders.

This is an explicit conservative risk policy, not a promoted research result or
an assertion of calibrated live accuracy. It does not alter FINAL or Tier-1.
"""
from copy import deepcopy
import math
import time

POLICY = 'EARLY_CAUSAL_VALUE_V2'
SOURCE = 'NATIVE_EARLY_VALUE_V2'
ARTIFACT = '1bf10e755fc81584bab3c3682b16103353f84582c27bb003664de883e7e7c816'
WEIGHTS = '95fc4e893c9032f29b9732d03c4a2e0cd62755ba93b36106a1d0c8c094520ba6'
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
    """First complete supported frame can qualify; no observation-count gate.

    Probability is a calibrated-model estimate, not established live accuracy.
    Existing model identity, causal features and independent current market
    corroboration are required in addition to cost-adjusted model value.
    """
    from .opportunities import economics, fee_scenario
    from .early_management import features
    e, final = raw['early'], raw['final']
    side, p = e['side'], e['fair']
    sign = 1 if side == 'UP' else -1
    left = raw['timer']['seconds_left']
    schedule = f.get('fee_schedule') or {}
    multiplier = schedule['multiplier'] if fee_valid(f) else 1.
    econ = economics(p,raw['market'][side.lower()+'_bid'],e['ask'],multiplier)
    x = features(f)
    # A sale at model fair is only an economic scenario, never a price forecast.
    sale_fee = fee_scenario(p,multiplier)
    margin = econ.get('stress_net_model_ev_scenario',-1)-sale_fee
    econ.update(exit_fee_at_model_fair_scenario=sale_fee,
        round_trip_stress_value_margin=margin,
        round_trip_basis='Stress entry cost plus sale fee at model fair; fair is not a predicted future BID',
        series_fee_verified=fee_valid(f))
    # Only the observed source/delivery delay is known. No assumed manual fill
    # latency, fabricated depth, or fixed entry-time window is introduced.
    delay=max(f['captured_ts']-f['btc_source'],f['captured_ts']-f['brti']['cf_ts'],
              f['captured_ts']-f['quote']['exchange_ts_ms']/1000)
    gates = dict(
        verified_model=f.get('artifact')==ARTIFACT and f.get('weights')==WEIGHTS,
        causal_model_features=x is not None,
        btc_target_support=sign*(f['btc_price']-f['target'])>0,
        brti_target_support=sign*(f['brti']['value']-f['target'])>0,
        momentum_and_trend_support=bool(x and sign*x['move1']>0 and sign*x['move5']>0),
        final_not_opposed=final['side']==side,
        current_series_fees=fee_valid(f),
        two_sided_execution=econ.get('valid_book',False) and raw['market'][side.lower()+'_bid']>0,
        observed_execution_runway=left>delay,
        positive_settlement_upside=econ.get('win_profit_scenario',-1)>0,
        positive_round_trip_value=margin>0)
    labels=dict(verified_model='Verified frozen model and calibration weights are unavailable',
        causal_model_features='The exact causal momentum/volatility feature snapshot used by this model decision is unavailable',
        btc_target_support='BTC must support the proposed side of the exact target',
        brti_target_support='BRTI must support the proposed side of the exact target',
        momentum_and_trend_support='Existing one-minute momentum and five-minute trend must both support this side; conflicting movement remains WATCH',
        final_not_opposed='Continuously available FINAL model direction opposes this setup',
        current_series_fees='A current supported Kalshi series fee schedule is required',
        two_sided_execution='A positive same-side BID and valid ASK are needed to assess a price-movement entry',
        observed_execution_runway='Remaining time must exceed the already observed source/delivery delay; manual execution still requires checking time and depth',
        positive_settlement_upside='Entry plus fees leaves no positive settlement reward',
        positive_round_trip_value='Model value must exceed entry fees, one observed spread of entry stress and a sale-fee scenario')
    missing=[labels[k] for k,v in gates.items() if not v]
    risk=dict(range5=x.get('range5') if x else None,vol5=x.get('vol5') if x else None,
        move1=x.get('move1') if x else None,move5=x.get('move5') if x else None,
        target_distance_over_range=f['fair']['dist_over_range5'],
        model_flip_probability=1-p,seconds_left=left,observed_source_delay=delay,
        target_inside_recent_range=bool(x and abs(f['btc_price']-f['target'])<x['range5']))
    return dict(policy=POLICY,side=side,ready=all(gates.values()),conditions=gates,
        missing=missing,economics=econ,risk=risk,
        reason=('Causal model, BTC/BRTI target support, aligned momentum/trend and cost-adjusted value qualify; probability is an estimate'
                if not missing else '; '.join(missing)),
        fee_schedule=deepcopy(schedule),
        reliability='VERIFIED_EXISTING_CALIBRATED_MODEL_AND_MARKET_CORROBORATION; CURRENT_POLICY_ACCURACY_UNESTABLISHED',
        price_ceiling=None,confidence_floor=None,entry_window=None,confirmation_count=None,
        signal_only=True,orders=False)


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
