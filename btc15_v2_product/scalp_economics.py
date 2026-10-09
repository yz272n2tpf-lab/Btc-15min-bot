"""Cost accounting for observed liquidation, never a future BID forecast."""
from .early_entry import fee_valid, finite
from .opportunities import fee_scenario
from .scalp_policy import proposal_for

NET_FLOOR = .02  # User-required exclusion: <=2 cents is not worthwhile.
ENTRY_POLICY = 'SCALP_MOMENTUM_COST_ROOM_V2'


def liquidation(entry, bid, ask, schedule, at, entry_schedule=None, entry_at=None):
    valid=all(finite(x) and 0<=x<=1 for x in (entry,bid,ask)) and bid<=ask and entry>0
    current_fees=fee_valid(dict(fee_schedule=schedule,feature_cutoff=at))
    original_fees=fee_valid(dict(fee_schedule=entry_schedule,feature_cutoff=entry_at))
    gross=bid-entry if valid else None
    ef=fee_scenario(entry,entry_schedule['multiplier']) if valid and original_fees else None
    xf=fee_scenario(bid,schedule['multiplier']) if valid and current_fees else None
    spread=ask-bid if valid else None
    net=gross-ef-xf if ef is not None and xf is not None else None
    stress=net-spread if net is not None else None
    return dict(original_ask=entry,observed_bid=bid if valid else None,gross_movement_cents=None if gross is None else gross*100,
        entry_fee_scenario=ef,exit_fee_scenario=xf,observed_spread=spread,
        net_liquidation_scenario=net,execution_reserve=spread,net_after_execution_reserve=stress,
        meaningful_positive_net=stress is not None and stress>NET_FLOOR+1e-12,
        required_net_exclusive=NET_FLOOR,fees_verified=original_fees and current_fees,
        basis='One-contract taker fees rounded up per leg; ASK-to-BID already includes crossing the book; one additional observed spread is execution stress, not a fill/slippage forecast. Depth, quantity and account/event overrides require manual verification.',
        realized_profit=None,fill_guaranteed=False)


def entry_assessment(row, side, schedule, history=None):
    """Qualify cost-feasible native momentum, never promise a future sale price.

    The $1 payout bounds possible price room; it is not a projected exit.
    Existing BTC30 qualification supplies direction. The same validated history
    checks whether Kalshi's BID is contradicting that move beyond one spread.
    Fees + crossing + one extra spread measure execution drag. Remaining room
    must cover that drag and allow >2c net, without a fixed entry-price band.
    """
    proposal=proposal_for(row,side,history or {})
    q=row['input_provenance']['quote'];ask=q[side.lower()+'_ask'];bid=q[side.lower()+'_bid']
    econ=liquidation(ask,bid,ask,schedule,row['ts'],schedule,row['ts'])
    spread=econ['observed_spread'];ef=econ['entry_fee_scenario']
    # Maximum schedule fee over all improving sale prices, not a chosen target.
    xf=fee_scenario(max(.5,ask),schedule['multiplier']) if econ['fees_verified'] else None
    known=ef is not None and xf is not None and spread is not None
    drag=ef+xf+2*spread if known else None
    room=1-ask-ef-xf-spread if known else None
    loss=ask+ef if ef is not None else None
    hurdle=ask+ef+xf+spread+NET_FLOOR if known else None
    observed_move=None
    if proposal['features'] is not None:
        observed_move=bid-proposal['history']['30']['input_provenance']['quote'][side.lower()+'_bid']
    conditions=dict(native_momentum=proposal['ok'],current_series_fees=econ['fees_verified'],
        two_sided_execution=finite(bid) and finite(ask) and 0<bid<=ask<1,
        net_price_room=room is not None and room>NET_FLOOR+1e-12,
        room_covers_execution_drag=room is not None and room>drag+1e-12,
        kalshi_not_opposing=observed_move is not None and spread is not None and observed_move>=-spread-1e-12)
    reason=('NATIVE_MOMENTUM_UNQUALIFIED' if not conditions['native_momentum'] else
        'CURRENT_SERIES_FEES_UNAVAILABLE' if not conditions['current_series_fees'] else
        'TWO_SIDED_EXECUTION_UNAVAILABLE' if not conditions['two_sided_execution'] else
        'INSUFFICIENT_NET_PRICE_ROOM' if not conditions['net_price_room'] else
        'EXECUTION_COSTS_DOMINATE_REMAINING_ROOM' if not conditions['room_covers_execution_drag'] else
        'KALSHI_BID_OPPOSES_MOMENTUM' if not conditions['kalshi_not_opposing'] else
        'QUALIFIED_MOMENTUM_WITH_COST_ROOM')
    explanations={
        'NATIVE_MOMENTUM_UNQUALIFIED':'Native momentum, causal history or remaining time does not qualify.',
        'CURRENT_SERIES_FEES_UNAVAILABLE':'Fresh applicable series fees are required to assess entry costs.',
        'TWO_SIDED_EXECUTION_UNAVAILABLE':'A positive same-side BID and usable ASK are required.',
        'INSUFFICIENT_NET_PRICE_ROOM':'Remaining price room cannot support more than 2¢ net after fees and execution reserve.',
        'EXECUTION_COSTS_DOMINATE_REMAINING_ROOM':'Remaining cost-adjusted price room does not exceed the round-trip execution-cost budget.',
        'KALSHI_BID_OPPOSES_MOMENTUM':'Same-side Kalshi BID fell by more than the current spread despite the BTC momentum setup.',
        'QUALIFIED_MOMENTUM_WITH_COST_ROOM':'Native BTC30 momentum and execution-cost room qualify; positive expected profit is not established.'}
    return dict(ready=all(conditions.values()),policy=ENTRY_POLICY,economics=econ,conditions=conditions,
        native_reason=proposal['reason'],projected_exit_bid=None,projected_net=None,expected_profit=None,
        profit_expectation='UNESTABLISHED',price_ceiling=None,reason=reason,explanation=explanations[reason],
        entry_room=dict(entry_ask=ask,observed_bid=bid,observed_spread=spread,
            entry_fee_estimate=ef,exit_fee_budget=xf,execution_reserve=spread,
            round_trip_execution_cost=drag,net_price_room=room,maximum_entry_loss=loss,
            capacity_to_full_loss=room/loss if room is not None and loss else None,
            bid_hurdle_exclusive=hurdle,required_bid_rise=None if hurdle is None else hurdle-bid,
            observed_bid_change_30s=observed_move,btc30=(proposal['features'] or {}).get('btc30'),
            expected_profit=None,
            basis='Price room is bounded by $1 payout, not an executable exit or forecast. The BID hurdle is a cost threshold, not a target. Full entry outlay can be lost; depth, fills and account/event fee overrides remain unverified.'))
