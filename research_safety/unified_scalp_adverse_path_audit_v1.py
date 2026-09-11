#!/usr/bin/env python3
"""Research-only adverse-path audit for the unified BTC 15m scalp engine.

The archived/live RESULT schema records maximum gain, aggregate adverse move,
and time-to-+10c, but it does not record whether the adverse move happened
before or after the +10c expansion. This auditor deliberately refuses to call a
successful signal an adverse-entry trap when event ordering is unavailable.

Failed expansion observations can still be analyzed because no +10c target was
reached in the observation window. Legacy ultra-cheap reversal observations are
counted for audit only and never participate in unified graduation evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from unified_scalp_qualification_guard_v1 import (
    LEGACY_REVERSAL_SOURCE,
    UNIFIED_STANDARD,
    price_zone,
)
from unified_scalp_result_scorecard_v1 import parse_result_line

EXPANSION_WINDOW_SECONDS = 180.0


def _new_bucket() -> dict:
    return {
        "n": 0,
        "hit10_in_window": 0,
        "failed_expansion": 0,
        "successful_order_unknown": 0,
        "failed_adverse_sum": 0.0,
        "failed_adverse_n": 0,
        "failed_worst_adverse": None,
        "failed_adverse_ratio_sum": 0.0,
        "failed_adverse_ratio_n": 0,
    }


def audit_lines(lines: list[str]) -> dict:
    parsed = [p for line in lines if (p := parse_result_line(line)) is not None]
    unified = [p for p in parsed if p.source == UNIFIED_STANDARD]
    legacy = [p for p in parsed if p.source == LEGACY_REVERSAL_SOURCE]
    unknown = [p for p in parsed if p.source.startswith("UNKNOWN:")]

    zones = defaultdict(_new_bucket)
    classifications = defaultdict(int)

    for p in unified:
        z = price_zone(p.entry)
        bucket = zones[z]
        bucket["n"] += 1
        hit10 = p.t10 is not None and p.t10 <= EXPANSION_WINDOW_SECONDS

        if hit10:
            bucket["hit10_in_window"] += 1
            if p.adverse < 0:
                bucket["successful_order_unknown"] += 1
                classifications["SUCCESS_ADVERSE_ORDER_UNKNOWN"] += 1
            else:
                classifications["SUCCESS_NO_ADVERSE_RECORDED"] += 1
            continue

        bucket["failed_expansion"] += 1
        classifications["FAILED_EXPANSION"] += 1
        if p.adverse < 0:
            bucket["failed_adverse_sum"] += p.adverse
            bucket["failed_adverse_n"] += 1
            ratio = abs(p.adverse) / p.entry if p.entry > 0 else None
            if ratio is not None:
                bucket["failed_adverse_ratio_sum"] += ratio
                bucket["failed_adverse_ratio_n"] += 1
            worst = bucket["failed_worst_adverse"]
            if worst is None or p.adverse < worst:
                bucket["failed_worst_adverse"] = p.adverse

    normalized_zones = {}
    for z, bucket in zones.items():
        row = dict(bucket)
        row["hit10_rate"] = row["hit10_in_window"] / row["n"] if row["n"] else None
        row["failed_avg_adverse"] = (
            row["failed_adverse_sum"] / row["failed_adverse_n"]
            if row["failed_adverse_n"] else None
        )
        row["failed_avg_adverse_to_entry"] = (
            row["failed_adverse_ratio_sum"] / row["failed_adverse_ratio_n"]
            if row["failed_adverse_ratio_n"] else None
        )
        del row["failed_adverse_sum"]
        del row["failed_adverse_n"]
        del row["failed_adverse_ratio_sum"]
        del row["failed_adverse_ratio_n"]
        normalized_zones[z] = row

    success_order_unknown = classifications["SUCCESS_ADVERSE_ORDER_UNKNOWN"]
    failed = classifications["FAILED_EXPANSION"]

    return {
        "schema": "unified-scalp-adverse-path-audit-v1",
        "research_only": True,
        "signal_only": True,
        "production_promotion": "NOT_PERFORMED",
        "result_stream_authority": True,
        "aggregate_adverse_has_event_order": False,
        "parsed_results": len(parsed),
        "unified_results": len(unified),
        "legacy_reversal_research_only": len(legacy),
        "unknown_lane_results": len(unknown),
        "classifications": dict(classifications),
        "zones": normalized_zones,
        "decision": {
            "unified_scalp_expansion_path": "KEEP",
            "separate_ultra_cheap_graduation_path": "REJECT",
            "adverse_trap_tightening": "MORE_DATA",
            "reason": (
                "Aggregate adverse on successful expansions has unknown event order; "
                "tightening on that value alone could reject good expansions."
                if success_order_unknown
                else "No timestamped pre-target adverse evidence is available."
            ),
            "confirmed_failed_expansion_observations": failed,
            "successful_expansions_with_unknown_adverse_order": success_order_unknown,
            "evidence_needed": "timestamped pre-target adverse or price-path ordering",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", nargs="?", help="Log file; defaults to stdin")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.log:
        lines = Path(args.log).read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        lines = sys.stdin.read().splitlines()
    report = audit_lines(lines)
    print(json.dumps(report, sort_keys=args.json, indent=None if args.json else 2))
    return 0 if report["unknown_lane_results"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
