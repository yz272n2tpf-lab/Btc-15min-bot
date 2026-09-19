#!/usr/bin/env python3
"""Certified BTC15 fitted-model artifact helpers.
Cost/speed transport only: model objects and immutable metadata. NO ORDERS.
"""
from __future__ import annotations
import hashlib,json,pickle
from pathlib import Path
from typing import Any

VERSION="BTC15_CERTIFIED_MODEL_ARTIFACT_V1"
GENERAL_FEATURES=["return_3","body_strength","trend_5_20","sma_distance","acceleration","momentum_3"]
FAIR_FEATURES=[
"elapsed","remaining","current_side","dist_target","abs_dist_target","dist_target_pct",
"move_from_start","move_from_start_pct","move1","move2","move3","move5",
"support1","support2","support3","support5","range5","vol5",
"dist_per_min_remaining","dist_over_range5"]
GENERAL_SPEC={"n_estimators":1200,"max_depth":8,"random_state":42,"class_weight":"balanced"}
FAIR_RF_SPEC={"n_estimators":900,"max_depth":9,"min_samples_leaf":12,"class_weight":"balanced","random_state":42,"n_jobs":-1}
FAIR_SIGMOID_SPEC={"solver":"lbfgs","C":1.0,"max_iter":1000,"random_state":42}

def sha256_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def canonical_meta(meta:dict[str,Any])->bytes:return json.dumps(meta,sort_keys=True,separators=(",",":")).encode()

def write_bundle(path:Path,*,general_model,fair_rf,fair_sigmoid,metadata:dict[str,Any])->dict[str,Any]:
    meta=dict(metadata)
    meta.update({"version":VERSION,"general_features":GENERAL_FEATURES,"fair_features":FAIR_FEATURES,
                 "general_spec":GENERAL_SPEC,"fair_rf_spec":FAIR_RF_SPEC,"fair_sigmoid_spec":FAIR_SIGMOID_SPEC,
                 "orders":False})
    payload=pickle.dumps({"general_model":general_model,"fair_rf":fair_rf,"fair_sigmoid":fair_sigmoid,
                          "metadata":meta},protocol=pickle.HIGHEST_PROTOCOL)
    path.write_bytes(payload)
    manifest={"artifact_sha256":sha256_bytes(payload),"artifact_bytes":len(payload),
              "metadata_sha256":sha256_bytes(canonical_meta(meta)),"version":VERSION,"orders":False}
    path.with_suffix(path.suffix+".manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True))
    return manifest

def load_bundle(path:Path,expected_sha256:str|None=None)->dict[str,Any]:
    raw=path.read_bytes(); actual=sha256_bytes(raw)
    if expected_sha256 and actual!=expected_sha256:raise RuntimeError("CERTIFIED MODEL ARTIFACT SHA MISMATCH")
    obj=pickle.loads(raw);meta=obj.get("metadata") or {}
    if meta.get("version")!=VERSION or meta.get("orders") is not False:raise RuntimeError("ARTIFACT METADATA SAFETY MISMATCH")
    if meta.get("general_features")!=GENERAL_FEATURES or meta.get("fair_features")!=FAIR_FEATURES:raise RuntimeError("ARTIFACT FEATURE ORDER DRIFT")
    if meta.get("general_spec")!=GENERAL_SPEC or meta.get("fair_rf_spec")!=FAIR_RF_SPEC or meta.get("fair_sigmoid_spec")!=FAIR_SIGMOID_SPEC:raise RuntimeError("ARTIFACT MODEL SPEC DRIFT")
    return obj
