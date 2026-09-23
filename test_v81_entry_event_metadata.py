import ast
from pathlib import Path
import threading
import time
import types
import unittest
from test_v81_qualified_inputs import NOW, make_row, publisher_scope


class FrozenEntryMetadata(unittest.TestCase):
    def test_active_updates_preserve_entry_time_without_changing_targets(self):
        tree=ast.parse(Path('v81_30_45_live_feed.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='publish_signal')
        clock=[NOW];scope=publisher_scope(clock)
        row=make_row(NOW)
        row['up_ask']=row['input_provenance']['quote']['up_ask']=.44
        scope['publish_signal'](row,'UP','CORE',.44,.43,NOW)
        original=scope['STATE']['last_signal_event'].copy()
        clock[0]=NOW+60;row=make_row(NOW+60)
        row['up_bid']=row['input_provenance']['quote']['up_bid']=.45
        row['up_ask']=row['input_provenance']['quote']['up_ask']=.46
        scope['publish_signal'](row,'UP','CORE',.44,.45,NOW,entry_seconds_left=original['seconds_left_at_signal'],entry_provenance=original['entry_provenance'])
        self.assertEqual(scope['STATE']['last_signal_event'],original)
        self.assertEqual(scope['STATE']['seconds_left'],round(row['left'],1))
        self.assertEqual(scope['STATE']['signal_age_sec'],60.)
        self.assertEqual(scope['STATE']['targets'],dict(plus_5c=.49,plus_10c=.54,plus_20c=.64))

    def test_both_sides_retain_original_entry_seconds(self):
        tree=ast.parse(Path('v81_30_45_live_feed.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='publish_signal')
        scope=publisher_scope([NOW])
        for side in ('UP','DOWN'):
            row=make_row();key=side.lower()+'_ask'
            row[key]=row['input_provenance']['quote'][key]=.44
            row[side.lower()+'_bid']=row['input_provenance']['quote'][side.lower()+'_bid']=.43
            scope['publish_signal'](row,side,'SURGE',.44,.43,NOW,entry_seconds_left=436.3)
            self.assertEqual(scope['STATE']['last_signal_event']['seconds_left_at_signal'],436.3)
            self.assertEqual(scope['STATE']['last_signal_event']['side'],side)


if __name__=='__main__':unittest.main()
