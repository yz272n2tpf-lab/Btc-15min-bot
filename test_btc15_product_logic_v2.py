"""Focused completion gate: causal guidance, durable evidence, source reuse."""
from datetime import datetime,timezone
import hashlib,json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import btc15_ladder_product_v1 as product
from btc15_ladder_journal_v1 import Journal,coverage_view,packed
from btc15_ladder_settlement_v2 import receipt,SettlementReader
from btc15_position_context_v2 import context
from test_btc15_ladder_completion_v1 import frame,OPEN
from test_btc15_scalp_journal_v1 import state,Scalp,ENTRY,TICKER

def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()

class FinishedDirectionalTests(unittest.TestCase):
    def setUp(self):self.e=product.Directional();self.e.restore({})
    def step(self,**kw):
        f=frame(**kw);return self.e.process(f,f['captured_ts']+.01)
    def test_value_ceiling_and_no_final_entry_veto(self):
        _,_,v=self.step(ask=.46);self.assertEqual(v['early']['guidance'],'PASS')
        _,_,v=self.step(offset=305,sequence=2,ask=.35)
        self.assertEqual(v['early']['guidance'],'ENTER');self.assertFalse(v['final']['ready'])
        self.assertNotIn('edge_ge8',v['early']['conditions']);self.assertEqual(v['early']['target_ask'],.50)
    def test_strengthening_weakening_mixed_sequence(self):
        _,_,e=self.step()
        _,_,v=self.step(offset=305,sequence=2,p=.85)
        self.assertEqual(v['early']['guidance'],'HOLD');self.assertEqual(v['final']['helper']['relation'],'STRENGTHENS')
        _,_,v=self.step(offset=310,sequence=3,p=.77)
        self.assertEqual(v['early']['guidance'],'WATCH');self.assertEqual(v['final']['helper']['relation'],'WEAKENS')
        f=frame(offset=315,sequence=4,p=.7);f['brti']['value']=80000.
        _,_,v=self.e.process(f,f['captured_ts']+.01)
        self.assertEqual(v['early']['guidance'],'CAUTION');self.assertEqual(v['final']['helper']['relation'],'MIXED')
        self.assertEqual(v['origin'],e['origin'])
    def test_confirm_loss_flip_and_clearance_does_not_unlatch(self):
        _,_,e=self.step();_,_,v=self.step(offset=425,sequence=2,p=.95,ask=.72)
        self.assertTrue(v['final']['helper']['confirmed'])
        _,_,v=self.step(offset=430,sequence=3,p=.8,ask=.72)
        self.assertTrue(v['final']['helper']['material_deterioration']);self.assertEqual(v['early']['guidance'],'PROTECT')
        _,_,v=self.step(offset=435,sequence=4,p=.95,ask=.72,side='DOWN')
        self.assertEqual(v['final']['helper']['relation'],'FLIPPED');self.assertEqual(v['final']['early_origin_id'],e['origin']['origin_id'])
        _,_,v=self.step(offset=440,sequence=5,p=.96,ask=.73)
        self.assertTrue(v['final']['helper']['clearance']);self.assertEqual(v['early']['guidance'],'PROTECT')
        self.assertIsNone(v['exit_guidance']);self.assertFalse(v['final']['helper']['exit_authority'])
    def test_final_survives_helper_failure_without_fake_link(self):
        with patch.object(product,'reduce_signal',side_effect=ValueError('MANAGER_FAILURE')):
            _,_,v=self.step(offset=425,p=.95,ask=.72)
        self.assertEqual(v['status'],'UNAVAILABLE');self.assertEqual(v['final_status'],'AVAILABLE')
        self.assertTrue(v['final']['ready']);self.assertIsNone(v['final']['early_origin_id'])
    def test_early_price_uses_original_ask_later_bid(self):
        _,_,entry=self.step();r,_,v=self.step(offset=305,sequence=2,ask=.70)
        self.assertEqual(v['origin']['original_ask'],.35);self.assertAlmostEqual(v['executable_current_bid'],.69)
        self.assertEqual(r['later_bid']['side'],'UP');self.assertEqual(r['later_bid']['origin_id'],entry['origin']['origin_id'])
        self.assertAlmostEqual(v['movement_cents'],34)
    def test_late_context_has_no_automatic_exit_authority(self):
        for left,weak,expected in [(301,False,'HOLD'),(300,True,'CAUTION'),(180,False,'CAUTION')]:
            c=context('UP',left,btc=80002,brti=80001,target=80000,weakening=weak)
            self.assertEqual(c['state'],expected);self.assertFalse(c['exit_authority'])
    def test_flip_model_information_cannot_invoke_exit(self):
        self.step();_,_,v=self.step(offset=725,sequence=2,p=.99,side='DOWN')
        self.assertEqual(v['flip_risk_authority'],'MODEL_INFORMATION_ONLY');self.assertNotEqual(v['early']['guidance'],'EXIT')
    def test_nonfinite_current_information_fails_closed(self):
        f=frame();f['brti']['value']=float('nan')
        _,_,v=self.e.process(f,f['captured_ts']+.01)
        self.assertEqual(v['status'],'UNAVAILABLE');self.assertIsNone(v['origin'])

class EvidenceTests(unittest.TestCase):
    def record(self,t,**kw):return dict(kind='SCALP_OBSERVATION',published_ts=t,contract=TICKER,**kw)
    def test_quiet_and_entire_missing_contracts_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            j=Journal(Path(d)/'v81.sqlite3','v81');j.commit(self.record(OPEN+1),{});j.commit(self.record(OPEN+1801),{})
            rows=coverage_view(d,'v81')['contracts']
            self.assertEqual(len(rows),3);self.assertTrue(rows[1]['missing']);self.assertEqual(rows[1]['observations'],0)
            self.assertFalse(rows[1]['quiet']);self.assertTrue(rows[2]['quiet']);self.assertTrue(rows[2]['missing']);j.close()
    def test_atomic_record_and_state_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            j=Journal(Path(d)/'main.sqlite3','main');j.commit(self.record(OPEN+1),dict(v=1))
            j.db.executescript("CREATE TRIGGER reject_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'fail'); END;")
            with self.assertRaises(sqlite3.IntegrityError):j.commit(self.record(OPEN+2),dict(v=2))
            self.assertEqual(j.get('state'),dict(v=1));self.assertEqual(j.db.execute('SELECT observations FROM contracts').fetchone()[0],1);j.close()
    def test_authoritative_receipt_only_after_finalized(self):
        m=dict(ticker=TICKER,open_time=iso(OPEN),close_time=iso(OPEN+900),status='determined',result='yes')
        self.assertIsNone(receipt(TICKER,OPEN,dict(market=m),OPEN+901)['side'])
        m['status']='finalized';r=receipt(TICKER,OPEN,dict(market=m),OPEN+901)
        self.assertEqual(r['side'],'UP');self.assertEqual(r['status'],'AUTHORITATIVE');m['ticker']='OTHER'
        with self.assertRaises(ValueError):receipt(TICKER,OPEN,dict(market=m),OPEN+901)
    def test_bounded_lookup_records_final_result_and_not_decision(self):
        with tempfile.TemporaryDirectory() as d:
            j=Journal(Path(d)/'main.sqlite3','main');j.commit(self.record(OPEN+1),{})
            m=dict(ticker=TICKER,open_time=iso(OPEN),close_time=iso(OPEN+900),status='finalized',result='no')
            class Response:
                def raise_for_status(self):pass
                def json(self):return dict(market=m)
            calls=[];events=[]
            def get(url,**kwargs):calls.append((url,kwargs));return Response()
            def offer(v):events.append(v);return True
            reader=SettlementReader(d,'main',offer,get,clock=lambda:OPEN+1000);reader.once()
            self.assertEqual(len(calls),1);self.assertFalse(calls[0][1]['allow_redirects'])
            e=product.Directional();e.restore({});r,s,v=e.process(events[0],OPEN+1000);j.commit(r,s)
            self.assertIsNone(e.origin);self.assertEqual(coverage_view(d,'main')['contracts'][0]['settlement']['side'],'DOWN')
            reader.once();self.assertEqual(len(calls),1);j.close()
    def test_brti_closeout_is_not_settlement(self):
        e=product.Directional();e.restore({});r,_,_=e.process(dict(kind='BRTI_CLOSEOUT',contract=TICKER,settlement={'final60_side':'UP'}),OPEN+1000)
        self.assertNotIn('settlement',r);self.assertIn('brti_closeout',r)
    def test_event_size_bounded(self):
        with self.assertRaises(ValueError):packed({'x':'a'*65536})

class CausalityTests(unittest.TestCase):
    def enter(self):
        e=Scalp();e.restore({});e.process(state(ENTRY-1),ENTRY-.999);e.process(state(seq=2),ENTRY+.001);return e
    def test_future_lookback_cannot_confirm(self):
        e=Scalp();e.restore({});e.process(state(ENTRY-1),ENTRY-.999)
        f=state(seq=2);f['proposals']['UP']['history']['5']['observed_ts']=ENTRY+1
        _,_,v=e.process(f,ENTRY+.001);self.assertEqual(v['status'],'UNAVAILABLE');self.assertIsNone(e.origin)
    def test_sequence_rollback_cannot_change_exit(self):
        e=self.enter();_,_,v=e.process(state(ENTRY+1,.70,1),ENTRY+1.001)
        self.assertEqual(v['guidance'],'UNAVAILABLE');self.assertIsNone(e.terminal)
    def test_prefix_unchanged_by_later_path_or_settlement(self):
        e=self.enter();r,s,v=e.process(state(ENTRY+1,.50,3),ENTRY+1.001);frozen=json.dumps([r,s,v],sort_keys=True)
        e.process(state(ENTRY+2,.24,4),ENTRY+2.001)
        e.process({'kind':'SETTLEMENT','contract':TICKER,'settlement':{'side':'DOWN'}},OPEN+1000)
        self.assertEqual(json.dumps([r,s,v],sort_keys=True),frozen)
    def test_recovered_mechanisms_byte_identical(self):
        for name,sha in [('btc15_scalp_management_presentation_v1.py','45bd5b58a652957d0d415797264aac09bc4f45f8'),('btc15_recovered_exit_engine_v1.py','64cc18c')]:
            raw=Path(name).read_bytes();actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            self.assertTrue(actual.startswith(sha),name+': '+actual)
    def test_installer_uses_existing_cards_and_one_authority(self):
        from btc15_information_install_v1 import assemble
        with tempfile.TemporaryDirectory() as d:
            assemble(Path(d));html=(Path(d)/'BTC_Kalshi_App_Live_v13.html').read_text()
            self.assertNotIn('id="v81-inline-scalp-script"',html);self.assertEqual(html.count('id="scalpCard"'),1)
            self.assertIn('window.btc15RenderLadders()',html)
            js=Path('btc15_ladder_panel_v1.js').read_text()
            self.assertNotIn('document.body.appendChild',js);self.assertNotIn('Date.now()',js)
            self.assertIn('data.signal_only!==true||data.orders!==false',js)

class DashboardTests(unittest.TestCase):
    def test_rendered_guidance_and_expiry(self):
        import os,subprocess,shutil
        from btc15_information_install_v1 import assemble
        p=product.Directional();p.restore({});p.process(frame(),ENTRY+.001)
        _,_,m=p.process(frame(offset=302,sequence=2,p=.85,ask=.69),ENTRY+2.001)
        e=Scalp();e.restore({})
        for at,bid,seq in [(ENTRY-1,.34,1),(ENTRY,.34,2),(ENTRY+1,.72,3),(ENTRY+2,.68,4)]:
            _,_,sc=e.process(state(at,bid,seq),at+.001)
        for x in [m,sc]:x.update(served_ts=ENTRY+2.001,journal={'sequence':4})
        with tempfile.TemporaryDirectory() as d:
            assemble(Path(d));fixture=Path(d)/'fixture.json';fixture.write_text(json.dumps(dict(main=m,scalp=sc)))
            node=os.getenv('CODEX_PRIMARY_RUNTIME_NODE') or shutil.which('node')
            self.assertIsNotNone(node,'Node required for the dashboard contract gate')
            result=subprocess.run([node,'test_btc15_ladder_ui_v2.cjs',str(fixture),str(Path(d)/'BTC_Kalshi_App_Live_v13.html')],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


class NativeDetectorTests(unittest.TestCase):
    def test_real_v81_gate_and_feature_functions(self):
        import ast
        from collections import deque
        ns={'hist':deque()}
        constants={'BTC5_MIN','BTC15_MIN','MAX_ASK5','V4_BTC5','V4_BTC15','V4_BRTI5','V4_MIN_ACCEL','V4_MAX_ASK5','V4_MAX_ASK15','V4_MIN_LEFT','V4_MIN_ASK','V5_BTC30_FLOOR','V5_BRTI15_FLOOR','MAX_ASK','CORE_FLOORS','SURGE_FLOORS'}
        for name,functions in [('scalp_lead_shadow_v5.py',{'ago','d','features'}),('scalp_lead_unified_v8.py',{'_fresh','_floor_ratio','evidence_route'}),('v81_30_45_live_feed.py',{'quality_30_45'})]:
            tree=ast.parse(Path(name).read_text());nodes=[]
            for node in tree.body:
                if isinstance(node,ast.FunctionDef) and node.name in functions:nodes.append(node)
                elif isinstance(node,ast.Assign) and all(isinstance(t,ast.Name) and t.id in constants for t in node.targets):nodes.append(node)
            exec(compile(ast.Module(body=nodes,type_ignores=[]),name,'exec'),ns)
        for ago,btc,brti in [(30,79970,79980),(15,79975,79995),(5,79980,79985)]:
            r=state(ENTRY-ago)['row'];r.update(btc=btc,brti=brti);ns['hist'].append(r)
        row=state()['row'];row.update(btc=80000,brti=80000)
        f=ns['features'](row,'UP');self.assertEqual(ns['quality_30_45'](row,'UP',f),(True,'CORE'))
        weak=dict(f,btc15=21.);self.assertEqual(ns['quality_30_45'](row,'UP',weak),(False,None))
        row['up_ask']=.46;self.assertEqual(ns['quality_30_45'](row,'UP',f),(False,None))
    def test_scalp_worker_commits_exit_before_publication(self):
        from btc15_ladder_journal_v1 import Worker,view
        with tempfile.TemporaryDirectory() as d:
            clock=[ENTRY-1+.001];w=Worker(d,'v81',Scalp(),clock=lambda:clock[0])
            for at,bid,seq in [(ENTRY-1,.34,1),(ENTRY,.34,2),(ENTRY+1,.72,3),(ENTRY+2,.68,4)]:
                clock[0]=at+.001;self.assertTrue(w.offer(state(at,bid,seq)));w.queue.join();self.assertIsNone(w.failed)
            v=view(d,'v81',clock[0]);self.assertEqual(v['guidance'],'EXIT');self.assertEqual(v['journal']['sequence'],4)
            with sqlite3.connect(Path(d)/'v81.sqlite3') as db:
                saved=json.loads(db.execute("SELECT v FROM meta WHERE k='state'").fetchone()[0])
                self.assertEqual(saved['terminal']['executable_exit_bid'],.68)
            w.queue.put(None);w.thread.join(2)

if __name__=='__main__':unittest.main()
