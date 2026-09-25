"""OFFLINE ONLY: native external effects adapter for installed-topology stress.

Executes the recovered full PR36 loop/model; sources are synthetic January 2020.
Never used by production installation. The installed supervisors/telemetry/UI
and actual information worker remain real processes. No upstream credentials.
"""
import ast
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import threading
import time

import numpy as np
import pandas as pd
from completion_audit.isolated_decision_v2 import FrozenRuntime
from test_btc15_isolated_decision_v2 import fixture, OPEN
from test_btc15_information_v1 import provider
from btc15_information_native_v1 import NativeExport, instrument, server_for


def main():
    out=Path(os.environ['BTC15_TEST_OUTPUT']);enabled=os.getenv('BTC15_TEST_INFORMATION')=='1'
    count=int(os.getenv('BTC15_TEST_PROOF_EVENTS','2'))
    index=pd.date_range(pd.Timestamp(OPEN-35*86400,unit='s',tz='UTC'),periods=35*1440+16,freq='min')
    values=100000+np.arange(len(index))%17
    history=pd.DataFrame(dict(Open=values,High=values+2,Low=values-2,Close=values,Volume=1.,source_utc=index),index=index)
    runtime=FrozenRuntime(history)
    current=[None];source_lock=threading.Lock();stop=threading.Event()
    export=NativeExport(provider_reader=lambda:current[0])
    if enabled:
        runtime.ns['_btc15_information_offer']=export.offer
        tree=instrument(runtime.tree)
        loop=next(n for n in tree.body if isinstance(n,ast.While) and isinstance(n.test,ast.Name) and n.test.id=='running')
        runtime.loop=compile(ast.Module(body=[loop],type_ignores=[]),'<installed-native-offline-effects>','exec')
        server=server_for(export,8766)
        threading.Thread(target=server.serve_forever,daemon=True).start()
    timings=[];error=[]
    def inputs(at):
        f=fixture(at-OPEN,ask=.31 if int(at)%2 else .61,brti_delay=2.486)
        p=f['proof'];first=deepcopy(p['events'][0]);delta=deepcopy(p['events'][1])
        first['seq']=int(at*10000);events=[first]
        for i in range(1,count):
            item=deepcopy(delta);item['seq']=first['seq']+i
            item['msg']['delta_fp']='0.00';events.append(item)
        p['events']=events;p['identity']=[p['identity'][0],first['sid'],events[-1]['seq'],p['identity'][3]]
        return f
    def sources():
        last=None
        while not stop.is_set():
            at=int(time.time())
            if at!=last:
                try:
                    f=inputs(at);p=provider(f)
                    with source_lock:
                        current[0]=p
                        runtime.ns['_brti_delivery'].accept(*f['brti_receipts'][0])
                    last=at
                except Exception as e:error.append(repr(e))
            stop.wait(.02)
    threading.Thread(target=sources,daemon=True).start()
    signal.signal(signal.SIGTERM,lambda *_:stop.set());signal.signal(signal.SIGINT,lambda *_:stop.set())
    start=time.monotonic();due=start
    try:
        while not stop.is_set():
            delay=max(0,due-time.monotonic())
            if stop.wait(delay):break
            began=time.monotonic();at=int(time.time()*1000)/1000
            f=inputs(at)
            with source_lock:current[0]=provider(f)
            before=time.monotonic();runtime.step(f);end=time.monotonic()
            timings.append(dict(decision=at,lateness_s=began-due,iteration_s=end-before,
                                elapsed_s=end-start,anchor_bytes=len(export.anchor[0]) if export.anchor else 0))
            report=dict(pid=os.getpid(),information=enabled,proof_events=count,
                        proof_bytes=len(json.dumps(f['proof'])),history_rows=len(history),ticks=timings,errors=error,
                        native_records=len(runtime.records),native_inputs=len(runtime.inputs),messages=runtime.messages)
            temp=out.with_suffix('.tmp');temp.write_text(json.dumps(report));temp.replace(out)
            due+=5
    finally:
        stop.set()
        if enabled:server.shutdown();server.server_close()


if __name__=='__main__':main()
