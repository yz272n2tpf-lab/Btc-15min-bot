#!/usr/bin/env python3
"""Offline transition planner for V8.1 post-test results. No live trading actions."""
from __future__ import annotations
import json, sys, re

LANES=("3-7c","7-15c","15-30c","30-45c")
DECISION_RE=re.compile(r"^(3-7c|7-15c|15-30c|30-45c)\s+\|.*?\|\s+(GRADUATE(?: / PROTECT| CAUTIOUSLY)?|HOLD / MORE SAMPLE|TIGHTEN|REJECT OR TIGHTEN|REJECTED BY DESIGN|INSUFFICIENT SAMPLE|FAIL:.*)$")

MAP={
    "GRADUATE":"ENABLE",
    "GRADUATE / PROTECT":"ENABLE_PROTECTED",
    "GRADUATE CAUTIOUSLY":"ENABLE_CAUTION",
    "REJECTED BY DESIGN":"DISABLE_LOCKED",
    "HOLD / MORE SAMPLE":"DISABLE_MORE_SAMPLE",
    "TIGHTEN":"DISABLE_TIGHTEN",
    "REJECT OR TIGHTEN":"DISABLE_RESEARCH",
    "INSUFFICIENT SAMPLE":"DISABLE_MORE_SAMPLE",
}

def main(report_path,out_path):
    lines=open(report_path,'r',encoding='utf-8',errors='replace').read().splitlines()
    plan={"runtime_integrity_required":True,"signal_only":True,"no_orders":True,"lanes":{},"ready_for_integration":False}
    for line in lines:
        m=DECISION_RE.match(line.strip())
        if not m: continue
        lane,decision=m.groups()
        action=MAP.get(decision,"BLOCK")
        plan['lanes'][lane]={"decision":decision,"action":action}
    missing=[x for x in LANES if x not in plan['lanes']]
    blocked=missing or any(v['action'].startswith('DISABLE_') and v['decision']=='FAIL:' for v in plan['lanes'].values())
    plan['missing_lanes']=missing
    plan['ready_for_integration']=not missing and all(v['action'] in {'ENABLE','ENABLE_PROTECTED','ENABLE_CAUTION','DISABLE_LOCKED','DISABLE_MORE_SAMPLE','DISABLE_TIGHTEN','DISABLE_RESEARCH'} for v in plan['lanes'].values()) and not blocked
    open(out_path,'w',encoding='utf-8').write(json.dumps(plan,indent=2)+"\n")
    print(json.dumps(plan,indent=2))

if __name__=='__main__':
    if len(sys.argv)!=3: raise SystemExit('usage: python v81_transition_orchestrator.py <scorer-output.txt> <plan.json>')
    main(sys.argv[1],sys.argv[2])
