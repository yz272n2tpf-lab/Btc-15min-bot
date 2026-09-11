#!/usr/bin/env python3
"""Research-only audit for UNIFIED_V8 Railway shadow logs.

Consumes log text containing UNIFIED_V8 CANDIDATE / RESULT lines.
It never changes qualification or trading behavior. It reports:
- raw +10c outcome rates by diagnostic entry zone/setup;
- contract-side clustering so repeated signals are not mistaken for independent evidence;
- pre-target adverse distributions and winner-retention under hypothetical adverse cutoffs;
- feature-floor candidate screens that preserve every observed +10c winner.

Signal-only research utility. NO ORDERS.
"""
from __future__ import annotations
import argparse, re, sys
from collections import defaultdict, deque

CANDIDATE = re.compile(
    r"UNIFIED_V8 CANDIDATE \\| (?P<ticker>[^|]+) \\| (?P<side>UP|DOWN) \\| "
    r"zone (?P<zone>\\S+) \\| setup (?P<setup>\\S+) \\| ask (?P<entry>\\d+\\.\\d+) \\| "
    r"quality (?P<quality>[-+\\d.]+) \\| btc5 (?P<btc5>[-+\\d.]+) \\| "
    r"btc15 (?P<btc15>[-+\\d.]+) \\| btc30 (?P<btc30>[-+\\d.]+) \\| "
    r"accel (?P<accel>[-+\\d.]+) \\| brti5 (?P<brti5>[-+\\d.]+) \\| "
    r"brti15 (?P<brti15>[-+\\d.]+) \\| left (?P<left>[-+\\d.]+)s"
)
RESULT = re.compile(
    r"UNIFIED_V8 RESULT \\| (?P<ticker>[^|]+) \\| (?P<side>UP|DOWN) \\| "
    r"zone (?P<zone>\\S+) \\| setup (?P<setup>\\S+) \\| style (?P<style>\\S+) \\| "
    r"entry (?P<entry>\\d+\\.\\d+) \\| quality (?P<quality>[-+\\d.]+) \\| "
    r"max_gain (?P<gain>[-+\\d.]+) \\| adverse (?P<adverse>[-+\\d.]+) \\| "
    r"pre10_adverse (?P<pre10>[-+\\d.]+) \\| to\\+5c (?P<t5>\\S+) \\| "
    r"to\\+10c (?P<t10>\\S+) \\| to\\+20c (?P<t20>\\S+)"
)
FEATURES = ("quality","btc5","btc15","btc30","accel","brti5","brti15")

def _f(x): return float(x)
def _maybe(x): return None if x == "None" else float(x)
def _key(d):
    # Round entry/quality exactly as logged. Queue preserves repeated same-key candidates.
    return (d["ticker"].strip(), d["side"], d["zone"], d["setup"],
            round(float(d["entry"]), 3), round(float(d["quality"]), 2))

def parse(lines):
    queues = defaultdict(deque)
    rows = []
    unmatched_results = 0
    for line in lines:
        m = CANDIDATE.search(line)
        if m:
            d = m.groupdict()
            row = {k:(v.strip() if isinstance(v,str) else v) for k,v in d.items()}
            for k in ("entry","quality","btc5","btc15","btc30","accel","brti5","brti15","left"):
                row[k] = _f(row[k])
            queues[_key(row)].append(row)
            continue
        m = RESULT.search(line)
        if not m: continue
        d = m.groupdict()
        r = {k:(v.strip() if isinstance(v,str) else v) for k,v in d.items()}
        for k in ("entry","quality","gain","adverse","pre10"):
            r[k] = _f(r[k])
        for k in ("t5","t10","t20"):
            r[k] = _maybe(r[k])
        q = queues[_key(r)]
        c = q.popleft() if q else None
        if c is None:
            unmatched_results += 1
        else:
            for f in ("btc5","btc15","btc30","accel","brti5","brti15","left"):
                r[f] = c[f]
        r["hit10"] = r["t10"] is not None
        rows.append(r)
    unmatched_candidates = sum(len(q) for q in queues.values())
    return rows, unmatched_candidates, unmatched_results

def pct(a,b): return 0.0 if not b else 100.0*a/b

def summarize(rows):
    out=[]
    n=len(rows); wins=sum(r["hit10"] for r in rows)
    out.append(f"RAW n={n} hit10={wins}/{n} ({pct(wins,n):.1f}%)")
    for field in ("zone","setup"):
        buckets=defaultdict(list)
        for r in rows:buckets[r[field]].append(r)
        for name in sorted(buckets):
            b=buckets[name]; w=sum(x["hit10"] for x in b)
            out.append(f"{field.upper()} {name} n={len(b)} hit10={w}/{len(b)} ({pct(w,len(b)):.1f}%)")
    clusters=defaultdict(list)
    for r in rows:clusters[(r["ticker"],r["side"])].append(r)
    anywin=sum(any(x["hit10"] for x in b) for b in clusters.values())
    mixed=sum(any(x["hit10"] for x in b) and not all(x["hit10"] for x in b) for b in clusters.values())
    out.append(f"INDEPENDENCE contract_side_clusters={len(clusters)} any_hit10={anywin}/{len(clusters)} ({pct(anywin,len(clusters)):.1f}%) mixed={mixed} max_signals_per_cluster={max([len(b) for b in clusters.values()] or [0])}")
    for cut in (-0.01,-0.03,-0.05,-0.10):
        kept=[r for r in rows if r["pre10"] > cut]
        kw=sum(r["hit10"] for r in kept)
        allw=sum(r["hit10"] for r in rows)
        out.append(f"ADVERSE_CANDIDATE pre10>{cut:+.2f} keeps={len(kept)}/{n} wins_kept={kw}/{allw} failures_removed={(n-allw)-(len(kept)-kw)}")
    paired=[r for r in rows if all(f in r for f in FEATURES)]
    wins_p=[r for r in paired if r["hit10"]]
    if wins_p:
        for f in FEATURES:
            floor=min(r[f] for r in wins_p)
            fail_removed=sum((not r["hit10"]) and r[f] < floor for r in paired)
            out.append(f"FEATURE_CANDIDATE {f}>={floor:.2f} preserves_observed_winners={len(wins_p)}/{len(wins_p)} failures_removed={fail_removed}")
    return out

def self_test():
    sample = [
"UNIFIED_V8 CANDIDATE | T1 | UP | zone UNIFIED_VALUE_15_30C | setup CORE | ask 0.250 | quality 1.20 | btc5 +30.00 | btc15 +35.00 | btc30 +40.00 | accel +15.00 | brti5 +30.00 | brti15 +25.00 | left 500s",
"UNIFIED_V8 RESULT | T1 | UP | zone UNIFIED_VALUE_15_30C | setup CORE | style BURST | entry 0.250 | quality 1.20 | max_gain +0.150 | adverse -0.010 | pre10_adverse -0.010 | to+5c 5.0 | to+10c 10.0 | to+20c None",
"UNIFIED_V8 CANDIDATE | T2 | DOWN | zone UNIFIED_CHEAP_7_15C | setup CORE | ask 0.080 | quality 1.00 | btc5 +20.00 | btc15 +25.00 | btc30 +10.00 | accel +10.00 | brti5 +15.00 | brti15 +5.00 | left 400s",
"UNIFIED_V8 RESULT | T2 | DOWN | zone UNIFIED_CHEAP_7_15C | setup CORE | style NO_EXPANSION | entry 0.080 | quality 1.00 | max_gain +0.020 | adverse -0.070 | pre10_adverse -0.070 | to+5c None | to+10c None | to+20c None",
]
    rows,uc,ur=parse(sample)
    assert len(rows)==2 and uc==0 and ur==0
    assert rows[0]["hit10"] and not rows[1]["hit10"]
    text="\n".join(summarize(rows))
    assert "RAW n=2 hit10=1/2 (50.0%)" in text
    assert "contract_side_clusters=2" in text
    assert "FEATURE_CANDIDATE quality>=1.20" in text
    print("SELF_TEST PASS")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="Railway log text file; stdin if omitted")
    ap.add_argument("--self-test", action="store_true")
    args=ap.parse_args()
    if args.self_test:
        self_test(); return
    lines=open(args.path,encoding="utf-8",errors="replace") if args.path else sys.stdin
    rows,uc,ur=parse(lines)
    for line in summarize(rows): print(line)
    print(f"PAIRING unmatched_candidates={uc} unmatched_results={ur}")
    if ur:
        print("DECISION MORE_DATA reason=unmatched_results_make_feature_pairing_incomplete")
    elif not rows:
        print("DECISION MORE_DATA reason=no_results")
    else:
        print("DECISION KEEP_RESEARCH_ONLY reason=diagnostic_audit_no_live_gate_change")

if __name__=="__main__": main()
