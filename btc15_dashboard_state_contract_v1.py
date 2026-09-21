from btc15_directional_position_manager_v1 import compose_position_view
def build_dashboard_contract(main_summary, scalp, *, position_open=False):
 e=main_summary["early"]; f=main_summary["final"]; contract=str(main_summary.get("contract") or "")
 p=compose_position_view(contract,early=e,final=f,scalp=scalp,position_open=position_open)
 return {"schema":"BTC15_DASHBOARD_STATE_CONTRACT_V1","contract":contract,
 "seconds_left":main_summary.get("seconds_left"),"kalshi":{"target":main_summary.get("kalshi_target"),
 "up_bid":main_summary.get("up_bid"),"up_ask":main_summary.get("up_ask"),
 "down_bid":main_summary.get("down_bid"),"down_ask":main_summary.get("down_ask")},
 "early":{"state":e.state,"side":e.side,"ask":e.ask,"fair":e.fair,"edge":e.edge},
 "final":{"state":f.state,"side":f.side,"fair":f.fair},
 "scalp":{"state":scalp.state,"side":scalp.side,"entry_ask":scalp.entry_ask,"current_bid":scalp.current_bid,
 "peak_exec_gain":scalp.peak_exec_gain,"exec_gain":scalp.exec_gain},
 "position":p.to_dict(),"safety":{"signal_only":True,"manual_execution_only":True,"orders_enabled":False}}
