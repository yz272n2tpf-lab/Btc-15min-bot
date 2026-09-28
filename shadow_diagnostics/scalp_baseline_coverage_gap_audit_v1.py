#!/usr/bin/env python3
"""BTC15 raw-baseline scalp coverage gap audit V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Explains every fully observed contract that does NOT produce a completed serial
baseline scalp opportunity. This tool does not loosen any gate and does not
select a production rule.

It reports two separate things:
1. causal/mechanical reason the existing baseline missed the contract;
2. hindsight opportunity ceiling: whether any already-collected candidate path
   in that uncovered contract later achieved executable +5c/+10c/+20c.

The hindsight ceiling is diagnostic only. It is never treated as a signal or
accuracy result and cannot be used directly for promotion.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import scalp_event_schema_adapter_v1 as adapter
import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_frontier_v1 as union

VERSION = "BTC15_SCALP_BASELINE_COVERAGE_GAP_AUDIT_V1"


def typ(r: Mapping[str, Any]) -> str:
    return str(r.get("record_type") or "").strip().upper()


def contract(r: Mapping[str, Any]) -> str:
    return str(r.get("contract") or "").strip()


def cid(r: Mapping[str, Any]) -> str:
    return str(r.get("candidate_id") or "").strip()


def finite(v: Any) -> float | None:
    return union.finite(v)


def classify_gap(
    candidates: list[Mapping[str, Any]],
    done_ids: set[str],
    path_ids: set[str],
) -> tuple[str, dict[str, Any]]:
    """Classify why the current baseline serial builder cannot cover a contract."""
    valid_side = [r for r in candidates if str(r.get("side") or "").strip().upper() in {"UP", "DOWN"}]
    early = [r for r in valid_side if (finite(r.get("seconds_left")) or -1.0) >= q.MIN_SECONDS_LEFT]
    qualified = [r for r in candidates if q.baseline_qualified(r)]
    qualified_done = [r for r in qualified if cid(r) and cid(r) in done_ids]
    qualified_complete = [r for r in qualified_done if cid(r) in path_ids]

    btc30_early = [q.btc30(r) for r in early]
    btc30_early = [x for x in btc30_early if x is not None]

    detail = {
        "candidate_rows": len(candidates),
        "valid_side_candidates": len(valid_side),
        "early_candidates_ge120s": len(early),
        "baseline_qualified_candidates": len(qualified),
        "qualified_with_result": len(qualified_done),
        "qualified_with_path": len(qualified_complete),
        "max_early_btc30_side": None if not btc30_early else max(btc30_early),
    }

    if not candidates:
        return "NO_CANDIDATE_ROWS", detail
    if not valid_side:
        return "INVALID_SIDE_ONLY", detail
    if not early:
        return "LATE_ONLY_CANDIDATES", detail
    if not btc30_early:
        return "BTC30_MISSING_ON_EARLY_CANDIDATES", detail
    if not qualified:
        if max(btc30_early) < q.MIN_BTC30:
            return "BTC30_BELOW_BASELINE_15", detail
        return "OTHER_BASELINE_GATE_FAIL", detail
    if not qualified_done:
        return "QUALIFIED_CANDIDATE_NO_RESULT", detail
    if not qualified_complete:
        return "QUALIFIED_RESULT_NO_PATH", detail
    return "SERIAL_LIFECYCLE_BLOCKED", detail


def candidate_path_ceiling(
    candidates: list[Mapping[str, Any]],
    paths_by_id: Mapping[str, list[Mapping[str, Any]]],
    done_ids: set[str],
) -> dict[str, Any]:
    """Hindsight-only ceiling from collected candidate paths; not a causal selector."""
    measured: list[dict[str, Any]] = []
    for cand in candidates:
        candidate_id = cid(cand)
        if not candidate_id or candidate_id not in done_ids:
            continue
        paths = list(paths_by_id.get(candidate_id, []))
        if not paths:
            continue
        outcome = q.measure_path(cand, paths)
        peak = finite(outcome.peak_gain)
        if peak is None:
            continue
        ask = finite(cand.get("entry_ask"))
        left = finite(cand.get("seconds_left"))
        measured.append({
            "candidate_id": candidate_id,
            "peak_gain": peak,
            "entry_ask": ask,
            "seconds_left": left,
            "baseline_qualified": q.baseline_qualified(cand),
        })

    def any_hit(target: float, predicate=lambda r: True) -> bool:
        return any(r["peak_gain"] >= target and predicate(r) for r in measured)

    return {
        "complete_candidate_paths": len(measured),
        "hindsight_any_plus5": any_hit(.05),
        "hindsight_any_plus10": any_hit(.10),
        "hindsight_any_plus20": any_hit(.20),
        "hindsight_early_plus10": any_hit(.10, lambda r: r.get("seconds_left") is not None and r["seconds_left"] >= q.MIN_SECONDS_LEFT),
        "hindsight_affordable_plus10": any_hit(.10, lambda r: r.get("entry_ask") is not None and r["entry_ask"] <= .50),
        "hindsight_early_affordable_plus10": any_hit(
            .10,
            lambda r: r.get("seconds_left") is not None and r["seconds_left"] >= q.MIN_SECONDS_LEFT
            and r.get("entry_ask") is not None and r["entry_ask"] <= .50,
        ),
        "hindsight_nonbaseline_plus10": any_hit(.10, lambda r: not r.get("baseline_qualified")),
        "best_hindsight_peak_c": None if not measured else 100.0 * max(r["peak_gain"] for r in measured),
    }


def audit(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    adapted = adapter.adapt_rows(rows)
    universe = union.full_contract_universe(adapted)
    if not universe:
        return {
            "version": VERSION,
            "status": "FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE",
            "orders": False,
            "automatic_promotion": False,
        }

    denominator = set(universe)
    baseline_opps = [r for r in q.build_serial_opportunities(adapted) if r.get("contract") in denominator]
    covered = {str(r.get("contract") or "") for r in baseline_opps}
    uncovered = sorted(denominator - covered)

    candidates_by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    paths_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    done_ids: set[str] = set()
    path_ids: set[str] = set()
    for row in adapted:
        t = typ(row)
        if t == "CANDIDATE" and contract(row) in denominator:
            candidates_by_contract[contract(row)].append(dict(row))
        elif t == "PATH" and cid(row):
            paths_by_id[cid(row)].append(dict(row))
            path_ids.add(cid(row))
        elif t == "RESULT" and cid(row):
            done_ids.add(cid(row))

    ledger: list[dict[str, Any]] = []
    for c in uncovered:
        cands = sorted(candidates_by_contract.get(c, []), key=lambda r: q.dt(r.get("timestamp_utc")))
        reason, detail = classify_gap(cands, done_ids, path_ids)
        ceiling = candidate_path_ceiling(cands, paths_by_id, done_ids)
        ledger.append({
            "contract": c,
            "reason": reason,
            **detail,
            **ceiling,
        })

    reasons = Counter(r["reason"] for r in ledger)
    denom = len(denominator)
    summary = {
        "version": VERSION,
        "status": "READY",
        "orders": False,
        "manual_execution_only": True,
        "production_logic_changed": False,
        "full_observed_contracts": denom,
        "baseline_covered_contracts": len(covered),
        "baseline_true_contract_coverage": None if not denom else len(covered) / denom,
        "uncovered_contracts": len(uncovered),
        "contracts_needed_to_reach_90pct": max(0, int(__import__("math").ceil(.90 * denom)) - len(covered)),
        "gap_reasons": dict(sorted(reasons.items())),
        "uncovered_with_any_complete_candidate_path": sum(r["complete_candidate_paths"] > 0 for r in ledger),
        "uncovered_with_hindsight_plus5": sum(bool(r["hindsight_any_plus5"]) for r in ledger),
        "uncovered_with_hindsight_plus10": sum(bool(r["hindsight_any_plus10"]) for r in ledger),
        "uncovered_with_hindsight_plus20": sum(bool(r["hindsight_any_plus20"]) for r in ledger),
        "uncovered_with_hindsight_early_plus10": sum(bool(r["hindsight_early_plus10"]) for r in ledger),
        "uncovered_with_hindsight_affordable_plus10": sum(bool(r["hindsight_affordable_plus10"]) for r in ledger),
        "uncovered_with_hindsight_early_affordable_plus10": sum(bool(r["hindsight_early_affordable_plus10"]) for r in ledger),
        "uncovered_with_hindsight_nonbaseline_plus10": sum(bool(r["hindsight_nonbaseline_plus10"]) for r in ledger),
        "hindsight_ceiling_is_not_a_signal": True,
        "automatic_promotion": False,
    }
    return {"summary": summary, "ledger": ledger}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({k for r in rows for k in r})
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default="/data/scalp_move_shadow_v1_events.csv")
    ap.add_argument("--outdir", default="shadow_baseline_gap_out")
    args = ap.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    result = audit(q.read_rows(Path(args.csv)))
    if "summary" not in result:
        (outdir / "scalp_baseline_coverage_gap_v1.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 2
    write_csv(outdir / "scalp_baseline_coverage_gap_ledger_v1.csv", result["ledger"])
    (outdir / "scalp_baseline_coverage_gap_v1.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
