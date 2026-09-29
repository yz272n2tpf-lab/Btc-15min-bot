"""Native controls with downstream authority; no AST capture instrumentation."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

from btc15_directional_signal_authority_v1 import Authority, BASE, initialize
from btc15_qualified_forward_observer_v1 import observation
from test_btc15_directional_signal_authority_v1 import fixture as publication, START
from test_btc15_isolated_decision_v2 import completed, fixture, TICKER
from completion_audit.isolated_decision_v2 import FrozenRuntime, stable


class NoninterferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.initial=FrozenRuntime(completed())

    def test_native_full_state_outputs_brtiboundaries_wait_rollover_and_failed_sink(self):
        a,b=self.initial.fork(),self.initial.fork()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'db';initialize(path,START)
            authority=Authority(path,runtime_epoch='synthetic',build={})
            for i,t in enumerate((300,305.000001,310,315,320,325,330,895,901,906)):
                native=fixture(t,ask=(.31,.79,.42)[i%3],btc=100000+(-1)**i*85,
                    quote_wait=i==3,brti_delay=(4.999999,5.000001,2.4)[i%3],
                    ticker=TICKER if t<900 else 'KXBTC15M-19DEC311930-15')
                self.assertEqual(stable(a.step(native)),stable(b.step(native)))
                self.assertEqual(stable(a.snapshot()),stable(b.snapshot()))
                before=stable(b.snapshot())
                now=START+timedelta(seconds=300+i*5)
                raw=publication(300+i*5,final_side='DOWN' if i>=5 else 'UP')
                if i==4:
                    with sqlite3.connect(path) as db:
                        db.execute("CREATE TRIGGER fail BEFORE INSERT ON records BEGIN SELECT RAISE(ABORT,'sink'); END")
                    with self.assertRaises(sqlite3.IntegrityError):
                        authority.consume(raw,observation(raw,now),now_utc=now,receipt_utc=now)
                    with sqlite3.connect(path) as db:db.execute('DROP TRIGGER fail')
                else:
                    authority.consume(raw,observation(raw,now),now_utc=now,receipt_utc=now)
                self.assertEqual(stable(b.snapshot()),before)
                self.assertEqual(stable(a.diag),stable(b.diag))

    def test_true_scalp_stop_first_overlapping_serial_and_profit_lifecycle_remain_native(self):
        r=self.initial.fork()
        names='minutes_left btc_gap_side abs_gap btc_move_15s_side btc_move_30s_side btc_move_60s_side ask_move_15s ask_move_30s ask_move_60s bounce_from_low drawdown_from_high ask_position_60'
        features={k:1. for k in names.split()};features['entry_ask']=.30
        r.ns['_true_scalp_probability']=lambda *args:(.95,dict(features))
        def snap(t,bid,contract='A'):
            return dict(contract=contract,timestamp_utc=f'2020-01-01T00:{t//60:02d}:{t%60:02d}Z',
                        seconds_left=500,up_bid=bid,up_ask=.30,down_bid=.1,down_ask=.9)
        r.ns['_maybe_true_scalp_signal']('UP',snap(0,.28),0.)
        original=deepcopy(r.ns['_true_scalp_pending'][0])
        r.ns['_update_true_scalp_pending'](snap(5,.19),5.)
        r.ns['_update_true_scalp_pending'](snap(10,.55),10.)
        first=r.ns['_true_scalp_pending'][0]
        self.assertEqual(first['entry_ask'],.30);self.assertEqual(first['stop_ts'],5.)
        self.assertTrue(all(value is None for value in first['hits'].values()))
        r.ns['_update_profit_shadow'](snap(10,.45),10.,None)
        r.ns['_update_profit_shadow'](snap(15,.39),15.,None)
        r.ns['_maybe_true_scalp_signal']('UP',snap(120,.28),120.)
        events=r.ns['_true_scalp_pending']
        self.assertEqual(len(events),2)
        self.assertNotEqual(events[0]['signal_id'],events[1]['signal_id'])
        self.assertEqual(events[0]['signal_id'],original['signal_id'])
        r.ns['_update_true_scalp_pending'](snap(125,.41),125.)
        self.assertEqual(events[1]['hits'][.10],125.)
        before=deepcopy(r.ns['_true_scalp_pending'])
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'db';initialize(path,START)
            a=Authority(path,runtime_epoch='synthetic',build={})
            for n in (300,305,310):
                raw=publication(n,final_side='DOWN' if n==310 else 'UP')
                now=START+timedelta(seconds=n)
                a.consume(raw,observation(raw,now),now_utc=now,receipt_utc=now)
        self.assertEqual(r.ns['_true_scalp_pending'],before)
        r.ns['_update_true_scalp_pending'](snap(130,.50,'B'),130.)
        r.ns['_update_profit_shadow'](snap(130,.50,'B'),130.,None)
        self.assertEqual(r.ns['_true_scalp_pending'],[])

    def test_all_native_scheduler_owner_and_model_files_identical_to_qualified_base(self):
        root=Path(__file__).parent
        names=('bot_two_output_build_v4_13_profit_protection_shadow.py',
               'btc15_information_native_offpath_candidate.py', 'btc15_information_native_v1.py',
               'btc15_brti_delivery_v1.py','btc15_decision_clock_v1.py',
               'btc15_kalshi_quote_provenance_v1.py','brti_shared_feed_v1.py',
               'BTC15_INSTALL_LIVE_DASHBOARD_V13.py','btc15_run_full_validation_v1.py',
               'requirements.txt','completion_audit/model_artifact/frozen_fair_candidate.joblib')
        for name in names:
            before=subprocess.check_output(['git','show',BASE+':'+name],cwd=root)
            self.assertEqual((root/name).read_bytes(),before,name)


if __name__=='__main__':unittest.main()
