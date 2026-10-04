"""D04 follow-up: exact frozen legacy shadow training source and prediction stage.

Fits ONLY the original frozen startup model offline; no artifact is promoted.
Measures identical fitted object under observed default and one-thread contexts.
"""
import ast
import csv
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_info,threadpool_limits
from completion_audit.isolated_decision_v2 import FrozenRuntime
from test_btc15_isolated_decision_v2 import completed,fixture

def run():
    source=Path('bot_two_output_build_v4_13_profit_protection_shadow.py')
    tree=ast.parse(source.read_text());runtime=FrozenRuntime(completed());ns=runtime.ns
    ns.update(csv=csv,hashlib=hashlib,HistGradientBoostingClassifier=HistGradientBoostingClassifier,Path=Path,__file__=str(source.resolve()))
    names={'_truthy','_git_blob_sha','_load_true_scalp_training_events','_train_true_scalp_candidate'}
    nodes=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in names]
    assigns=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('TRUE_SCALP_TRAIN_CUTOFF','TRUE_SCALP_TRAIN_EVENT_LOG') for t in n.targets)]
    exec(compile(ast.Module(body=assigns+nodes,type_ignores=[]),str(source),'exec'),ns)
    start=time.perf_counter()
    with threadpool_limits(limits=1):ns['_train_true_scalp_candidate']()
    if not ns['_true_scalp_ready']:raise AssertionError(runtime.messages)
    training_ms=(time.perf_counter()-start)*1000
    print(json.dumps(dict(stage='frozen_shadow_fit_complete',training_ms=training_ms,messages=runtime.messages,threadpools=threadpool_info())),flush=True)
    # Populate real frozen features from a native iteration with the same model.
    with threadpool_limits(limits=1):runtime.step(fixture(300))
    samples=[]
    for workers in (None,1,None,1):
        from contextlib import nullcontext
        with threadpool_limits(limits=workers) if workers else nullcontext():
            start=time.perf_counter();prob,features=ns['_true_scalp_probability']('UP',ns['snap']);duration=(time.perf_counter()-start)*1000
        row=dict(workers='DEFAULT' if workers is None else workers,elapsed_ms=duration,probability=prob)
        samples.append(row);print(json.dumps(row),flush=True)
    loops=[]
    for i in range(10):
        start=time.perf_counter();output=runtime.step(fixture(305+i*5));loops.append((time.perf_counter()-start)*1000)
        if any('WARNING' in msg for msg in output['messages']):raise AssertionError(output['messages'])
    result=dict(schema='BTC15_D04_LEGACY_SHADOW_TIMING_V1',evidence_class='OFFLINE_FROZEN_SOURCE',
        source_blob=ns['TRUE_SCALP_TRAIN_EVENT_GIT_BLOB_SHA'],training_ms=training_ms,
        fitted_model_class=type(ns['_true_scalp_model']).__name__,parameters=ns['_true_scalp_model'].get_params(),
        threadpools=threadpool_info(),samples=samples,equal_probabilities=len({r['probability'] for r in samples})==1,
        complete_loop_with_legacy_shadow_ms=loops,optimization_selected=False,
        limitations=['Local CPU/thread environment differs from production','Same offline-fitted frozen startup model used for both contexts; no new artifact deployed'],
        signal_only=True,orders=False)
    Path('qualification/v2_product_20261004/shadow_stage_timing.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':run()
