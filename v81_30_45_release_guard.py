#!/usr/bin/env python3
"""Final fail-closed release guard for V8.1 30-45c dashboard integration."""
from v81_30_45_app_integration_gate import validate_event

REQUIRED_MARKERS={
 'version':'V8.1_GRADUATED_30_45','entry_band':'30-45c','graduated':True,
 'manual_execution_only':True,'order_action':None,
 'owns_final_outcome':False,'owns_early_opportunity':False,
}

def release_check():
    cases=[
      dict(side='UP',entry_ask=.30,current_bid=.35,route='CORE',seconds_left=899),
      dict(side='DOWN',entry_ask=.45,current_bid=.65,route='SURGE',seconds_left=60),
    ]
    for c in cases:
      r=validate_event(**c); assert r['publish']; p=r['payload']
      for k,v in REQUIRED_MARKERS.items(): assert p.get(k)==v,(k,p.get(k),v)
    blocked=[
      dict(side='UP',entry_ask=.299,current_bid=.40,route='CORE',seconds_left=300),
      dict(side='UP',entry_ask=.451,current_bid=.55,route='CORE',seconds_left=300),
      dict(side='UP',entry_ask=.35,current_bid=.50,route='SUB30_STRONG',seconds_left=300),
      dict(side='UP',entry_ask=.35,current_bid=.50,route='CORE',seconds_left=0),
    ]
    assert all(not validate_event(**c)['publish'] for c in blocked)
    print('V81_30_45_RELEASE_GUARD_PASS | FAIL_CLOSED | MODULE_SEPARATION | MANUAL_ONLY | NO_ORDERS')
    return True

if __name__=='__main__':release_check()
