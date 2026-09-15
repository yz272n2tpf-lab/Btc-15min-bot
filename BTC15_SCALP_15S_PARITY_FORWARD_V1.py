#!/usr/bin/env python3
"""
BTC15 SCALP 15-second cross-source parity forward validator V1.

FRESH FORWARD SHADOW ONLY | SIGNAL ONLY | NO ORDERS

Frozen hypothesis
-----------------
Keep the current reviewed serial SCALP blueprint unchanged, but compare it with
ONE research-only entry-strength condition on NEW future data only:

    brti15 / btc15 >= 1.00

Interpretation: the side-aligned BRTI 15-second move must be at least as strong
as the side-aligned BTC 15-second move at candidate time. This is a cross-source
confirmation hypothesis, not a price rule, time rule, stop-loss, or order rule.

Why this one rule exists
------------------------
The prior 60-opportunity sample is development/hypothesis-generation data only.
Never-armed false starts had nearly identical 5s BTC/BRTI momentum to +10c
winners, while their 15s BRTI confirmation was weaker. BTC30 tightening and
normalized-momentum tightening were already rejected. No threshold sweep is
performed here: parity 1.00 is frozen before this future cutoff.

Validation gate
---------------
- Fresh cutoff: 2026-09-15T04:51:00Z. Nothing before it can count.
- Review requires >=30 completed baseline serial opportunities across >=15
  contracts.
- Hypothesis must retain >=80% of baseline opportunity IDs.
- Hypothesis must retain >=90% of baseline +10c winner IDs.
- Hypothesis opportunity count must remain >=80% of baseline count.
- Hypothesis +10c precision must improve by >=5 percentage points.

Passing these conditions does NOT promote the rule. It only earns manual review
for a later independent confirmation phase. The production bot and V5/V10
shadow behavior are not modified by this module.
"""
from __future__ import annotations

import os
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_15S_PARITY_FORWARD_V1"
CUTOFF_RAW = "2026-09-15T04:51:00Z"
PARITY_MIN = 1.00
MIN_BASELINE_OPPS = 30
MIN_BASELINE_CONTRACTS = 15
MIN_OPPORTUNITY_ID_RETENTION = 0.80
MIN_WINNER_ID_RETENTION = 0.90
MIN_COUNT_RETENTION = 0.80
MIN_PRECISION_LIFT = 0.05
POLL_SEC = max(30, int(os.environ.get("SCALP_15S_PARITY_POLL_SEC", "60")))


def cutoff_dt() -> datetime:
    return research.dt(CUTOFF_RAW)


def _result_times(rows: list[Mapping[str, Any]]) -> dict[str, datetime]:
    out: dict[str, datetime] = {}
    for r in rows:
        if research.typ(r) != "RESULT":
            continue
        cid = research.cid(r)
        if not cid:
            continue
        t = research.dt(r.get("timestamp_utc"))
        if t == datetime.min.replace(tzinfo=timezone.utc):
            continue
        prev = out.get(cid)
        if prev is None or t < prev:
            out[cid] = t
    return out


def _paths(rows: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if research.typ(r) == "PATH" and research.cid(r):
            out[research.cid(r)].append(dict(r))
    return out


def fresh_candidates(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    cut = cutoff_dt()
    return [
        dict(r) for r in rows
        if research.typ(r) == "CANDIDATE"
        and research.cid(r)
        and research.contract(r)
        and research.dt(r.get("timestamp_utc")) >= cut
        and research.candidate_qualified(r)
    ]


def parity_ratio(candidate: Mapping[str, Any]) -> float | None:
    b15 = research.f(candidate.get("btc15"))
    r15 = research.f(candidate.get("brti15"))
    if b15 is None or r15 is None or b15 <= 1e-12:
        return None
    return r15 / b15


def parity_pass(candidate: Mapping[str, Any]) -> bool:
    ratio = parity_ratio(candidate)
    return bool(ratio is not None and ratio >= PARITY_MIN - 1e-12)


def build_serial(
    rows: list[Mapping[str, Any]],
    predicate: Callable[[Mapping[str, Any]], bool] | None = None,
) -> list[dict[str, Any]]:
    """Project current V5 lifecycle, optionally skipping candidates by hypothesis."""
    rows = [dict(r) for r in rows]
    results = _result_times(rows)
    paths = _paths(rows)
    by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in fresh_candidates(rows):
        by_contract[research.contract(c)].append(c)

    out: list[dict[str, Any]] = []
    for contract, candidates in by_contract.items():
        candidates.sort(key=lambda x: research.dt(x.get("timestamp_utc")))
        earliest = datetime.min.replace(tzinfo=timezone.utc)
        used: set[str] = set()
        index = 1
        while True:
            cand = next((
                c for c in candidates
                if research.cid(c) not in used
                and research.dt(c.get("timestamp_utc")) > earliest
                and (predicate is None or predicate(c))
            ), None)
            if cand is None:
                break
            cid = research.cid(cand)
            used.add(cid)
            result_time = results.get(cid)
            if result_time is None:
                # Current/incomplete accepted candidate remains current; do not
                # fabricate a terminal or skip through it.
                break

            pm = research.measure_path(cand, research.path_rows_for(cand, paths))
            terminal_kind: str
            terminal_time: datetime | None
            if pm.exit_time_utc:
                terminal_kind = "PROTECTED_EXIT"
                terminal_time = research.dt(pm.exit_time_utc)
            elif not pm.armed:
                terminal_kind = "ENDED_UNARMED"
                terminal_time = result_time
            else:
                terminal_kind = "ARMED_NO_VALIDATED_EXIT"
                terminal_time = None

            peak = pm.peak_gain
            out.append({
                "contract": contract,
                "candidate_id": cid,
                "opportunity_index": index,
                "timestamp_utc": str(cand.get("timestamp_utc") or ""),
                "side": str(cand.get("side") or "").strip().upper(),
                "btc15": research.f(cand.get("btc15")),
                "brti15": research.f(cand.get("brti15")),
                "parity_ratio": parity_ratio(cand),
                "peak_gain": peak,
                "plus10": bool(peak is not None and peak >= 0.10 - 1e-12),
                "plus20": bool(peak is not None and peak >= 0.20 - 1e-12),
                "terminal_kind": terminal_kind,
                "entry_price_is_telemetry_only": True,
                "seconds_left_is_existing_blueprint_only": True,
                "orders": False,
            })
            if terminal_time is None:
                break
            earliest = terminal_time
            index += 1
    out.sort(key=lambda r: (research.dt(r.get("timestamp_utc")), str(r.get("candidate_id") or "")))
    return out


def _rate(rows: list[Mapping[str, Any]], key: str) -> float | None:
    return None if not rows else sum(bool(r.get(key)) for r in rows) / len(rows)


def _median(rows: list[Mapping[str, Any]], key: str) -> float | None:
    vals = [float(v) for r in rows if (v := research.f(r.get(key))) is not None]
    return statistics.median(vals) if vals else None


def summarize(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    baseline = build_serial(rows)
    hypothesis = build_serial(rows, parity_pass)
    baseline_ids = {str(r.get("candidate_id") or "") for r in baseline}
    hyp_ids = {str(r.get("candidate_id") or "") for r in hypothesis}
    baseline_winners = {str(r.get("candidate_id") or "") for r in baseline if r.get("plus10")}
    hyp_winners = {str(r.get("candidate_id") or "") for r in hypothesis if r.get("plus10")}
    baseline_contracts = {str(r.get("contract") or "") for r in baseline}

    base_rate = _rate(baseline, "plus10")
    hyp_rate = _rate(hypothesis, "plus10")
    id_retention = None if not baseline_ids else len(baseline_ids & hyp_ids) / len(baseline_ids)
    winner_retention = None if not baseline_winners else len(baseline_winners & hyp_winners) / len(baseline_winners)
    count_retention = None if not baseline else len(hypothesis) / len(baseline)
    precision_lift = None if base_rate is None or hyp_rate is None else hyp_rate - base_rate

    sample_ready = bool(
        len(baseline) >= MIN_BASELINE_OPPS
        and len(baseline_contracts) >= MIN_BASELINE_CONTRACTS
    )
    acceptance_pass = bool(
        sample_ready
        and id_retention is not None and id_retention >= MIN_OPPORTUNITY_ID_RETENTION
        and winner_retention is not None and winner_retention >= MIN_WINNER_ID_RETENTION
        and count_retention is not None and count_retention >= MIN_COUNT_RETENTION
        and precision_lift is not None and precision_lift >= MIN_PRECISION_LIFT
    )
    status = "READY_FOR_MANUAL_REVIEW" if acceptance_pass else ("REVIEW_SAMPLE_READY_REJECTED" if sample_ready else "COLLECTING_FRESH_FORWARD")

    return {
        "version": VERSION,
        "status": status,
        "cutoff_utc": CUTOFF_RAW,
        "hypothesis": "brti15/btc15 >= 1.00",
        "parity_min": PARITY_MIN,
        "baseline_n": len(baseline),
        "baseline_contracts": len(baseline_contracts),
        "baseline_plus10_n": sum(bool(r.get("plus10")) for r in baseline),
        "baseline_plus10_rate": base_rate,
        "baseline_plus20_rate": _rate(baseline, "plus20"),
        "hypothesis_n": len(hypothesis),
        "hypothesis_plus10_n": sum(bool(r.get("plus10")) for r in hypothesis),
        "hypothesis_plus10_rate": hyp_rate,
        "hypothesis_plus20_rate": _rate(hypothesis, "plus20"),
        "opportunity_id_retention": id_retention,
        "winner_id_retention": winner_retention,
        "opportunity_count_retention": count_retention,
        "plus10_precision_lift": precision_lift,
        "baseline_median_parity": _median(baseline, "parity_ratio"),
        "hypothesis_median_parity": _median(hypothesis, "parity_ratio"),
        "sample_ready": sample_ready,
        "acceptance_pass": acceptance_pass,
        "minimum_baseline_opps": MIN_BASELINE_OPPS,
        "minimum_baseline_contracts": MIN_BASELINE_CONTRACTS,
        "minimum_opportunity_id_retention": MIN_OPPORTUNITY_ID_RETENTION,
        "minimum_winner_id_retention": MIN_WINNER_ID_RETENTION,
        "minimum_count_retention": MIN_COUNT_RETENTION,
        "minimum_precision_lift": MIN_PRECISION_LIFT,
        "baseline_records": baseline,
        "hypothesis_records": hypothesis,
        "research_only": True,
        "manual_execution_only": True,
        "orders": False,
        "entry_price_filter_applied": False,
        "new_fixed_time_window_applied": False,
        "protected_thresholds_changed": False,
        "stop_loss_rule_selected": False,
        "auto_promote_allowed": False,
        "actionable_now": False,
        "production_behavior_changed": False,
        "note": (
            "Fresh-forward single-hypothesis shadow only. Passing earns manual review, "
            "not promotion. Existing V5/V10 and production remain unchanged."
        ),
    }


def _fmt(v: Any, digits: int = 3) -> str:
    if v is None:
        return "NA"
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return str(v)


def cycle() -> dict[str, Any]:
    rows, sha = forward.fetch_csv_rows()
    s = summarize(rows)
    print(
        "SCALP 15S PARITY FORWARD | "
        f"status={s['status']} | cutoff={s['cutoff_utc']} | "
        f"base={s['baseline_n']} opps/{s['baseline_contracts']} contracts | base_+10={_fmt(s['baseline_plus10_rate'])} | "
        f"parity={s['hypothesis_n']} | parity_+10={_fmt(s['hypothesis_plus10_rate'])} | "
        f"lift={_fmt(s['plus10_precision_lift'])} | id_ret={_fmt(s['opportunity_id_retention'])} | "
        f"winner_ret={_fmt(s['winner_id_retention'])} | count_ret={_fmt(s['opportunity_count_retention'])} | "
        f"sample_ready={s['sample_ready']} | pass={s['acceptance_pass']} | source_sha256={sha} | "
        "FRESH FORWARD SHADOW | NO AUTO-PROMOTE | NO ORDERS",
        flush=True,
    )
    return s


def main() -> int:
    print(
        f"{VERSION} START | cutoff={CUTOFF_RAW} | hypothesis=brti15/btc15>=1.00 | "
        "FRESH FORWARD SHADOW | READ ONLY | SIGNAL ONLY | NO ORDERS",
        flush=True,
    )
    while True:
        try:
            cycle()
        except Exception as exc:
            print(
                f"SCALP 15S PARITY FORWARD ERROR | {type(exc).__name__}: {exc} | "
                "RETRYING | NO ORDERS",
                flush=True,
            )
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
