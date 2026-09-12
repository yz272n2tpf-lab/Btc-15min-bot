#!/usr/bin/env python3
from v81_30_45_integration_adapter import map_graduated_30_45

def run():
    # Graduated boundaries and both sides/routes.
    for side in ('UP','DOWN'):
        for route in ('CORE','SURGE'):
            for entry in (.30,.34,.45):
                x=map_graduated_30_45(side=side,entry_ask=entry,current_bid=entry+.10,route=route,seconds_left=300)
                assert x is not None
                assert x['engine']=='V81_GRADUATED_30_45'
                assert x['signal_only'] is True and x['automatic_order'] is False
                assert x['status']=='ACTIONABLE_EXPANSION'
    # Ungraduated lanes/routes must never leak through.
    for entry in (.03,.07,.15,.29,.451):
        assert map_graduated_30_45(side='UP',entry_ask=entry,current_bid=.50,route='CORE',seconds_left=300) is None
    assert map_graduated_30_45(side='DOWN',entry_ask=.35,current_bid=.50,route='SUB30_STRONG',seconds_left=300) is None
    assert map_graduated_30_45(side='UP',entry_ask=.35,current_bid=.50,route='CORE',seconds_left=0) is None
    print('V81_30_45_INTEGRATION_REGRESSION_PASS | GRADUATED_ONLY | SIGNAL_ONLY | NO_ORDERS')

if __name__=='__main__': run()
