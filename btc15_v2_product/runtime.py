"""Frozen native action clocks; independent read-only source projections."""
import ast
from copy import deepcopy
import json
import os
from pathlib import Path
import threading
import time
from .admin import Admin
from .bootstrap import Pool,Preparation
from .journal import install,public_view

CALLS={'get_active_market','extract_target','get_btc_spot','consume_ws_quotes',
       '_retry_brti_closeouts','_brti_contract_snapshot','_log_brti_parity',
       '_live_fair_shadow','_fair_frame_at_cut','_fair_build_snapshot',
       'record_model_input','log_early_conf_shadow','log_unified_subminute',
       'update_pending','_update_true_scalp_pending','_update_profit_shadow',
       '_maybe_true_scalp_signal','maybe_create_event','save_state',
       '_true_scalp_probability','_true_scalp_live_features',
       '_btc15_information_offer','_btc15_cohort_offer','_btc15_cohort_closeout_offer',
       '_btc15_ladder_offer','snap','features','quality_30_45','journal_offer'}


def instrument(tree,lane):
    tree=deepcopy(tree)
    class Calls(ast.NodeTransformer):
        def visit_Call(self,n):
            self.generic_visit(n)
            name=n.func.id if isinstance(n.func,ast.Name) and n.func.id in CALLS else None
            if isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='time' and n.func.attr=='sleep':name='native_sleep'
            if isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id in ('_fair_rf','_fair_sigmoid','_true_scalp_model') and n.func.attr=='predict_proba':name=ast.unparse(n.func)
            if name:
                return ast.copy_location(ast.Call(func=ast.Attribute(value=ast.Name(id='_v2_admin',ctx=ast.Load()),attr='call',ctx=ast.Load()),
                    args=[ast.Constant(name),n.func,*n.args],keywords=n.keywords),n)
            return n
    tree=Calls().visit(tree)
    if lane=='main':
        loops=[n for n in tree.body if isinstance(n,ast.While) and isinstance(n.test,ast.Name) and n.test.id=='running']
        if len(loops)!=1:raise ValueError('PINNED_MAIN_LOOP')
        loop=loops[0];tree.body.insert(tree.body.index(loop),ast.parse('_v2_prepare(globals())').body[0])
    else:
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='loop')
        loop=next(n for n in fn.body if isinstance(n,ast.While))
        # Set up preparation after the frozen QualifiedInputs object exists.
        seam=next(i for i,n in enumerate(tree.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_qualified_inputs' for t in n.targets))
        tree.body.insert(seam+1,ast.parse('_v2_prepare(globals())').body[0])
    blocks=[n for n in loop.body if isinstance(n,ast.Try)]
    if len(blocks)!=1:raise ValueError('PINNED_NATIVE_TRY')
    block=blocks[0]
    for handler in block.handlers:
        if handler.name:handler.body.insert(0,ast.parse('_v2_admin.exception('+handler.name+')').body[0])
    loop.body.insert(loop.body.index(block),ast.parse('_v2_admin.begin()').body[0])
    block.finalbody.append(ast.parse('_v2_admin.finish(globals())').body[0])
    return ast.fix_missing_locations(tree)


def prepare_main(ns,pool):
    from .fair_readiness import install as install_fair_readiness
    install_fair_readiness(ns)
    original=ns['get_active_market']
    preparation=Preparation(ns['kalshi_get'],ns['extract_target'],pool)
    # Move the original optional unopened-list observation off the action path.
    # It never selected an active ticker; the exact staged handoff is above.
    ns['rollover_canary'].observe=lambda *a,**k:None
    ns['get_active_market']=lambda:preparation.select(original)
    import btc15_kalshi_quote_provenance_v1 as quotes
    quotes._provider=pool
    preparation.start();return preparation


def prepare_v81(ns,pool):
    owner=ns['_qualified_inputs'];original=owner.market
    admin=ns['_v2_admin'];original_get=owner.get;original_brti=owner.brti_read
    owner.get=lambda *a,**k:admin.call('coinbase_http',original_get,*a,**k)
    owner.brti_read=lambda:admin.call('shared_brti_read',original_brti)
    def get(path,params=None):
        response=ns['requests'].get(ns['MARKET']+path,headers=ns['hdr']('GET',path),params=params,timeout=7)
        response.raise_for_status();return response.json()
    preparation=Preparation(get,owner.target,pool)
    owner.market=lambda:admin.call('official_market_selection',preparation.select,original)
    owner.provider=pool
    preparation.start();return preparation


def native_main():
    import hashlib
    import btc15_information_native_offpath_candidate as native
    from .quote_view import QuoteProjection
    root=Path(os.environ['BTC15_LADDER_DATA_ROOT'])
    admin=Admin(root,'main');install(admin)
    from .directional import start,offer
    raw=native.BOT.read_bytes()
    if hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()!=native.PR36_BLOB:raise ValueError('FROZEN_NATIVE_BYTES')
    pool=Pool();export=native.NativeExport(provider_reader=lambda:pool.current)
    projection=QuoteProjection(pool)
    from .revalidation import InputProjection
    revalidation=InputProjection(export,projection)
    server=native.server_for(export,8766)
    original_get=server.RequestHandlerClass.do_GET
    def do_GET(handler):
        try:
            if handler.path=='/revalidation-input':
                try:
                    value=revalidation.capture();code=200
                except Exception:
                    value=dict(status='UNAVAILABLE');code=503
                raw=json.dumps(value,allow_nan=False,separators=(',',':')).encode()
                handler.send_response(code);handler.send_header('Content-Type','application/json')
                handler.send_header('Cache-Control','no-store');handler.send_header('Content-Length',str(len(raw)))
                handler.end_headers();handler.wfile.write(raw);return
            if handler.path=='/executable-quote':
                raw=json.dumps(projection.capture(),allow_nan=False,separators=(',',':')).encode()
                handler.send_response(200);handler.send_header('Content-Type','application/json')
                handler.send_header('Cache-Control','no-store');handler.send_header('Content-Length',str(len(raw)))
                handler.end_headers();handler.wfile.write(raw);return
            return original_get(handler)
        except (BrokenPipeError,ConnectionResetError,TimeoutError):return
    server.RequestHandlerClass.do_GET=do_GET
    ns=dict(__name__='__main__',__file__=str(native.BOT),_v2_admin=admin,
        _v2_prepare=lambda ns:prepare_main(ns,pool),_btc15_information_offer=export.offer,
        _btc15_cohort_offer=native.cohort_offer,_btc15_cohort_closeout_offer=native.cohort_closeout_offer,
        _btc15_ladder_offer=offer)
    start()
    threading.Thread(target=server.serve_forever,daemon=True,name='native-small-projections').start()
    try:exec(compile(instrument(native.instrument(ast.parse(raw)),'main'),str(native.BOT),'exec'),ns)
    finally:server.shutdown();server.server_close()


def v81_main(root):
    admin=Admin(os.environ['BTC15_LADDER_DATA_ROOT'],'v81');install(admin)
    import btc15_ladder_journal_v1 as journal
    journal.view=public_view
    pool=Pool()
    path=Path(root)/'btc15_v2_product/scalp_feed.py'
    ns=dict(__name__='__main__',__file__=str(path),_v2_admin=admin,_v2_prepare=lambda ns:prepare_v81(ns,pool))
    exec(compile(instrument(ast.parse(path.read_bytes()),'v81'),str(path),'exec'),ns)
