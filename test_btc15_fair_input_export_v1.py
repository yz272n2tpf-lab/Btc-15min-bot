import ast
import gzip
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
from urllib.request import urlopen
from btc15_fair_input_export_v1 import NAME,FEATURES,MAX_BYTES,response,install_route


class FairInputExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.row=dict(schema='BTC15_FAIR_INPUT_V1',ticker='KXBTC15M-26SEP240800-00',target=100.,
            decision_utc='2026-09-24T12:00:02Z',btc_source_utc='2026-09-24T12:00:00Z',
            btc_observed_utc='2026-09-24T12:00:01Z',btc_price=101.,features=dict.fromkeys(FEATURES,1.),
            feature_order=FEATURES,weights_sha256='a'*64,artifact_sha256='b'*64,signal_only=True,orders=False)
        self.raw=(json.dumps(self.row)+'\n').encode();(self.root/NAME).write_bytes(self.raw)

    def identity(self):return json.loads(response('/research/fair-input-manifest',self.root)[3])['identity']
    def export(self,extra=''):return response('/research/fair-input-export?identity='+self.identity()+extra,self.root)

    def test_bounded_export_retains_exact_clocks_bytes_and_hash(self):
        status,_,h,b=self.export();self.assertEqual(status,200);self.assertEqual(b,self.raw)
        self.assertEqual(h['X-Range-SHA256'],hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(int(h['X-Range-Next-Offset']),len(self.raw))

    def test_append_preserves_identity_and_incremental_offset(self):
        identity=self.identity()
        with (self.root/NAME).open('ab') as f:f.write(self.raw)
        self.assertEqual(self.identity(),identity)
        self.assertEqual(self.export('&offset='+str(len(self.raw)))[3],self.raw)

    def test_partial_tail_is_not_exported_or_silently_skipped(self):
        with (self.root/NAME).open('ab') as f:f.write(b'{"unfinished":')
        r=self.export();self.assertEqual(r[3],self.raw)
        self.assertGreater(int(r[2]['X-Journal-Snapshot-Bytes']),int(r[2]['X-Range-Next-Offset']))

    def test_bounds_and_line_boundary_enforced(self):
        for extra in ['&offset=1','&offset=-1','&limit=0','&limit='+str(MAX_BYTES+1),'&offset=999999']:
            self.assertEqual(self.export(extra)[0],400)

    def test_no_arbitrary_paths_duplicate_params_or_secret_fields(self):
        self.assertEqual(self.export('&path=/etc/passwd')[0],400)
        self.assertEqual(self.export('&offset=0&offset=0')[0],400)
        with (self.root/NAME).open('ab') as f:f.write(json.dumps(dict(self.row,private_key='not-a-real-secret')).encode()+b'\n')
        result=self.export();self.assertEqual(result[0],400);self.assertNotIn(b'not-a-real-secret',result[3])

    def test_outcome_schema_and_future_receipt_are_rejected(self):
        for field,value in [('orders',True),('btc_observed_utc','2026-09-24T12:00:03Z')]:
            (self.root/NAME).write_text(json.dumps(dict(self.row,**{field:value}))+'\n')
            self.assertEqual(response('/research/fair-input-manifest',self.root)[0],400)

    def test_duplicate_fields_cannot_hide_unvalidated_raw_values(self):
        raw=b'{"ticker":"unvalidated-private-value",'+self.raw[1:]
        (self.root/NAME).write_bytes(raw)
        status,_,_,body=response('/research/fair-input-manifest',self.root)
        self.assertEqual(status,400);self.assertNotIn(b'unvalidated-private-value',body)

    def test_missing_or_replaced_identity_fails_closed(self):
        self.assertEqual(response('/research/fair-input-export?identity=old',self.root)[0],409)
        self.assertEqual(response('/research/fair-input-export',self.root)[0],409)

    def test_other_routes_unaffected(self):
        for route in ['/health','/dashboard_state.json','/','/research/fair-input-manifest/../other']:
            self.assertIsNone(response(route,self.root))

    def test_server_hook_is_idempotent_and_packaged_server_compiles(self):
        p=ast.parse(Path('BTC15_INSTALL_LIVE_DASHBOARD_V13.py').read_text())
        payload=next(ast.literal_eval(n.value) for n in p.body if isinstance(n,ast.Assign) and
                     any(isinstance(t,ast.Name) and t.id=='PAYLOADS' for t in n.targets))
        server=self.root/'BTC15_DASHBOARD_LIVE_SERVER_V1.py'
        server.write_bytes(gzip.decompress(base64.b64decode(payload[server.name])))
        install_route(self.root);one=server.read_text();install_route(self.root)
        self.assertEqual(server.read_text(),one);compile(one,str(server),'exec')
        self.assertEqual(one.count('BTC15_FAIR_INPUT_EXPORT_ROUTE_V1'),1)

    def test_http_routes_export_verified_range_and_keep_existing_dashboard(self):
        p=ast.parse(Path('BTC15_INSTALL_LIVE_DASHBOARD_V13.py').read_text())
        payload=next(ast.literal_eval(n.value) for n in p.body if isinstance(n,ast.Assign) and
                     any(isinstance(t,ast.Name) and t.id=='PAYLOADS' for t in n.targets))
        server_file=self.root/'BTC15_DASHBOARD_LIVE_SERVER_V1.py'
        server_file.write_bytes(gzip.decompress(base64.b64decode(payload[server_file.name])))
        install_route(self.root)
        stub=types.ModuleType('BTC15_DASHBOARD_STATE_V2');stub.build_state=lambda:dict(sentinel='existing')
        namespace=dict(__name__='export_integration_test',__file__=str(server_file))
        with patch.dict('sys.modules',{'BTC15_DASHBOARD_STATE_V2':stub}):exec(server_file.read_text(),namespace)
        http=namespace['ThreadingHTTPServer'](('127.0.0.1',0),namespace['Handler'])
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            base='http://127.0.0.1:'+str(http.server_port)
            with patch('btc15_fair_input_export_v1._btc15_data_root',return_value=self.root):
                with urlopen(base+'/research/fair-input-manifest',timeout=2) as r:identity=json.load(r)['identity']
                with urlopen(base+'/research/fair-input-export?identity='+identity,timeout=2) as r:
                    self.assertEqual(r.read(),self.raw);self.assertEqual(r.headers['X-Range-SHA256'],hashlib.sha256(self.raw).hexdigest())
                with urlopen(base+'/dashboard_state.json',timeout=2) as r:self.assertEqual(json.load(r),dict(sentinel='existing'))
                with urlopen(base+'/health',timeout=2) as r:self.assertTrue(json.load(r)['read_only'])
        finally:http.shutdown();http.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
