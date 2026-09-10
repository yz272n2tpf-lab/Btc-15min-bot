#!/usr/bin/env python3
"""Deterministic research-only V7 KEEP/TIGHTEN/REJECT/MORE_DATA gate.

This tool intentionally embeds NO V7 qualification thresholds. A policy must
be supplied explicitly. Without one, every lane returns MORE_DATA.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

DECISIONS = ("KEEP", "TIGHTEN", "REJECT", "MORE_DATA")

def _metric_ok(metrics, rules):
    failures = []
    for key, spec in sorted(rules.items()):
        value = metrics.get(key)
        if value is None:
            failures.append(f"{key}=MISSING")
            continue
        if "min" in spec and value < spec["min"]:
            failures.append(f"{key}<{spec['min']}")
        if "max" in spec and value > spec["max"]:
            failures.append(f"{key}>{spec['max']}")
    return failures

def decide_lane(metrics, policy):
    if policy is None:
        return {"decision": "MORE_DATA", "reasons": ["NO_POLICY_SUPPLIED"]}
    min_n = int(policy.get("min_n", 0))
    n = int(metrics.get("n") or 0)
    if n < min_n:
        return {"decision": "MORE_DATA", "reasons": [f"n={n}<min_n={min_n}"]}
    reject_failures = _metric_ok(metrics, policy.get("reject_floor", {}))
    if reject_failures:
        return {"decision": "REJECT", "reasons": reject_failures}
    keep_failures = _metric_ok(metrics, policy.get("keep", {}))
    if not keep_failures:
        return {"decision": "KEEP", "reasons": ["ALL_KEEP_RULES_PASSED"]}
    return {"decision": "TIGHTEN", "reasons": keep_failures}

def evaluate(scorecard, policy_doc=None):
    lane_policies = {} if policy_doc is None else policy_doc.get("lanes", {})
    out = {"schema_version": 1, "collector_identity": scorecard.get("collector_identity"), "lanes": {}}
    for lane, payload in sorted(scorecard.get("lanes", {}).items()):
        out["lanes"][lane] = decide_lane(payload.get("overall", {}), lane_policies.get(lane))
    return out

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("scorecard", help="JSON scorecard from v7_split_scorecard_v1.py")
    p.add_argument("--policy", help="Explicit research freeze policy JSON")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args(argv)
    scorecard = json.loads(Path(args.scorecard).read_text(encoding="utf-8"))
    policy = json.loads(Path(args.policy).read_text(encoding="utf-8")) if args.policy else None
    print(json.dumps(evaluate(scorecard, policy), indent=2 if args.pretty else None, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
