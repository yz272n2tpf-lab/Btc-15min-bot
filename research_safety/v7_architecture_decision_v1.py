#!/usr/bin/env python3
"""Deterministic research-only V7 architecture synthesis.

Consumes a V7 final report and maps already-authorized freeze-gate decisions
into architecture actions. It embeds no qualification thresholds, never
changes collector behavior, and never promotes to production.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ACTION_BY_DECISION = {
    "KEEP": "INCLUDE_UNCHANGED",
    "TIGHTEN": "INCLUDE_ONLY_AFTER_EXPLICIT_TIGHTEN_POLICY",
    "REJECT": "EXCLUDE_FROM_FINAL_ARCHITECTURE",
    "MORE_DATA": "DEFER_PENDING_MORE_DATA",
}


def synthesize(final_report):
    if final_report.get("collector_identity") != "LEAD_V7":
        raise ValueError("collector_identity must be LEAD_V7")
    if final_report.get("production_promotion") != "NOT_PERFORMED":
        raise ValueError("refusing report that does not preserve production_promotion=NOT_PERFORMED")

    lanes = final_report.get("freeze_gate", {}).get("lanes", {})
    out_lanes = {}
    decisions = []
    for lane, payload in sorted(lanes.items()):
        decision = payload.get("decision", "MORE_DATA")
        if decision not in ACTION_BY_DECISION:
            raise ValueError(f"unknown freeze decision for {lane}: {decision}")
        decisions.append(decision)
        out_lanes[lane] = {
            "freeze_decision": decision,
            "architecture_action": ACTION_BY_DECISION[decision],
            "reasons": list(payload.get("reasons", [])),
        }

    if not out_lanes or "MORE_DATA" in decisions:
        overall = "MORE_DATA"
    elif all(d == "REJECT" for d in decisions):
        overall = "REJECT_ALL_LANES"
    else:
        overall = "READY_FOR_MANUAL_FINALIZATION"

    summary_status = final_report.get("summary_staleness", {}).get("status", "NOT_AUDITED")
    return {
        "schema_version": 1,
        "collector_identity": "LEAD_V7",
        "overall_architecture_status": overall,
        "lanes": out_lanes,
        "evidence_authority": final_report.get("result_source_authority", {}),
        "summary_staleness_status": summary_status,
        "production_promotion": "NOT_PERFORMED",
        "notes": [
            "Architecture actions are derived only from freeze-gate outputs; no V7 qualification thresholds are embedded here.",
            "TIGHTEN is never applied automatically and requires an explicit research policy before collector changes.",
            "Production promotion is intentionally out of scope.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("final_report", help="JSON from v7_final_report_v1.py")
    p.add_argument("--out")
    args = p.parse_args(argv)
    report = json.loads(Path(args.final_report).read_text(encoding="utf-8"))
    rendered = json.dumps(synthesize(report), indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
