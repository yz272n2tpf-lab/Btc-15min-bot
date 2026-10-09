"""Causal feature publication and native, conditional EARLY risk management.

No model refit, price forecast, fill assumption or order execution. This explicit
risk policy has not established profitability. Natural side/value boundaries
replace invented fixed stops or profit targets.
"""
from copy import deepcopy
from .early_entry import finite, fee_valid, ARTIFACT, WEIGHTS
from .opportunities import fee_scenario

POLICY = 'EARLY_THESIS_AND_LIQUIDATION_V1'


def install_features(ns):
    original = ns['_fair_build_snapshot']
    def capture(df, start, target, *args, **kwargs):
        ns['_early_model_features'] = None
        row = original(df, start, target, *args, **kwargs)
        cut = kwargs.get('_cut')
        if row is not None and cut is not None:
            ns['_early_model_features'] = dict(target=float(target),
                official_open=start.timestamp(),feature_cutoff=cut.timestamp(),values=deepcopy(row))
        return row
    ns['_fair_build_snapshot'] = capture


def features(f):
    x=f.get('model_features') or {};v=x.get('values') or {}
    if (f.get('artifact')!=ARTIFACT or f.get('weights')!=WEIGHTS or
        x.get('target')!=f['target'] or x.get('official_open')!=f['official_open'] or
        not finite(x.get('feature_cutoff')) or abs(x['feature_cutoff']-f['feature_cutoff'])>1e-6 or
        not all(finite(v.get(k)) for k in ('move1','move5','range5','vol5','current_coinbase_close')) or
        v['range5']<0 or v['vol5']<0 or v['current_coinbase_close']!=f['btc_price']):
        return None
    return v


def decide(f, origin, prior_p, path, current_action, later_bid, terminal=None):
    """Called only after full native source qualification and origin binding."""
    side=origin['side'];sign=1 if side=='UP' else -1
    p=f['fair'][side.lower()+'_fair'];bid=f[side.lower()+'_bid']
    x=features(f);weak=p<prior_p-1e-12
    opposing=f['fair']['side']!=side
    btc=sign*(f['btc_price']-f['target']);brti=sign*(f['brti']['value']-f['target'])
    adverse=bool(x and sign*x['move1']<0)
    trend_adverse=bool(x and sign*x['move5']<0)
    gross=bid-origin['original_ask']
    entry_fee=(origin.get('qualification') or {}).get('economics',{}).get('entry_fee_scenario')
    if entry_fee is None and fee_valid(origin['entry_provenance']):
        entry_fee=fee_scenario(origin['original_ask'],origin['entry_provenance']['fee_schedule']['multiplier'])
    exit_fee=fee_scenario(bid,f['fee_schedule']['multiplier']) if fee_valid(f) else None
    net=gross-entry_fee-exit_fee if entry_fee is not None and exit_fee is not None else None
    giveback=path.get('mfe') is not None and gross<path['mfe']-1e-12
    economics=dict(original_signal_ask=origin['original_ask'],current_bid=bid,
        gross_movement_cents=gross*100,entry_fee_scenario=entry_fee,exit_fee_scenario=exit_fee,
        net_liquidation_scenario=net,realized_profit=None,fill_guaranteed=False,
        basis='If manually entered at signal ASK and closed at displayed BID; one contract; fees estimated, overrides/depth/slippage unverified')
    evidence=dict(held_model_probability=p,prior_model_probability=prior_p,
        probability_weakening=weak,model_opposes=opposing,btc_held_side_gap=btc,
        brti_held_side_gap=brti,causal_momentum_available=x is not None,
        recent_momentum_adverse=adverse,trend_adverse=trend_adverse,
        observed_bid_giveback=giveback,later_executable_bid=bool(later_bid and bid>0))
    if terminal:
        return dict(state='EXIT',reason=terminal['reason'],terminal=terminal,
            economics=economics,evidence=evidence,new_exit=False,policy=POLICY)
    thesis_failed=opposing and btc<0 and brti<0 and adverse
    sell_dominates=bool(exit_fee is not None and bid-exit_fee>=p and weak and adverse)
    exit_reason=('DIRECTIONAL_THESIS_INVALIDATED' if thesis_failed else
                 'NET_BID_EXCEEDS_WEAKENING_MODEL_VALUE' if sell_dominates else None)
    if exit_reason and later_bid and bid>0:
        q=f['quote']
        terminal=dict(state='EXIT',actionable_exit=True,origin_id=origin['origin_id'],
            contract=origin['contract'],side=side,original_ask=origin['original_ask'],
            decision_ts=f['captured_ts'],executable_exit_bid=bid,quote=deepcopy(q),
            reason=exit_reason,policy=POLICY,evidence=evidence,economics=economics,
            manual_fill=None,realized_profit=None,closure_confirmed=False)
        state='EXIT';reason=exit_reason
    elif current_action=='BUY':
        state='ENTER';reason='ENTRY_EVIDENCE_ACCEPTED'
    elif current_action=='PROTECT':
        state='PROTECT';reason='ESTABLISHED_PROTECTION_REMAINS_LATCHED'
    elif (weak or opposing) and (btc<=0 or brti<=0 or adverse and giveback):
        state='PROTECT';reason='DIRECTIONAL_DETERIORATION_CORROBORATED_BY_MARKET'
    elif net is not None and net>0 and adverse and (weak or giveback):
        state='PROTECT';reason='POSITIVE_LIQUIDATION_SCENARIO_WITH_DETERIORATION'
    elif weak or opposing or btc<=0 or brti<=0 or adverse or trend_adverse or giveback or x is None:
        state='WATCH';reason='SUPPORT_WEAKENED_OR_MOMENTUM_UNAVAILABLE'
    else:
        state='HOLD';reason='DIRECTION_AND_MARKET_SUPPORT_CONTINUE'
    if exit_reason and not (later_bid and bid>0):
        reason+='; EXIT_WAITING_FOR_LATER_POSITIVE_SAME_SIDE_BID'
    return dict(state=state,reason=reason,terminal=terminal,economics=economics,
        evidence=evidence,new_exit=state=='EXIT',policy=POLICY)
