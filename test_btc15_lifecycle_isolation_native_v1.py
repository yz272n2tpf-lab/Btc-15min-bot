"""Exact conditional native parity with the REAL durable consumer enabled/off."""
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest

from completion_audit.isolated_decision_v2 import FrozenRuntime,stable
from test_btc15_isolated_decision_v2 import completed,fixture,TICKER
from test_btc15_directional_signal_authority_v1 import fixture as publication,START
from btc15_directional_signal_authority_v1 import initialize
from btc15_isolated_lifecycle_consumer_v1 import Consumer
from btc15_protected_publication_handoff_v1 import envelope
from btc15_qualified_forward_observer_v1 import observation,append


class DurableNativeParity(unittest.TestCase):
    def test_every_native_state_publication_cutoff_source_and_scalp_is_identical(self):
        initial=FrozenRuntime(completed());off,on=initial.fork(),initial.fork()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);initialize(root/'db',START);clock=[START+timedelta(seconds=300)]
            consumer=Consumer(root/'csv',root/'db',root/'cursor',epoch='SYNTHETIC',build={},clock=lambda:clock[0])
            for i,at in enumerate((300.,300.000001,305,310,315,320,325,330,895,901,906)):
                native=fixture(at,ask=(.31,.79,.42)[i%3],btc=100000+(-1)**i*85,
                    quote_wait=i in (3,4),brti_delay=4.999999 if i==1 else (4.999999,5.000001,2.4)[i%3],
                    ticker=TICKER if at<900 else 'KXBTC15M-19DEC311930-15')
                expected=off.step(native);actual=on.step(native)
                self.assertEqual(stable(actual),stable(expected))
                before=stable(on.snapshot())
                raw=publication(300+i*5,final_ready=i==2,final_side='DOWN' if i>5 else 'UP')
                clock[0]=START+timedelta(seconds=300+i*5)
                record=observation(raw,clock[0]);record.update(record_type='OBSERVATION',
                    protected_publication_bytes=envelope(json.dumps(raw).encode()))
                append(record,root/'csv')
                result=consumer.step()
                if result['status']=='HEADER':consumer.step()
                self.assertEqual(stable(on.snapshot()),before)
                self.assertEqual(stable(on.snapshot()),stable(off.snapshot()))
                self.assertEqual(stable(on.diag),stable(off.diag))


if __name__=='__main__':unittest.main()
