"""Migrate four obsolete test fixtures to the existing V2 journal publication seam.

Original V81 tests remain byte-identical; their four failures are reproducible
on frozen 60e6ebd (missing BTC fixture clock and removed legacy publisher calls).
No source gates or strategy code are changed to satisfy these tests.
"""
import ast
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock,patch
from ops.v2_product import legacy_v81_test_fixture as legacy
from btc15_scalp_journal_v1 import Scalp
from btc15_v2_product.journal import ProcessorEnvelope,public_view
from btc15_ladder_journal_v1 import atomic_json

class Adapter(legacy.Adapter):pass

class SourceAge(legacy.SourceAge):
    def setUp(self):
        original=legacy.make_row
        def make_row(now=legacy.NOW):
            row=original(now);row['input_provenance']['btc_source_utc']=legacy.iso(now-.6);return row
        change=patch.object(legacy,'make_row',make_row);change.start();self.addCleanup(change.stop)
    def publication(self):
        row=legacy.make_row();p=ProcessorEnvelope(Scalp(),'v81');p.restore({})
        _,_,view=p.process((dict(kind='SCALP_DECISION',contract=row['ticker'],row=row,captured_ts=legacy.NOW,
            proposals={'UP':{'ok':False},'DOWN':{'ok':False}},diagnostics=[]),'fixture'),legacy.NOW+.01)
        self.assertEqual(view['status'],'PASS');return p,view
    def test_current_publication_cannot_renew_expired_sources(self):
        _,v=self.publication()
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'v81.json';atomic_json(path,v);before=path.read_bytes()
            self.assertEqual(public_view(td,'v81',legacy.NOW+.1)['status'],'PASS')
            self.assertEqual(public_view(td,'v81',legacy.NOW+3.01)['status'],'UNAVAILABLE')
            self.assertEqual(before,path.read_bytes())
    def test_stale_publication_and_horizon_fail_closed(self):
        _,v=self.publication()
        with tempfile.TemporaryDirectory() as td:
            atomic_json(Path(td)/'v81.json',v)
            self.assertEqual(public_view(td,'v81',v['expires_at'])['status'],'UNAVAILABLE')
            self.assertNotIn('official_identity',public_view(td,'v81',legacy.CLOSE))
    def test_btc_age_and_causality_boundaries_remain_exact(self):
        for age,valid in [(10,True),(10.001,False),(-.001,False)]:
            r=legacy.make_row();r['input_provenance']['btc_source_utc']=legacy.iso(legacy.NOW-age)
            if valid:legacy.inputs.require_qualified(r,legacy.NOW)
            else:
                with self.assertRaises(legacy.inputs.InputUnavailable):legacy.inputs.require_qualified(r,legacy.NOW)

class DecoderAndRecovery(legacy.DecoderAndRecovery):
    def test_actual_loop_failure_clears_confirmation_publishes_wait(self):
        tree=ast.parse(Path('v81_30_45_live_feed.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='loop')
        class End(BaseException):pass
        p=Scalp();p.restore({});p.confirm={'old':[legacy.NOW]};rows=[]
        def offer(f):rows.append(p.process(f,legacy.NOW))
        ns=dict(print=lambda *a,**k:None,InputUnavailable=legacy.inputs.InputUnavailable,
            snap=Mock(side_effect=legacy.inputs.InputUnavailable('TIMESTAMPED_QUOTES_UNAVAILABLE')),
            _qualified_inputs=SimpleNamespace(last_ticker=legacy.TICKER),POLL=1.,journal_offer=offer,
            time=SimpleNamespace(time=lambda:legacy.NOW,sleep=Mock(side_effect=End)))
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<frozen-loop>','exec'),ns)
        with self.assertRaises(End):ns['loop']()
        self.assertEqual(len(rows),1);self.assertFalse(p.confirm)
        self.assertEqual(rows[0][0]['unavailable_reason'],'TIMESTAMPED_QUOTES_UNAVAILABLE')
        self.assertEqual(rows[0][2]['status'],'UNAVAILABLE')
