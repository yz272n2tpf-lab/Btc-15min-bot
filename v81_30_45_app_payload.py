#!/usr/bin/env python3
"""App payload boundary for graduated V8.1 30-45c scalp signals. No orders."""
from v81_30_45_integration_adapter import map_graduated_30_45

def build_scalp_card(**kwargs):
    s=map_graduated_30_45(**kwargs)
    if s is None:return None
    return {
      'module':'SCALP_OPPORTUNITY',
      'version':'V8.1_GRADUATED_30_45',
      'side':s['side'],
      'entry_price':s['entry_ask'],
      'current_bid':s['current_bid'],
      'route':s['route'],
      'seconds_left':s['seconds_left'],
      'targets':{'plus_5c':s['target_5c'],'plus_10c':s['target_10c'],'plus_20c':s['target_20c']},
      'status':s['status'],
      'entry_band':'30-45c',
      'graduated':True,
      'manual_execution_only':True,
      'order_action':None,
      # Explicit namespace separation: these modules are not overwritten here.
      'owns_final_outcome':False,
      'owns_early_opportunity':False,
    }

if __name__=='__main__':
    p=build_scalp_card(side='UP',entry_ask=.34,current_bid=.45,route='CORE',seconds_left=600)
    assert p and p['manual_execution_only'] and p['order_action'] is None
    assert not p['owns_final_outcome'] and not p['owns_early_opportunity']
    print('V81_30_45_APP_PAYLOAD_PASS | MODULE_SEPARATION_PASS | NO_ORDERS')
