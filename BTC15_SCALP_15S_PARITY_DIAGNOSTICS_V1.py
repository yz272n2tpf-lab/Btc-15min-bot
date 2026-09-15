#!/usr/bin/env python3
"""
BTC15 SCALP 15-second parity diagnostic observer V1.

READ ONLY | FRESH FORWARD SHADOW | SIGNAL ONLY | NO ORDERS

This wraps the already-frozen BTC15_SCALP_15S_PARITY_FORWARD_V1 hypothesis.
It does not alter the cutoff, parity threshold, serial lifecycle, acceptance
criteria, production bot, V5, or V10. It only exposes why baseline fresh
opportunities are absent from the parity projection, with special emphasis on
baseline +10c winners lost by the hypothesis.
"""
from __future__ import annotations

import json
import time
from typing import Any, Mapping

import BTC15_SCALP_15S_PARITY_FORWARD_V1 as base

VERSION = "BTC15_SCALP_15S_PARITY_DIAGNOSTICS_V1"


def _diag_record(r: Mapping[str, Any]) -> dict[str, Any]:
    ratio = base.parity_ratio(r)
    return {
        "candidate_id": str(r.get("candidate_id") or ""),
        "contract": str(r.get("contract") or ""),
        "opportunity_index": r.get("opportunity_index"),
        "timestamp_utc": str(r.get("timestamp_utc") or ""),
        "side": str(r.get("side") or ""),
        "btc15": r.get("btc15"),
        "brti15": r.get("brti15"),
        "parity_ratio": ratio,
        "direct_parity_pass": bool(ratio is not None and ratio >= base.PARITY_MIN - 1e-12),
        "plus10": bool(r.get("plus10")),
        "plus20": bool(r.get("plus20")),
        "terminal_kind": str(r.get("terminal_kind") or ""),
    }


def diagnostics(summary: Mapping[str, Any]) -> dict[str, Any]:
    baseline = [dict(r) for r in (summary.get("baseline_records") or [])]
    hypothesis = [dict(r) for r in (summary.get("hypothesis_records") or [])]
    hyp_ids = {str(r.get("candidate_id") or "") for r in hypothesis}

    direct_rejected = [
        _diag_record(r) for r in baseline
        if not base.parity_pass(r)
    ]
    lost_winners = [
        _diag_record(r) for r in baseline
        if bool(r.get("plus10")) and str(r.get("candidate_id") or "") not in hyp_ids
    ]
    retained_winners = [
        _diag_record(r) for r in baseline
        if bool(r.get("plus10")) and str(r.get("candidate_id") or "") in hyp_ids
    ]

    # Most recent first for compact live review.
    direct_rejected.sort(key=lambda r: (r.get("timestamp_utc") or "", r.get("candidate_id") or ""), reverse=True)
    lost_winners.sort(key=lambda r: (r.get("timestamp_utc") or "", r.get("candidate_id") or ""), reverse=True)
    retained_winners.sort(key=lambda r: (r.get("timestamp_utc") or "", r.get("candidate_id") or ""), reverse=True)

    return {
        "version": VERSION,
        "cutoff_utc": summary.get("cutoff_utc"),
        "hypothesis": summary.get("hypothesis"),
        "baseline_n": len(baseline),
        "hypothesis_n": len(hypothesis),
        "direct_rejected_n": len(direct_rejected),
        "lost_plus10_winners_n": len(lost_winners),
        "retained_plus10_winners_n": len(retained_winners),
        "direct_rejected": direct_rejected,
        "lost_plus10_winners": lost_winners,
        "retained_plus10_winners": retained_winners,
        "research_only": True,
        "manual_execution_only": True,
        "orders": False,
        "actionable_now": False,
        "production_behavior_changed": False,
    }


def _print_detail(d: Mapping[str, Any], source_sha: str) -> None:
    rejected = list(d.get("direct_rejected") or [])[:5]
    lost = list(d.get("lost_plus10_winners") or [])[:5]
    print(
        "SCALP 15S PARITY DIAGNOSTICS | "
        f"base={d.get('baseline_n')} | parity={d.get('hypothesis_n')} | "
        f"direct_rejected={d.get('direct_rejected_n')} | "
        f"lost_+10_winners={d.get('lost_plus10_winners_n')} | "
        f"retained_+10_winners={d.get('retained_plus10_winners_n')} | "
        f"source_sha256={source_sha} | READ ONLY | NO ORDERS",
        flush=True,
    )
    print(
        "SCALP 15S PARITY REJECT DETAIL | "
        f"latest={json.dumps(rejected, separators=(',', ':'))} | "
        "FRESH FORWARD ONLY | NO RULE CHANGE | NO ORDERS",
        flush=True,
    )
    if lost:
        print(
            "SCALP 15S PARITY LOST WINNER ALERT | "
            f"latest={json.dumps(lost, separators=(',', ':'))} | "
            "RESEARCH WARNING ONLY | NO AUTO-PROMOTE | NO ORDERS",
            flush=True,
        )


def main() -> int:
    print(
        f"{VERSION} START | wraps={base.VERSION} | cutoff={base.CUTOFF_RAW} | "
        "READ ONLY | FRESH FORWARD SHADOW | SIGNAL ONLY | NO ORDERS",
        flush=True,
    )
    last_sig = None
    while True:
        try:
            rows, sha = base.forward.fetch_csv_rows()
            s = base.summarize(rows)
            # Preserve the frozen validator's aggregate line each cycle.
            print(
                "SCALP 15S PARITY FORWARD | "
                f"status={s['status']} | cutoff={s['cutoff_utc']} | "
                f"base={s['baseline_n']} opps/{s['baseline_contracts']} contracts | "
                f"base_+10={base._fmt(s['baseline_plus10_rate'])} | "
                f"parity={s['hypothesis_n']} | parity_+10={base._fmt(s['hypothesis_plus10_rate'])} | "
                f"lift={base._fmt(s['plus10_precision_lift'])} | "
                f"winner_ret={base._fmt(s['winner_id_retention'])} | "
                f"count_ret={base._fmt(s['opportunity_count_retention'])} | "
                f"sample_ready={s['sample_ready']} | pass={s['acceptance_pass']} | "
                f"source_sha256={sha} | FRESH FORWARD SHADOW | NO AUTO-PROMOTE | NO ORDERS",
                flush=True,
            )
            d = diagnostics(s)
            sig = (
                d["baseline_n"],
                d["hypothesis_n"],
                d["direct_rejected_n"],
                d["lost_plus10_winners_n"],
                d["retained_plus10_winners_n"],
            )
            if sig != last_sig:
                _print_detail(d, sha)
                last_sig = sig
        except Exception as exc:
            print(
                f"SCALP 15S PARITY DIAGNOSTICS ERROR | {type(exc).__name__}: {exc} | "
                "RETRYING | NO ORDERS",
                flush=True,
            )
        time.sleep(base.POLL_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
