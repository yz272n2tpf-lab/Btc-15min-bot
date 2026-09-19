#!/usr/bin/env python3
"""Runtime certified artifact preflight. Read-only, no orders.
Validates artifact SHA/spec/features and proves loaded estimators can score fixed frames.
"""
from __future__ import annotations
import argparse,json,pickle
from pathlib import Path
import numpy as np
import btc15_certified_model_artifact_v1 as art

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--artifact",required=True);ap.add_argument("--sha",required=True);ap.add_argument("--parity-input",required=True);a=ap.parse_args()
 z=art.load_bundle(Path(a.artifact),a.sha)
 q=pickle.loads(Path(a.parity_input).read_bytes())
 gx=q["general_parity_X"];fx=q["fair_parity_X"]
 if list(gx.columns)!=art.GENERAL_FEATURES:raise SystemExit("STOP general live feature order drift")
 if list(fx.columns)!=art.FAIR_FEATURES:raise SystemExit("STOP fair live feature order drift")
 gp=z["general_model"].predict_proba(gx);raw=z["fair_rf"].predict_proba(fx)[:,1];cal=z["fair_sigmoid"].predict_proba(raw.reshape(-1,1))
 for name,x in [("general",gp),("fair_raw",raw),("fair_cal",cal)]:
  if not np.isfinite(np.asarray(x,dtype=float)).all():raise SystemExit("STOP nonfinite "+name)
 print(json.dumps({"status":"CERTIFIED_ARTIFACT_RUNTIME_PREFLIGHT_PASS","artifact_sha256":a.sha,
  "general_rows":len(gx),"fair_rows":len(fx),"orders":False},sort_keys=True))
if __name__=="__main__":main()
