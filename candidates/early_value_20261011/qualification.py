"""Unified value selection; historical model probability is not resale value."""
from dataclasses import replace
from candidates.early_condition_20261011.engine import features as prior_features, fee


def features(history, r, side, rules):
    short = prior_features(history, r, side, replace(rules, lookback=rules.short))
    if short is None:
        return None
    long = prior_features(history, r, side, rules)
    x = dict(long or short)
    x.update(context120_available=long is not None, short_range=short['range'],
             short_efficiency=short['efficiency'])
    return x


def screen(r, x, side, rules):
    ask, bid = r[side.lower()+'_ask'], r[side.lower()+'_bid']
    p = r['p'] if r['side'] == side else 1-r['p']
    if rules.baseline_tier1:
        # Exact archived predicates transferred to the available live-model p.
        # Original RF predictions and one-minute timing are NOT reconstructed.
        checks = dict(TIER1_PRICE=0 < ask <= rules.max_ask,
            TIER1_CONFIDENCE=p >= .75, TIER1_MODEL_EDGE=p-ask >= .08,
            TIER1_WINDOW=120 <= r['left'] <= 600,
            TIER1_ABSOLUTE_GAP=abs(r['btc']-r['target']) >= 25,
            PROTECTION_HISTORY=x is not None, POSITIVE_BID=bid > 0)
        return [k for k,v in checks.items() if not v]
    if not x:
        return ['CAUSAL_30S_HISTORY_UNAVAILABLE']
    exceptional = rules.allow_exception and rules.max_ask < ask <= rules.exception_max
    checks = dict(
        VALUE_PRICE=0 < bid <= ask and (ask <= rules.max_ask or exceptional),
        SPREAD=0 <= x['spread'] <= rules.max_spread+1e-9,
        ENTRY_RUNWAY=r['left']-(r['received']-r['time']) > rules.min_left+rules.manual_seconds,
        MODEL_DIRECTION=p >= rules.min_confidence,
        CURRENT_BTC_BRTI_SUPPORT=min(x['gap'],x['brti_gap']) >= rules.gap_range*x['short_range'],
        FRESH_DIRECTIONAL_IMPULSE=min(x['move_short'],x['brti_short']) >= rules.impulse_range*x['short_range'],
        SHORT_PATH_EFFICIENCY=x['short_efficiency'] >= rules.efficiency,
        NO_MATERIAL_QUOTE_REVERSAL=x['quote_short'] >= -max(x['spread'],.01)-1e-9,
        MODEL_DISAGREEMENT_MARGIN=p-ask-fee(ask)-fee(.5)-max(x['spread'],rules.reserve) >= .08,
        # Merely capacity, explicitly never a forecast or economic proof.
        FINITE_RESALE_CAPACITY=1-ask-fee(ask)-fee(.5)-max(x['spread'],rules.reserve) > 0)
    if exceptional:
        checks['EXCEPTIONAL_DIRECTION'] = (p >= .90 and x['context120_available'] and
            min(x['move_long'],x['brti_long']) > 0 and x['persistence'] >= rules.persistence)
    return [k for k,v in checks.items() if not v]


def economics(r, side, profile, rules):
    ask, bid = r[side.lower()+'_ask'], r[side.lower()+'_bid']
    reserve = max(ask-bid,rules.reserve)
    cost = fee(ask)+fee(.5)+reserve
    exceptional = ask > .55
    cell = (profile or {}).get('support',{}).get(side,{})
    if exceptional:
        cell = cell.get('exception',{})
    lower = cell.get('gross_gain_lower')
    reasons = []
    if not cell.get('supported'):
        reasons.append('NO_INDEPENDENT_AFTER_COST_SUPPORT')
    required = cost*(2 if exceptional else 1)
    if lower is None or lower <= required:
        reasons.append('EXCEPTIONAL_NET_EVIDENCE_REQUIRED' if exceptional else 'NET_LOWER_BOUND_INSUFFICIENT')
    if cell.get('min_left') is None or not cell['min_left'] <= r['left'] <= cell['max_left']:
        reasons.append('RUNWAY_OUTSIDE_EMPIRICAL_SUPPORT')
    if cell.get('min_ask') is None or not cell['min_ask'] <= ask <= cell['max_ask']:
        reasons.append('PRICE_OUTSIDE_EMPIRICAL_SUPPORT')
    return dict(ready=not reasons,reasons=reasons,ask=ask,bid=bid,spread=ask-bid,
        entry_fee_stress=fee(ask),exit_fee_upper_stress=fee(.5),execution_reserve=reserve,
        required_gross_gain=required,condition_exit_gain_lower=lower,
        net_mean_lower=None if lower is None else lower-cost,
        payout_capacity=1-ask-cost,entry_risk=ask+fee(ask),
        exception=exceptional,realized_profit=None,
        basis='Observed condition-exit cohort; payout capacity/model edge are NOT predicted resale profit')
