#!/usr/bin/env python3
"""One-command V7 research report: parse logs, score lanes, apply optional gate."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from v7_split_scorecard_v1 import build_scorecard
from v7_freeze_gate_v1 import evaluate

def build_final_report(log_text, policy=None):
    scorecard = build_scorecard(log_text)
    gate = evaluate(scorecard, policy)
    return {
        "schema_version": 1,
        "collector_identity": "LEAD_V7",
        "scorecard": scorecard,
        "freeze_gate": gate,
        "production_promotion": "NOT_PERFORMED",
    }

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("logfile")
    p.add_argument("--policy")
    p.add_argument("--out")
    args = p.parse_args(argv)
    text = Path(args.logfile).read_text(encoding="utf-8")
    policy = json.loads(Path(args.policy).read_text(encoding="utf-8")) if args.policy else None
    report = build_final_report(text, policy)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
