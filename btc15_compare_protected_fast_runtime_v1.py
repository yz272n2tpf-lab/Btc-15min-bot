#!/usr/bin/env python3
"""Protected-vs-fast acceptance comparator for BTC15 runtime canary.
Consumes two JSON snapshots captured at the same source/input boundary.
NO ORDERS.
"""
import argparse,json,math
from pathlib import Path

EXACT=["contract","ticker","open_time","close_time","target","early_status","early_side",
"final_status","final_side","final_source","brti_ready","brti_side","scalp_authority","orders"]
FLOAT=["general_up_prob","general_down_prob","fair_up","fair_down","fair_flip_prob",
"fair_stay_prob","early_ask","early_fair","early_edge","final_confidence","brti_gap"]
TOL=1e-12

def eqf(a,b):
 if a is None or b is None:return a is b
 try:return math.isclose(float(a),float(b),rel_tol=0,abs_tol=TOL)
 except:return False

def main():
 p=argparse.ArgumentParser();p.add_argument("protected");p.add_argument("fast");a=p.parse_args()
 x=json.loads(Path(a.protected).read_text());y=json.loads(Path(a.fast).read_text());bad=[]
 if x.get("source_boundary_sha256")!=y.get("source_boundary_sha256"):bad.append("source_boundary_sha256")
 for k in EXACT:
  if x.get(k)!=y.get(k):bad.append(k)
 for k in FLOAT:
  if not eqf(x.get(k),y.get(k)):bad.append(k)
 if y.get("orders") is not False:bad.append("orders_not_false")
 # Fast path may be faster, never materially slower.
 for k in ["source_to_compute_ms","compute_to_publish_ms","source_to_publish_ms"]:
  if float(y.get(k,1e99))>float(x.get(k,0))*1.02+5:bad.append(k+"_slower")
 if bad:raise SystemExit("FAST_RUNTIME_PARITY_FAIL | "+",".join(sorted(set(bad))))
 print("FAST_RUNTIME_PARITY_PASS | exact semantics | latency non-regression | NO ORDERS")
if __name__=="__main__":main()
