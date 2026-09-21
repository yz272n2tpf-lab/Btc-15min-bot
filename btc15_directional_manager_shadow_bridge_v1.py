from btc15_main_protected_state_adapter_v1 import protected_main_summary
from btc15_signal_integration_v1 import ScalpState
from btc15_dashboard_state_contract_v1 import build_dashboard_contract

def shadow_cycle(main_state, scalp_state=None, *, position_open=False):
    """Pure parity bridge: protected production JSON -> dashboard contract. No I/O."""
    protected=protected_main_summary(main_state)
    scalp=(scalp_state or ScalpState()).normalized()
    out=build_dashboard_contract(protected,scalp,position_open=position_open)
    assert out["contract"]==protected["contract"]
    assert out["seconds_left"]==protected["seconds_left"]
    assert out["kalshi"]["target"]==protected["kalshi_target"]
    assert out["safety"]["orders_enabled"] is False
    return out
