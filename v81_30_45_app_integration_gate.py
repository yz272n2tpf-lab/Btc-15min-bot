#!/usr/bin/env python3
"""Fail-closed gate for V8.1 graduated 30-45c app integration. SIGNAL ONLY."""
from v81_30_45_app_payload import build_scalp_card

def validate_event(**event):
    p=build_scalp_card(**event)
    if p is None:return {'publish':False,'reason':'NOT_GRADUATED_30_45'}
    checks=[
      p.get('version')=='V8.1_GRADUATED_30_45',
      p.get('entry_band')=='30-45c',
      p.get('graduated') is True,
      p.get('manual_execution_only') is True,
      p.get('order_action') is None,
      p.get('owns_final_outcome') is False,
      p.get('owns_early_opportunity') is False,
    ]
    if not all(checks):return {'publish':False,'reason':'BOUNDARY_GUARD_FAIL'}
    return {'publish':True,'payload':p}

def self_test():
    assert validate_event(side='UP',entry_ask=.30,current_bid=.40,route='CORE',seconds_left=500)['publish']
    assert validate_event(side='DOWN',entry_ask=.45,current_bid=.55,route='SURGE',seconds_left=300)['publish']
    for x in (.03,.07,.15,.29,.451):
      assert not validate_event(side='UP',entry_ask=x,current_bid=.50,route='CORE',seconds_left=300)['publish']
    assert not validate_event(side='UP',entry_ask=.35,current_bid=.50,route='SUB30_STRONG',seconds_left=300)['publish']
    assert not validate_event(side='UP',entry_ask=.35,current_bid=.50,route='CORE',seconds_left=0)['publish']
    print('V81_APP_INTEGRATION_GATE_PASS | 30-45 ONLY | MODULE_SEPARATION | SIGNAL_ONLY | NO_ORDERS')

if __name__=='__main__':self_test()
