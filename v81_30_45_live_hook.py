#!/usr/bin/env python3
"""Guarded hook between V8.1 graduated scalp events and dashboard renderer. No orders."""
from v81_30_45_app_integration_gate import validate_event

def publish_to_dashboard(renderer, **event):
    """Validate first; renderer is called only for a graduated safe payload."""
    result=validate_event(**event)
    if not result.get('publish'):
        return {'rendered':False,'reason':result.get('reason','BLOCKED')}
    payload=result['payload']
    # Hard safety assertions immediately before UI boundary.
    assert payload['manual_execution_only'] is True
    assert payload['order_action'] is None
    assert payload['owns_final_outcome'] is False
    assert payload['owns_early_opportunity'] is False
    renderer(payload)
    return {'rendered':True,'version':payload['version'],'entry_band':payload['entry_band']}

def self_test():
    seen=[]
    def renderer(p):seen.append(p)
    ok=publish_to_dashboard(renderer,side='UP',entry_ask=.34,current_bid=.45,route='CORE',seconds_left=600)
    assert ok['rendered'] and len(seen)==1 and seen[0]['version']=='V8.1_GRADUATED_30_45'
    bad=publish_to_dashboard(renderer,side='DOWN',entry_ask=.20,current_bid=.35,route='CORE',seconds_left=600)
    assert not bad['rendered'] and len(seen)==1
    print('V81_30_45_LIVE_HOOK_PASS | FAIL_CLOSED | FINAL/EARLY PRESERVED | SIGNAL_ONLY | NO_ORDERS')

if __name__=='__main__':self_test()
