import ast
from pathlib import Path
import threading
import time
import types
import unittest


class FrozenEntryMetadata(unittest.TestCase):
    def test_active_updates_preserve_entry_time_without_changing_targets(self):
        tree=ast.parse(Path('v81_30_45_live_feed.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='publish_signal')
        clock=[100.]
        scope=dict(STATE={},STATE_LOCK=threading.Lock(),time=types.SimpleNamespace(time=lambda:clock[0],strftime=time.strftime,gmtime=time.gmtime))
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<actual publisher>','exec'),scope)
        row=dict(ticker='KXBTC15M-TEST',left=360.,ts=100.)
        scope['publish_signal'](row,'UP','CORE',.35,.35,100.)
        original=scope['STATE']['last_signal_event'].copy()
        clock[0]=160.;row.update(left=300.,ts=160.)
        scope['publish_signal'](row,'UP','CORE',.35,.45,100.,entry_seconds_left=360.)
        self.assertEqual(scope['STATE']['last_signal_event'],original)
        self.assertEqual(scope['STATE']['seconds_left'],300.)
        self.assertEqual(scope['STATE']['signal_age_sec'],60.)
        self.assertEqual(scope['STATE']['targets'],dict(plus_5c=.4,plus_10c=.45,plus_20c=.55))

    def test_both_sides_retain_original_entry_seconds(self):
        tree=ast.parse(Path('v81_30_45_live_feed.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='publish_signal')
        scope=dict(STATE={},STATE_LOCK=threading.Lock(),time=time)
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<actual publisher>','exec'),scope)
        for side in ('UP','DOWN'):
            scope['publish_signal'](dict(ticker='KXBTC15M-TEST',left=100),side,'SURGE',.3,.36,time.time()-60,entry_seconds_left=160)
            self.assertEqual(scope['STATE']['last_signal_event']['seconds_left_at_signal'],160)
            self.assertEqual(scope['STATE']['last_signal_event']['side'],side)


if __name__=='__main__':unittest.main()
