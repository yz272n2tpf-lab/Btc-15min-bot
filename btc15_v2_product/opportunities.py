"""Native, price-unbounded opportunity analysis; no orders or inferred fills.

Historical Tier-1 and the supported-value native origin policy are independent.
All prices/windows are evaluated on every qualified native frame. Missing
supported-entry evidence stays observational. No rejected study is promoted.
Costs are explicit scenarios, never an execution claim.
"""
import math
from decimal import Decimal, ROUND_CEILING

SCHEMA = 'BTC15_NATIVE_VALUE_ANALYSIS_V1'
FEE_SOURCE = 'https://kalshi.com/docs/kalshi-fee-schedule.pdf'


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def fee_scenario(price, multiplier=1.):
    # Conservative one-contract cent-rounded bound, covering the general
    # schedule's centicent rounding. M=1 is a scenario, not verified series data.
    p = Decimal(str(price))
    return float((Decimal(str(multiplier)) * Decimal('.07') * p * (1-p)).quantize(Decimal('.01'), rounding=ROUND_CEILING))


def economics(probability, bid, ask, multiplier=1.):
    valid = all(finite(v) for v in (probability,bid,ask)) and 0<=probability<=1 and 0<=bid<=ask<=1 and ask>0
    if not valid:
        return dict(valid_book=False, reason='A valid same-contract bid/ask is required')
    fee = fee_scenario(ask, multiplier)
    spread = ask-bid
    stress_price = min(1.,ask+spread)
    stress_cost = stress_price+fee_scenario(stress_price, multiplier)
    cost = ask+fee
    return dict(valid_book=True,bid=bid,ask=ask,model_probability=probability,
        gross_model_edge=probability-ask,entry_fee_scenario=fee,
        spread=spread,stress_entry_price=stress_price,
        entry_cost_scenario=cost,break_even_probability=cost,
        net_model_ev_scenario=probability-cost,
        stress_net_model_ev_scenario=probability-stress_cost,
        win_profit_scenario=1-cost,loss_scenario=cost,
        reward_risk_scenario=(1-cost)/cost,
        max_additional_cost_before_model_edge_zero=probability-cost,
        expected_profit=None,fill_guaranteed=False,
        execution_cost_basis='ASK plus fee; stress adds one observed spread, capped at $1; not a slippage forecast',
        fee_multiplier=multiplier,
        fee_basis='Quadratic taker scenario, one contract, rounded up to a cent; verify event/account overrides and execution size manually',
        settlement_fee_scenario=0,exit_fee_included=False)


def evaluate(raw, frame=None, previous=None, origin=None):
    early, final = raw['early'],raw['final']
    historical=raw.get('historical_early',early)
    qualification=raw.get('early_value_qualification')
    left=raw['timer']['seconds_left']
    frame=frame or {}
    fair=frame.get('fair') or {}
    up=fair.get('up_fair',early['fair'] if early['side']=='UP' else 1-early['fair'])
    probabilities={'UP':up,'DOWN':fair.get('down_fair',1-up)}
    same_previous=previous and previous.get('contract')==raw['contract']
    previous=previous if same_previous else None
    gap=frame.get('btc_price',math.nan)-frame.get('target',math.nan)
    brti=(frame.get('brti') or {}).get('value',math.nan)-frame.get('target',math.nan)
    elapsed=(frame.get('captured_ts',0)-previous.get('captured_ts',0)) if previous else None
    continuous=previous and finite(elapsed) and 0<elapsed<=15
    btc_move=frame['btc_price']-previous['btc_price'] if continuous and finite(previous.get('btc_price')) else None
    candidates=[]
    for side,p in probabilities.items():
        bid,ask=(raw['market'][side.lower()+'_'+kind] for kind in ('bid','ask'))
        from .early_entry import fee_valid
        econ=economics(p,bid,ask,(frame.get('fee_schedule') or {}).get('multiplier',1.) if fee_valid(frame) else 1.)
        econ['series_fee_verified']=fee_valid(frame)
        tier=side==historical['side'] and historical['ready']
        value=bool(qualification and qualification['ready'] and qualification['side']==side)
        supported=tier or value
        sign=1 if side=='UP' else -1
        conditions=dict(valid_book=econ['valid_book'],market_open=left>0,
            positive_cost_scenario=econ.get('net_model_ev_scenario',-1)>0,
            positive_spread_stress=econ.get('stress_net_model_ev_scenario',-1)>0)
        missing=[]
        if not conditions['valid_book']:missing.append('Valid same-contract executable quotes must become available')
        if not conditions['market_open']:missing.append('Contract must still be open')
        if not conditions['positive_cost_scenario']:missing.append('Model probability must exceed entry cost including fees')
        if not conditions['positive_spread_stress']:missing.append('Price or spread must improve enough to retain model edge under the execution stress scenario')
        if finite(gap) and sign*gap<=0:missing.append('BTC must move to the proposed side of the exact target')
        if finite(brti) and sign*brti<=0:missing.append('BRTI must support the proposed side of the exact target')
        if btc_move is not None and sign*btc_move<0:missing.append('Recent observed BTC movement opposes this side; momentum support must improve')
        opposed=final['ready'] and final['side']!=side
        if opposed:missing.append('Qualified FINAL currently contradicts this setup')
        if not supported:
            missing.extend(qualification['missing'] if qualification and qualification['side']==side else
                           ['Strong native value-entry evidence is missing; this setup remains unvalidated'])
        if value:missing=[]
        status='QUALIFIED' if supported else 'WATCH' if all(conditions.values()) else 'PASS'
        reason=('Historical Tier-1 rules qualify; model probability is not an established win rate'
                if tier else qualification['reason'] if value else
                'Positive model value; entry evidence remains unvalidated: '+('; '.join(qualification['missing'][:2]) if qualification and qualification['side']==side else 'strong native qualification is missing')
                if status=='WATCH' else (missing[0] if missing else 'No qualified directional value setup'))
        prior_ask=(previous.get('prices') or {}).get(side.lower()+'_ask') if continuous else None
        pullback=finite(prior_ask) and ask<prior_ask
        candidates.append(dict(side=side,status=status,ask=ask,bid=bid,fair=p,
            edge=p-ask if finite(ask) else None,economics=econ,reason=reason,conditions=conditions,
            improvements=missing,qualification_basis='HISTORICAL_TIER1' if tier else qualification['policy'] if value else 'OBSERVATIONAL_ONLY',
            value_qualification=qualification if qualification and qualification['side']==side else None,
            reliability='CURRENT_PRICE_CONDITIONED_CALIBRATION_NOT_ESTABLISHED',
            qualified_signal=supported,origin_authority=supported and not (origin and origin.get('contract')==raw['contract']),price_ceiling=None,
            final_relation='SUPPORTS' if final['side']==side else 'CONTRADICTS',
            target_gap=gap if finite(gap) else None,brti_gap=brti if finite(brti) else None,
            btc_move_since_previous_native=btc_move,native_interval_seconds=elapsed if continuous else None,
            probability_change=(p-(previous['probability_up'] if side=='UP' else 1-previous['probability_up'])) if previous else None,
            pullback_observed=pullback,pullback_ask_change=ask-prior_ask if pullback else None,
            secondary_state='WATCH' if pullback and status!='PASS' else 'PASS',
            secondary_reason=('Observed ask pullback; directional re-entry remains observational' if pullback else 'No causal ask pullback in this native interval; no directional re-entry signal')))
    rank={'QUALIFIED':2,'WATCH':1,'PASS':0}
    ranked=sorted(candidates,key=lambda c:(rank[c['status']],c['economics'].get('stress_net_model_ev_scenario',-math.inf),-c['ask']),reverse=True)
    best=ranked[0] if ranked[0]['status']!='PASS' else None
    preferred=next(c for c in candidates if c['side']==early['side'])
    selected=best or preferred
    opportunity=dict(status=selected['status'],side=selected['side'],ask=selected['ask'],fair=selected['fair'],edge=selected['edge'],
        reason=selected['reason'],conditions=selected['conditions'],improvements=selected['improvements'],
        economics=selected['economics'],price_zone='MODEL VALUE / COST SCENARIO' if selected['status']!='PASS' else 'NO SUPPORTED VALUE SETUP',
        target_ask=None,price_ceiling=None,protected_tier1_origin_eligible=bool(historical['ready']),
        qualification_basis=selected['qualification_basis'],
        final_call_authority=False,origin_authority=selected['origin_authority'],authority='NATIVE_EARLY_DECISION_NO_FILL_ASSUMED')
    analysis=dict(schema=SCHEMA,contract=raw['contract'],seconds_left=left,candidates=candidates,
        best_directional=best,selection_reason='Native qualified entry policy first, then observational cost-adjusted model value; cheaper price breaks equal-value ties',
        value_entry_policy=qualification,
        current_origin_id=origin.get('origin_id') if origin and origin.get('contract')==raw['contract'] else None,
        model=dict(artifact=frame.get('artifact'),weights=frame.get('weights'),probability_up=up,probability_down=probabilities['DOWN'],
            reliability='Model estimate; current calibration and expanded-price accuracy not established'),
        volatility=dict(range5=fair.get('range5'),vol5=fair.get('vol5'),distance_range5=fair.get('dist_over_range5')),
        reversal=dict(status='WATCH' if (previous and previous['side']!=early['side']) else 'PASS',
            reason=('Model direction changed; directional reversal is observational. Independent SCALP REVERSAL_RECROSS requires its own native origin.' if previous and previous['side']!=early['side'] else 'No model direction change observed; SCALP reversal continues to use its independent native rules.')),
        signal_only=True,orders=False,fee_source=FEE_SOURCE,fee_checked_date='2026-10-09',
        limitations=['Scenario EV uses model probability, not calibrated expected profit',
            'Book depth, fill size, event/account fee overrides and actual slippage are unverified',
            'Settlement reward/risk is not a SCALP price-target forecast',
            'Historical Tier-1 results do not validate expanded prices or windows',
            'Supported-value entry is a conservative implemented policy; its live win rate and profitability are not established'])
    return opportunity,analysis
