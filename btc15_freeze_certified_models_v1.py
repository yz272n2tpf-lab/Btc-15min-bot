#!/usr/bin/env python3
"""Offline-only freeze gate for BTC15 fitted models.
Imports no live bot and places no orders. It validates fitted estimator identity,
serializes the exact objects, reloads them, and requires machine-precision parity.
"""
from __future__ import annotations
import argparse,hashlib,json,pickle
from pathlib import Path
import numpy as np
import btc15_certified_model_artifact_v1 as art

def h(x)->str:return hashlib.sha256(x).hexdigest()
def spec_ok(model,want):
    p=model.get_params(deep=False)
    return all(p.get(k)==v for k,v in want.items())

def maxdiff(a,b):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    return float(np.max(np.abs(a-b))) if a.size else 0.0

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True,help="offline pickle with fitted models + frozen parity frames")
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    src=Path(args.input); obj=pickle.loads(src.read_bytes())
    g=obj["general_model"];fr=obj["fair_rf"];fs=obj["fair_sigmoid"]
    gx=obj["general_parity_X"];fx=obj["fair_parity_X"]
    if list(gx.columns)!=art.GENERAL_FEATURES:raise SystemExit("STOP general feature order drift")
    if list(fx.columns)!=art.FAIR_FEATURES:raise SystemExit("STOP fair feature order drift")
    if not spec_ok(g,art.GENERAL_SPEC):raise SystemExit("STOP general RF spec drift")
    if not spec_ok(fr,art.FAIR_RF_SPEC):raise SystemExit("STOP fair RF spec drift")
    if not spec_ok(fs,art.FAIR_SIGMOID_SPEC):raise SystemExit("STOP fair sigmoid spec drift")
    gp0=g.predict_proba(gx); fp0=fr.predict_proba(fx)[:,1]
    sp0=fs.predict_proba(fp0.reshape(-1,1))
    meta={"source_freeze_sha256":h(src.read_bytes()),"general_parity_rows":len(gx),"fair_parity_rows":len(fx),
          "training_boundary_sha256":obj["training_boundary_sha256"],"fair_chronology_sha256":obj["fair_chronology_sha256"]}
    man=art.write_bundle(Path(args.output),general_model=g,fair_rf=fr,fair_sigmoid=fs,metadata=meta)
    z=art.load_bundle(Path(args.output),man["artifact_sha256"])
    gp1=z["general_model"].predict_proba(gx);fp1=z["fair_rf"].predict_proba(fx)[:,1]
    sp1=z["fair_sigmoid"].predict_proba(fp1.reshape(-1,1))
    dg,df,ds=maxdiff(gp0,gp1),maxdiff(fp0,fp1),maxdiff(sp0,sp1)
    if max(dg,df,ds)>1e-12:raise SystemExit(f"STOP probability parity failure {dg} {df} {ds}")
    print(json.dumps({"status":"MODEL_ARTIFACT_FREEZE_PASS","general_max_abs_diff":dg,
      "fair_rf_max_abs_diff":df,"fair_sigmoid_max_abs_diff":ds,**man,"orders":False},sort_keys=True))
if __name__=="__main__":main()
