"""Cost accounting for observed liquidation, never a future BID forecast."""
from .early_entry import fee_valid, finite
from .opportunities import fee_scenario

NET_FLOOR = .02  # User-required exclusion: <=2 cents is not worthwhile.


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


def entry_assessment(row, side, schedule):
    q=row['input_provenance']['quote'];ask=q[side.lower()+'_ask'];bid=q[side.lower()+'_bid']
    econ=liquidation(ask,bid,ask,schedule,row['ts'],schedule,row['ts'])
    # BTC30 is a BTC momentum observation, not an estimate of a later Kalshi BID.
    # Neither maximum payout nor the old 5c arm supplies that missing evidence.
    return dict(ready=False,policy='SCALP_NET_EVIDENCE_V1',economics=econ,
        projected_exit_bid=None,projected_net=None,price_ceiling=None,
        reason='NO_SUPPORTED_EXIT_BID_FORECAST' if econ['fees_verified'] else 'CURRENT_SERIES_FEES_UNAVAILABLE',
        explanation='Momentum scan only — NOT ISSUED BUY. A supported exit-value estimate with net margin greater than 2¢ after entry/exit fees and execution stress is required; this scan does not supply one.')
