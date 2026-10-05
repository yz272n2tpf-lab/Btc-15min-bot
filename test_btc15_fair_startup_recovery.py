"""Exact production failure mechanism, with synthetic causal OHLC prerequisites.

No archived candle/tick payload exists for the incident in this workspace. The
clock, ticker, target, spot, BRTI and asks below match its production log; its
historical features are explicitly synthetic, not an invented recorded replay.
"""
import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from completion_audit.isolated_decision_v2 import FrozenRuntime, stable
from completion_audit.fair_input_candidate import completed_candles
from completion_audit.frozen_model_artifact import load_verified
from test_btc15_isolated_decision_v2 import fixture, OPEN as OLD_OPEN
from btc15_ladder_product_v1 import Directional, native_frame, iso
from btc15_v2_product.fair_readiness import install

OPEN = datetime(2026, 10, 5, 10, 15, tzinfo=timezone.utc).timestamp()
OUT = Path(__file__).parent/'qualification/visible_completion_20261005'


def observations(offset, age=1.5, ask=.991):
    opened = OPEN + (900 if offset >= 900 else 0)
    close = datetime.fromtimestamp(opened+900, timezone.utc)
    from zoneinfo import ZoneInfo
    ticker = 'KXBTC15M-'+close.astimezone(ZoneInfo('America/New_York')).strftime('%y%b%d%H%M-%M').upper()
    bid=round(ask-.001,3)
    value = fixture(offset, ask=ask, btc=86128.05, brti_delay=age,
                    brti_value=86124.12)
    shift = OPEN-OLD_OPEN
    value['decision'] += shift
    for key in ('btc_source', 'btc_received'):
        value[key] += timedelta(seconds=shift)
    value['market'].update(ticker=ticker, open_time=iso(opened), close_time=iso(opened+900),
                          floor_strike=86006.62, yes_bid_dollars=bid, no_ask_dollars=round(1-bid,3))
    proof = value['proof']
    proof.update(ticker=ticker, source_time=iso(value['decision']), consumed_ms=int(value['decision']*1000))
    sequence = int(offset*10)+2
    proof['identity'][2:] = [sequence, round((value['decision']-.2)*1000)]
    for n,event in enumerate(proof['events']):
        event['seq'] = sequence-1+n
        event['msg']['market_ticker'] = ticker
        if 'ts_ms' in event['msg']:event['msg']['ts_ms'] += int(shift*1000)
    proof['events'][0]['msg']['yes_dollars_fp'] = [[str(bid),'10']]
    proof['events'][1]['msg']['price_dollars'] = str(bid)
    value['brti_receipts'] = [(p,t+shift,r+shift,e) for p,t,r,e in value['brti_receipts']]
    return value


def history(end=11):
    index = pd.date_range(iso(OPEN-12*60), iso(OPEN+end*60), freq='min')
    prices = 86000 + np.arange(len(index))*5 + np.sin(np.arange(len(index)))*3
    raw = pd.DataFrame(dict(Open=prices, High=prices+2, Low=prices-2, Close=prices, Volume=1.),index=index)
    return raw


def startup_failure(runtime, raw):
    # Execute the actual entire frozen fair startup try/except; the earlier
    # official-market lookup yielded no active market in production.
    block = next(n for n in runtime.tree.body if isinstance(n,ast.Try)
                 and any(isinstance(f,ast.FunctionDef) and f.name=='_fair_build_snapshot' for f in n.body))
    ns = runtime.ns
    ns.update(_v3_cal=pd.DataFrame(), data_1m=raw, _fair_completed_candles=completed_candles,
              _fair_load_verified=load_verified, _fair_ready=False)
    class AbsentCache:
        def exists(self):return False
    ns['Path'] = lambda name: AbsentCache() if name=='btc_35d_live_cache.csv' else Path(name)
    exec(compile(ast.Module(body=[block],type_ignores=[]),'<actual-frozen-startup>','exec'),ns)
    return ns['_fair_error_text']


def product(runtime, inp, sequence, engine=None):
    at=inp['decision'];proof=inp['proof']
    quote=dict(ticker=inp['market']['ticker'],source_time=iso(at),close_ms=round(datetime.fromisoformat(inp['market']['close_time']).timestamp()*1000),
        exchange_ts_ms=proof['identity'][3], consumed_ms=proof['consumed_ms'], epoch=proof['epoch'],
        market_id='M',sid=1,seq=proof['identity'][2],quotes=[runtime.ns[k] for k in ('up_bid','up_ask','down_bid','down_ask')])
    frame=native_frame(runtime.ns,quote,'native',sequence,at+.001)
    if engine is None:engine=Directional();engine.restore({})
    return engine.process(frame,at+.002)


class FairStartupRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.initial=FrozenRuntime(completed_candles(history()))

    def test_incident_first_prerequisite_then_healthy_native_frame(self):
        broken=self.initial.fork()
        self.assertEqual(startup_failure(broken,history()),"name '_strict_active_open' is not defined")
        inp=observations(702.529806, age=1.5298058986663818)
        broken.ns['iteration']=5  # Existing 30-second console heartbeat.
        before=broken.step(inp)
        self.assertTrue(broken.ns['_brti_contract']['ready'])
        self.assertIsNone(broken.ns['_ec_live'])
        self.assertEqual(product(broken,inp,1)[2]['reason'],'DECISION_INPUT_UNAVAILABLE')
        self.assertTrue(any('fair warming' in x for x in before['messages']))
        repaired=self.initial.fork();startup_failure(repaired,history())
        oracle=self.initial.fork()
        self.assertTrue(install(repaired.ns))
        actual=repaired.step(inp);expected=oracle.step(inp)
        self.assertEqual(stable(actual),stable(expected))
        self.assertIsNotNone(repaired.ns['_ec_live'])
        result=product(repaired,inp,1)
        self.assertNotEqual(result[2]['status'],'UNAVAILABLE')
        self.assertEqual(stable(result),stable(product(oracle,inp,1)))
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'incident_recovery.json').write_text(json.dumps(dict(
            ticker=inp['market']['ticker'],decision=iso(inp['decision']),
            scope='Observed failure mechanism; synthetic historical candles, not recorded incident model output',
            before='DECISION_INPUT_UNAVAILABLE',after=result[2]['status'],
            fair=result[2]['final'],native_outputs_equal=True),indent=2)+'\n')

    def test_missing_model_remains_unavailable(self):
        for key in ('_fair_rf','_fair_artifact','_fair_features','_fair_model_weights_sha256'):
            with self.subTest(key=key):
                runtime=self.initial.fork();startup_failure(runtime,history());runtime.ns.pop(key)
                self.assertFalse(install(runtime.ns))
                runtime.step(observations(702.529806))
                self.assertIsNone(runtime.ns['_ec_live'])
        runtime=self.initial.fork();startup_failure(runtime,history())
        runtime.ns['_fair_error_text']='FAIR MODEL FEATURE IDENTITY MISMATCH'
        self.assertFalse(install(runtime.ns))

    def test_no_carry_forward_after_history_disappears(self):
        runtime=self.initial.fork();startup_failure(runtime,history());self.assertTrue(install(runtime.ns))
        runtime.step(observations(702.529806));self.assertIsNotNone(runtime.ns['_ec_live'])
        runtime.ns['_fair_btc']=runtime.ns['_fair_btc'].iloc[:0]
        runtime.ns['_ec_btc_ticks'].clear()
        inp=observations(707.529806);runtime.step(inp)
        self.assertIsNone(runtime.ns['_ec_live'])
        self.assertEqual(product(runtime,inp,2)[2]['reason'],'DECISION_INPUT_UNAVAILABLE')

    def test_full_native_contract_and_rollover_event_equivalence(self):
        oracle=FrozenRuntime(completed_candles(history(-1)))
        repaired=oracle.fork();startup_failure(repaired,history(-1));self.assertTrue(install(repaired.ns))
        engines=[Directional(),Directional()]
        for engine in engines:engine.restore({})
        counts={};events=[];final_calls=[];holes=[];decisions=0
        for n in range(192):
            offset=.5+5*n;inp=observations(offset,age=(.5,1.5,3.,4.9)[n%4],ask=.35 if 300<=offset<350 else .991)
            # Observations cannot precede contract open at rollover.
            if offset%900 < 5:inp['brti_receipts']=[(86124.12,inp['decision']-.1,inp['decision']-.01,'owner')]
            actual=repaired.step(inp);expected=oracle.step(inp)
            self.assertEqual(stable(actual),stable(expected),offset)
            decisions+=1
            a=product(repaired,inp,n+1,engines[0]);b=product(oracle,inp,n+1,engines[1])
            self.assertEqual(stable(a),stable(b),offset)
            counts[a[2]['status']]=counts.get(a[2]['status'],0)+1
            if a[2]['status']=='UNAVAILABLE':holes.append([offset,a[2].get('reason')])
            if a[0].get('event') or a[0].get('final_event'):events.append(a[0])
            if a[2]['final']['ready']:final_calls.append(dict(at=inp['decision'],publication_id=a[2]['final']['publication_id']))
        self.assertEqual(holes,[])
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'native_contract.json').write_text(json.dumps(dict(status='PASS',
            scope='Synthetic exact frozen native loop; recovered startup vs healthy startup',
            native_decisions=decisions,cadence_seconds=5,elapsed_seconds=960,
            availability=counts,holes=holes,events=events,final_calls=final_calls,native_outputs_equal=True),default=str,indent=2)+'\n')


if __name__=='__main__':unittest.main()
