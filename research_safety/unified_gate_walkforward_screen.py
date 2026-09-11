#!/usr/bin/env python3
"""Research-only chronological holdout screen for the unified 3c-45c scalp engine.

Discovers price-neutral entry-time single/pair feature floors on earlier
contract-side clusters and validates the exact rules on later unseen clusters.
Never changes the live gate. Never uses price/zone as qualification features.
Signal-only. NO ORDERS.
"""
from __future__ import annotations
import argparse, itertools, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from research_safety.unified_gate_tighten_screen import (  # noqa:E402
    GRIDS, MIN_FAILURE_CLUSTERS_REMOVED_FOR_WATCH,
    MIN_FAILURES_REMOVED_FOR_WATCH, MIN_FAILURE_ZONES_FOR_WATCH,
    MIN_WINNER_CLUSTERS_FOR_WATCH, cluster, parse,
)

PAIR_FEATURES=("btc5","btc15","btc30","accel","brti5","brti15")
TRAIN_FRACTION=.70
MIN_HOLDOUT_WINNER_CLUSTERS=5
MIN_HOLDOUT_FAILURE_CLUSTERS=3
MIN_HOLDOUT_FAILURES_REMOVED=3
MIN_HOLDOUT_FAILURE_ZONES=2

def ordered_clusters(rows):
    seen=set(); out=[]
    for r in rows:
        k=cluster(r)
        if k not in seen: seen.add(k); out.append(k)
    return out

def split_rows(rows,fraction=TRAIN_FRACTION):
    keys=ordered_clusters(rows)
    if len(keys)<2:return rows[:],[],keys,[]
    cut=max(1,min(len(keys)-1,int(len(keys)*fraction)))
    a=set(keys[:cut]); b=set(keys[cut:])
    return ([r for r in rows if cluster(r) in a],
            [r for r in rows if cluster(r) in b],keys[:cut],keys[cut:])

def evaluate(rows,conds):
    paired=[r for r in rows if all(f in r for f,_ in conds)]
    removed=[r for r in paired if any(float(r[f])<t for f,t in conds)]
    wins=[r for r in removed if r["hit10"]]
    fails=[r for r in removed if not r["hit10"]]
    return {"n":len(paired),
            "winner_clusters":len({cluster(r) for r in paired if r["hit10"]}),
            "wins_removed":len(wins),"failures_removed":len(fails),
            "failure_clusters_removed":len({cluster(r) for r in fails}),
            "failure_zones_removed":len({r["zone"] for r in fails})}

def discovery_ok(s):
    return (s["wins_removed"]==0 and
            s["winner_clusters"]>=MIN_WINNER_CLUSTERS_FOR_WATCH and
            s["failure_clusters_removed"]>=MIN_FAILURE_CLUSTERS_REMOVED_FOR_WATCH and
            s["failures_removed"]>=MIN_FAILURES_REMOVED_FOR_WATCH and
            s["failure_zones_removed"]>=MIN_FAILURE_ZONES_FOR_WATCH)

def holdout_decision(s):
    if s["wins_removed"]:return "REJECT"
    if (s["winner_clusters"]>=MIN_HOLDOUT_WINNER_CLUSTERS and
        s["failure_clusters_removed"]>=MIN_HOLDOUT_FAILURE_CLUSTERS and
        s["failures_removed"]>=MIN_HOLDOUT_FAILURES_REMOVED and
        s["failure_zones_removed"]>=MIN_HOLDOUT_FAILURE_ZONES):return "TIGHTEN"
    return "MORE_DATA"

def candidates(train):
    out=[]
    for f,grid in GRIDS.items():
        for t in grid:
            c=((f,t),); s=evaluate(train,c)
            if discovery_ok(s):out.append(("SINGLE",c,s))
    for f1,f2 in itertools.combinations(PAIR_FEATURES,2):
        for t1 in GRIDS[f1]:
            for t2 in GRIDS[f2]:
                c=((f1,t1),(f2,t2)); s=evaluate(train,c)
                if discovery_ok(s):out.append(("PAIR",c,s))
    return out

def rank(x):
    s=x[2]
    return (s["failure_clusters_removed"],s["failures_removed"],s["failure_zones_removed"])

def rule_text(c):return " AND ".join("%s>=%.2f"%(f,t) for f,t in c)

def analyze(rows):
    train,holdout,tk,hk=split_rows(rows); rules=candidates(train)
    out=["POLICY PRICE_ONLY=REJECT OUTCOME_LOOKAHEAD_QUALIFICATION=REJECT "
         "ULTRA_CHEAP_SEPARATE_LANE=REJECT LIVE_GATE_CHANGE=NO",
         "SPLIT total_clusters=%d discovery_clusters=%d holdout_clusters=%d discovery_n=%d holdout_n=%d"%
         (len(tk)+len(hk),len(tk),len(hk),len(train),len(holdout))]
    for shape in ("SINGLE","PAIR"):
        group=[x for x in rules if x[0]==shape]
        if not group:
            out.append("%s decision=MORE_DATA reason=no_discovery_candidate"%shape);continue
        _,c,d=max(group,key=rank); v=evaluate(holdout,c); dec=holdout_decision(v)
        out.append("%s rule=%s decision=%s discovery_failures=%d discovery_failure_clusters=%d "
                   "discovery_zones=%d holdout_wins_removed=%d holdout_failures_removed=%d "
                   "holdout_failure_clusters=%d holdout_zones=%d holdout_winner_clusters=%d"%
                   (shape,rule_text(c),dec,d["failures_removed"],d["failure_clusters_removed"],
                    d["failure_zones_removed"],v["wins_removed"],v["failures_removed"],
                    v["failure_clusters_removed"],v["failure_zones_removed"],v["winner_clusters"]))
    out.append("WALK_FORWARD note=chronological_contract_side_holdout; TIGHTEN_requires_unseen_independent_support")
    return out

def self_test():
    wins=[{"ticker":"W%d"%i,"side":"UP","zone":"UNIFIED_VALUE_15_30C","hit10":True,
           "btc5":30.,"brti15":30.} for i in range(5)]
    fails=[
      {"ticker":"F0","side":"DOWN","zone":"UNIFIED_CHEAP_7_15C","hit10":False,"btc5":21.,"brti15":30.},
      {"ticker":"F1","side":"DOWN","zone":"UNIFIED_VALUE_15_30C","hit10":False,"btc5":30.,"brti15":20.},
      {"ticker":"F2","side":"DOWN","zone":"UNIFIED_HIGH_30_45C","hit10":False,"btc5":21.,"brti15":20.},
      {"ticker":"F2","side":"DOWN","zone":"UNIFIED_HIGH_30_45C","hit10":False,"btc5":22.,"brti15":20.}]
    c=(("btc5",23.),("brti15",25.))
    s=evaluate(wins+fails,c)
    assert discovery_ok(s)
    good=[{"ticker":"HW0","side":"UP","zone":"UNIFIED_CHEAP_7_15C","hit10":True,"btc5":24.,"brti15":26.},
          {"ticker":"HF0","side":"DOWN","zone":"UNIFIED_VALUE_15_30C","hit10":False,"btc5":22.,"brti15":30.}]
    assert holdout_decision(evaluate(good,c))=="MORE_DATA"
    bad=good+[{"ticker":"HW1","side":"UP","zone":"UNIFIED_CHEAP_7_15C","hit10":True,"btc5":22.,"brti15":30.}]
    assert holdout_decision(evaluate(bad,c))=="REJECT"
    print("SELF_TEST PASS")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("path",nargs="?"); ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:self_test();return
    lines=open(a.path,encoding="utf-8",errors="replace") if a.path else sys.stdin
    rows,uc,ur,bad=parse(lines)
    for x in analyze(rows):print(x)
    print("PAIRING unmatched_candidates=%d unmatched_results=%d bad_lines=%d"%(uc,ur,bad))
    print("DECISION MORE_DATA reason=incomplete_or_unparseable_evidence" if ur or bad
          else "DECISION KEEP_RESEARCH_ONLY reason=no_live_gate_change")
if __name__=="__main__":main()
