#!/usr/bin/env python3
"""One-command V7 research report with fail-closed evidence and architecture synthesis."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from v7_architecture_decision_v1 import synthesize as synthesize_architecture
from v7_brti_reliability_audit_v1 import audit as audit_brti
from v7_contract_independence_audit_v1 import build_independence_audit
from v7_data_quality_incident_audit_v1 import audit_incidents
from v7_evidence_decomposition_v1 import build_decomposition
from v7_split_scorecard_v1 import build_scorecard
from v7_freeze_gate_v1 import evaluate
from v7_summary_staleness_audit_v1 import audit as audit_summary_staleness


def build_final_report(log_text, policy=None):
    scorecard = build_scorecard(log_text)
    gate = evaluate(scorecard, policy)
    evidence = build_decomposition(log_text)
    independence = build_independence_audit(log_text)
    brti_reliability = audit_brti(log_text)
    data_quality_incidents = audit_incidents(log_text)
    summary_staleness = audit_summary_staleness(log_text)
    report = {
        "schema_version": 6,
        "collector_identity": "LEAD_V7",
        "result_source_authority": {
            "scoring_source": "RESULT_STREAM",
            "contract_summary_role": "ADVISORY_ONLY",
            "reason": "RESULT records can arrive after CONTRACT_SUMMARY and are reconstructed by ticker.",
        },
        "scorecard": scorecard,
        "evidence_decomposition": evidence,
        "contract_independence": independence,
        "brti_reliability": brti_reliability,
        "data_quality_incidents": data_quality_incidents,
        "summary_staleness": summary_staleness,
        "freeze_gate": gate,
        "production_promotion": "NOT_PERFORMED",
    }
    report["architecture_decision"] = synthesize_architecture(report)
    return report


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
