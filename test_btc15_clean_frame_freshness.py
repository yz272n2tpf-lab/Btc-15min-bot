import ast
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
import os
import time
import unittest
from unittest.mock import Mock, patch


class FrameFreshness(unittest.TestCase):
    def make(self, delay=0, quote_missing=False, close_delay=600):
        now=datetime(2026,9,23,20,0,tzinfo=timezone.utc)
        clock=[now]
        class Clock:
            @staticmethod
            def now(tz=None):return clock[0]
        response=Mock();response.json.return_value={'price':'85000','time':now.isoformat()}
        def get(*args,**kwargs):clock[0]+=timedelta(seconds=delay);return response
        quotes=Mock(side_effect=[(.4,.41,.59,.6),None if quote_missing else (.42,.43,.57,.58)])
        env=dict(datetime=Clock,timezone=timezone,time=time,os=os,
                 active_market=lambda:dict(ticker='KXBTC15M-TEST',close_time=(now+timedelta(seconds=close_delay)).isoformat()),
                 dt=lambda x:datetime.fromisoformat(x),target_from_market=lambda _:85001,
                 _production_guard=lambda *args:True, num=lambda x:None if x is None else float(x),
                 read_shared_brti=lambda **kwargs:dict(age_seconds=1,status='PRIMARY_OK',orders=False,value=85002,source_ts_ms=int(now.timestamp()*1000)-1000),
                 consume_ws_quotes=quotes,valid_quote=lambda v:isinstance(v,(int,float)) and 0<=v<=1,
                 _clean_http=SimpleNamespace(get=get),CB='https://example.invalid',
                 _clean_stats=dict(accepted_frames=0,brti_waits=0,quote_waits=0,metadata_waits=0),
                 health=dict(snapshots=0,brti_clean_snapshots=0))
        tree=ast.parse(Path('scalp_move_shadow_v2_finalprod_clean.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='snap')
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<actual clean snap>','exec'),env)
        return env

    def test_slow_btc_read_does_not_refresh_brti(self):
        env=self.make(delay=5)
        with patch.dict(os.environ,{},clear=True):self.assertIsNone(env['snap']())
        self.assertEqual(env['_clean_stats']['brti_waits'],1)

    def test_expired_quote_is_rechecked_after_btc_read(self):
        env=self.make(delay=1,quote_missing=True)
        with patch.dict(os.environ,{},clear=True):self.assertIsNone(env['snap']())
        self.assertEqual(env['_clean_stats']['quote_waits'],1)

    def test_post_read_clock_and_refreshed_quotes_are_used(self):
        env=self.make(delay=1)
        with patch.dict(os.environ,{},clear=True):result=env['snap']()
        self.assertEqual(result['left'],599)
        self.assertEqual(result['up_ask'],.43)
        self.assertEqual(env['_clean_stats']['accepted_frames'],1)

    def test_contract_that_closes_during_read_is_rejected(self):
        env=self.make(delay=2,close_delay=1)
        with patch.dict(os.environ,{},clear=True):self.assertIsNone(env['snap']())
        self.assertEqual(env['_clean_stats']['metadata_waits'],1)


if __name__=='__main__':unittest.main()
