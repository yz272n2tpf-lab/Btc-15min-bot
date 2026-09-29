"""Exact recovered V8.1 producer OFF/ON tests with injected qualified inputs.

These are engineering fixtures, not new prospective V8.1 performance results.
No producer top-level code, server, credential loader or source HTTP is executed.
"""
import ast
from collections import defaultdict,deque
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
import math
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import unittest

from sprint_evidence.passive_capture import Producer,Identity,digest
from sprint_evidence.v81_capture import V81Capture,instrument,SOURCE_SHA256,INPUT_SHA256,ENGINE_SHA256,DIRECT_SOURCE_PINS
from test_sprint_capture import MemorySocket
from test_btc15_external_evidence_admission_v1 import KEY

ROOT=Path(__file__).parent/'sprint_evidence/references'
SOURCE=(ROOT/'v81_30_45_live_feed.py').read_bytes()
INPUT=(ROOT/'btc15_v81_qualified_inputs_v1.py').read_bytes()
ENGINE=(ROOT/'scalp_lead_unified_v8.py').read_bytes()
FEATURES=(ROOT/'scalp_lead_shadow_v5.py').read_bytes()
AT=1801242000.0 # exact 15-minute boundary is rounded below
OPEN=int(AT//900)*900
AT=OPEN+300
TICKER='KXBTC15M-SYNTHETIC'
IDENTITY=Identity('synthetic-v81','synthetic-build',SOURCE_SHA256,'synthetic-run','unqualified-clock','synthetic-boot')


def row(at=AT,*,bid=.34,ask=.35,side='UP',ticker=TICKER,brti_age=1):
    opened=int(at//900)*900
    q=dict(ticker=ticker,epoch='quote-epoch',market_id='market',sid=1,sequence=int(at*1000),
           source_ts_ms=int((at-.1)*1000),validated_at_ms=int(at*1000),transport='timestamped_contiguous_ws',
           up_bid=bid,up_ask=ask,down_bid=round(1-ask,6),down_ask=round(1-bid,6))
    if side=='DOWN':q.update(down_bid=bid,down_ask=ask,up_bid=round(1-ask,6),up_ask=round(1-bid,6))
    p=dict(schema='V81_TIMESTAMPED_INPUTS_V1',ticker=ticker,target=100000,open_ts=opened,close_ts=opened+900,
           quote=q,brti=dict(source_ts_ms=int((at-brti_age)*1000),owner_epoch='brti-epoch',sequence=1,
                           status='PRIMARY_OK',clean_for_qualification=True,value=100020),
           btc_source_utc='SYNTHETIC_LABEL',signal_only=True,orders=False)
    return dict(ts=at,ticker=ticker,left=opened+900-at,target=100000,btc=100030,brti=100020,input_provenance=p,
                **{k:q[k] for k in ('up_bid','up_ask','down_bid','down_ask')})


class Clock:
    def __init__(self):self.at=AT;self.stop=False
    gmtime=staticmethod(time.gmtime)
    strftime=staticmethod(time.strftime)
    def time(self):return self.at
    def sleep(self,_):raise StopIteration('single original loop iteration completed')


def namespace(enabled):
    clock=Clock();sock=MemorySocket();producer=Producer('unused',IDENTITY,KEY,sock=sock)
    ns=dict(__name__='v81-test',time=clock,math=math,json=json,threading=threading,
            defaultdict=defaultdict,deque=deque,_sprint_v81=V81Capture(producer),
            print=lambda *a,**k:None,KEEP=240,POLL=1,hist=deque(),
            _qualified_inputs=SimpleNamespace(last_ticker=TICKER))
    # Pure actual qualification functions/constants; omit QuoteProvider and
    # QualifiedInputs classes and their imports (those own sockets/network).
    input_tree=ast.parse(INPUT)
    nodes=[n for n in input_tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef,ast.Assign)) and
           (not isinstance(n,ast.ClassDef) or n.name=='InputUnavailable')]
    ns.update(datetime=__import__('datetime').datetime,timezone=__import__('datetime').timezone,MAX_AGE=6.0)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'exact-qualified-inputs','exec'),ns)
    feature_tree=ast.parse(FEATURES)
    nodes=[n for n in feature_tree.body if isinstance(n,ast.FunctionDef) and n.name in ('ago','d','features')]
    for n in feature_tree.body:
        if isinstance(n,ast.Assign):
            try:v=ast.literal_eval(n.value)
            except (ValueError,TypeError):continue
            if type(v) in (int,float):nodes.append(n)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'exact-v5-features','exec'),ns)
    engine_tree=ast.parse(ENGINE)
    names={'CORE_FLOORS','SURGE_FLOORS'}
    nodes=[n for n in engine_tree.body if (isinstance(n,ast.FunctionDef) and n.name in ('_fresh','_floor_ratio','evidence_route'))
           or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets))]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'exact-evidence-route','exec'),ns)
    tree=instrument(SOURCE,enabled=enabled)
    names={'STATE','STATE_LOCK','confirm','last_signal','active'}
    nodes=[n for n in tree.body if (isinstance(n,ast.FunctionDef) and n.name not in ('main','self_test'))
           or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets))]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'exact-v81-publisher-loop','exec'),ns)
    return ns,clock,producer,sock


def core():return dict(btc5=20.,btc15=25.,brti5=15.,brti15=5.,accel=10.,btc30=0.,ask5=0.,ask15=0.,v4=True,structure_ok=True)


class V81Controls(unittest.TestCase):
    def test_exact_source_pins_and_off_ast_identity(self):
        for name,expected in DIRECT_SOURCE_PINS.items():self.assertEqual(digest((ROOT/name).read_bytes()),expected)
        self.assertEqual(digest(SOURCE),SOURCE_SHA256);self.assertEqual(digest(INPUT),INPUT_SHA256);self.assertEqual(digest(ENGINE),ENGINE_SHA256)
        self.assertEqual(ast.dump(instrument(SOURCE,enabled=False)),ast.dump(ast.parse(SOURCE)))
        class Strip(ast.NodeTransformer):
            def visit_Expr(self,node):
                c=node.value
                if isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and isinstance(c.func.value,ast.Name) and c.func.value.id=='_sprint_v81':return None
                return self.generic_visit(node)
        self.assertEqual(ast.dump(Strip().visit(instrument(SOURCE))),ast.dump(ast.parse(SOURCE)))
        with self.assertRaisesRegex(ValueError,'V81_SOURCE_CHANGED'):instrument(SOURCE+b'# change')

    def test_publisher_up_down_origin_current_quote_and_protection_off_on(self):
        for side in ('UP','DOWN'):
            off,oc,_,_=namespace(False);on,clock,p,sock=namespace(True)
            original=row(side=side);origin=None
            for dt,bid,status in [(0,.34,'WATCH'),(1,.405,'ACTIONABLE'),(2,.46,'ACTIONABLE_EXPANSION'),(3,.57,'PROTECT')]:
                current=row(AT+dt,bid=bid,ask=bid+.01,side=side) if dt else original
                clock.at=oc.at=AT+dt
                args=(current,side,'CORE',.35,bid,AT)
                kw=dict(entry_seconds_left=600,entry_provenance=original['input_provenance'])
                off['publish_signal'](*args,**kw);on['publish_signal'](*args,**kw)
                self.assertEqual(on['STATE'],off['STATE']);self.assertEqual(on['STATE']['status'],status)
                e=json.loads(sock.packets[-1])['event']['body']['emission']
                self.assertEqual(e['original_executable_ask'],.35);self.assertEqual(e['published_entry_price'],.35)
                self.assertEqual(e['current_row'],current);self.assertEqual(e['state']['status'],status)
                if origin is None:origin=e['evidence_origin_id']
                self.assertEqual(e['evidence_origin_id'],origin)
                self.assertIsNone(e['upstream_native_origin_id']);self.assertIsNone(e['manual_fill']);self.assertIsNone(e['completed_http_delivery_utc'])
            self.assertEqual(p.sequence,4)

    def test_quote_or_brti_unqualified_publishes_no_new_signal(self):
        on,clock,p,_=namespace(True)
        for age in (5.001,6):
            bad=row(brti_age=age)
            with self.assertRaises(on['InputUnavailable']):on['publish_signal'](bad,'UP','CORE',.35,.34,AT)
        self.assertEqual(p.sequence,0)
        # Exact boundary remains unchanged; no new tolerance.
        okay=row(brti_age=5);on['publish_signal'](okay,'UP','CORE',.35,.34,AT);self.assertEqual(p.sequence,1)

    def test_real_loop_confirmation_source_wait_recovery_and_rollover_off_on(self):
        off,oc,_,_=namespace(False);on,clock,p,sock=namespace(True)
        frames=[row(),row(AT+1),None,row(AT+3,bid=.42,ask=.43),row(OPEN+901,ticker='KXBTC15M-NEXT')]
        for ns,cl in ((off,oc),(on,clock)):
            position=[0]
            def snap():
                item=frames[position[0]]
                if item is None:raise ns['InputUnavailable']('SYNTHETIC_SOURCE_WAIT')
                return deepcopy(item)
            ns['snap']=snap
            # Real historical feature functions receive only already-observed
            # fixture rows; detector thresholds/routes are not replaced.
            for offset,btc,brti in [(-30,99970,99970),(-15,99990,99990),(-5,100000,100000)]:
                old=row(AT+offset);old.update(btc=btc,brti=brti);old['input_provenance']['brti']['value']=brti
                ns['hist'].append(old)
            # Use one actual invocation of loop across all frames. time.sleep
            # advances fixture input; it never touches strategy counters.
            def advance(_):
                position[0]+=1
                if position[0]>=len(frames):raise StopIteration
                cl.at=AT+position[0] if frames[position[0]] is None else frames[position[0]]['ts']
            cl.sleep=advance
            with self.assertRaises(StopIteration):ns['loop']()
        self.assertEqual(on['STATE'],off['STATE']);self.assertEqual(on['active'],off['active'])
        self.assertEqual(dict(on['last_signal']),dict(off['last_signal']));self.assertEqual(dict(on['confirm']),dict(off['confirm']))
        emissions=[json.loads(x)['event']['body']['emission'] for x in sock.packets]
        waits=[e for e in emissions if e['event_type']=='EVALUATION' and e['phase']=='SOURCE_WAIT']
        self.assertEqual(len(waits),1);self.assertTrue(waits[0]['active']);self.assertIsNone(waits[0]['row'])
        completed=[e for e in emissions if e['event_type']=='EVALUATION' and e['phase']=='COMPLETE']
        self.assertEqual(len(completed),4)
        self.assertEqual(completed[1]['diagnostics'][0]['confirm_count'],2)
        self.assertIsNone(completed[-1]['active']) # rollover clears old lifecycle; no EXIT fabricated
        self.assertTrue(all(e.get('automatic_exit') is None for e in completed))

    def test_wait_keeps_last_signal_event_and_does_not_invent_exit(self):
        ns,clock,p,sock=namespace(True);r=row();ns['publish_signal'](r,'UP','CORE',.35,.34,AT)
        before=deepcopy(ns['STATE']['last_signal_event']);ns['publish_wait'](TICKER,reason='QUOTE_GAP')
        e=json.loads(sock.packets[-1])['event']['body']['emission']
        self.assertEqual(e['state']['last_signal_event'],before);self.assertEqual(e['phase'],'WAIT')
        self.assertIsNone(e['evidence_origin_id']);self.assertIsNone(e['original_signal_event'])
        self.assertIsNone(e['published_entry_price']);self.assertEqual(e['state']['status'],'WAIT')

    def test_immutable_detach_first_later_quote_is_not_same_quote(self):
        ns,clock,p,sock=namespace(True);r=row();ns['publish_signal'](r,'UP','CORE',.35,.34,AT)
        publication=json.loads(sock.packets[-1])['event']['body']['emission']
        ns['active']={'ticker':TICKER,'side':'UP','entry':.35,'ts':AT}
        ns['_sprint_v81'].evaluation('COMPLETE',{'row':r,'diagnostics':[]},ns)
        same=json.loads(sock.packets[-1])['event']['body']['emission']
        later=row(AT+1,bid=.4,ask=.41);ns['_sprint_v81'].evaluation('COMPLETE',{'row':later,'diagnostics':[]},ns)
        subsequent=json.loads(sock.packets[-1])['event']['body']['emission']
        origin_source=publication['original_signal_event']['entry_provenance']['quote']['source_ts_ms']
        self.assertEqual(same['row']['input_provenance']['quote']['source_ts_ms'],origin_source)
        self.assertGreater(subsequent['row']['input_provenance']['quote']['source_ts_ms'],origin_source)
        r['up_ask']=.99;self.assertEqual(publication['current_row']['up_ask'],.35)
        self.assertNotIn('fill',subsequent)

    def test_capture_failure_does_not_change_publisher(self):
        class Lost:
            def sendto(self,*args):raise BlockingIOError('consumer backlog')
            def close(self):pass
        off,oc,_,_=namespace(False);on,clock,p,_=namespace(True);p.sock=Lost()
        r=row();off['publish_signal'](r,'UP','CORE',.35,.34,AT);on['publish_signal'](r,'UP','CORE',.35,.34,AT)
        self.assertEqual(on['STATE'],off['STATE']);self.assertEqual(p.dropped,1)

if __name__=='__main__':unittest.main()
