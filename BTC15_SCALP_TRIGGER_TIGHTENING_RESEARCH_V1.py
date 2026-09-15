#!/usr/bin/env python3
"""
BTC15 SCALP trigger-tightening research V1.

RESEARCH ONLY | READ ONLY | SIGNAL ONLY | NO ORDERS

Purpose
-------
Study why some serial SCALP selections do not produce the user's meaningful
~10c move, without changing the confirmed blueprint or suppressing valid cheap
scalps by price.

This V1 deliberately tests only one existing signal-strength dimension:
side-aligned BTC 30-second movement (btc30). It does NOT create a Kalshi price
filter and it does NOT create a fixed time window. Entry price and seconds-left
are telemetry only.

Method
------
- Start from the research serial lifecycle that can reset after protected EXIT
  and after completed ENDED_UNARMED lifecycle terminals.
- Split chronologically by contract: first 60% DEVELOPMENT, last 40% HOLDOUT.
- Sweep btc30 minimums: 15/20/25/30/40/50/75/100.
- A DEVELOPMENT candidate may be named for HOLDOUT review only when it retains
  >=90% of DEVELOPMENT +10c winners and has enough sample. That is a research
  nomination, never an automatic strategy promotion.
- Report HOLDOUT precision and winner retention for the nominated threshold.

The existing +5c arm / first 4c giveback EXIT remains untouched.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import BTC15_SCALP_UNARMED_TERMINAL_HANDOFF_AUDIT_V1 as lifecycle
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_TRIGGER_TIGHTENING_RESEARCH_V1"
BTC30_THRESHOLDS = (15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 75.0, 100.0)
DEV_WINNER_RETENTION_MIN = 0.90
MIN_DEV_N = 10
MIN_HOLDOUT_N = 6


def _records(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(r) for r in rows]
    projected = lifecycle.audit(rows).get("projected_ladder") or []
    cands = {
        research.cid(c): c
        for c in forward.forward_candidates(rows)
        if research.cid(c)
    }
    out: list[dict[str, Any]] = []
    for p in projected:
        cid = str(p.get("candidate_id") or "")
        c = cands.get(cid)
        if c is None:
            continue
        out.append({
            "contract": str(p.get("contract") or research.contract(c)),
            "candidate_id": cid,
            "timestamp_utc": str(c.get("timestamp_utc") or ""),
            "side": str(p.get("side") or c.get("side") or "").upper(),
            "btc30": research.f(p.get("btc30")) if p.get("btc30") is not None else research.f(c.get("btc30")),
            "seconds_left": research.f(p.get("seconds_left")) if p.get("seconds_left") is not None else research.f(c.get("seconds_left")),
            "entry_ask": research.f(p.get("entry_ask")) if p.get("entry_ask") is not None else research.f(c.get("entry_ask")),
            "peak_gain": research.f(p.get("peak_gain")),
            "plus10": bool(p.get("plus10")),
            "plus20": bool(p.get("plus20")),
            "price_is_telemetry_only": True,
            "seconds_left_is_telemetry_only": True,
        })
    out.sort(key=lambda r: research.dt(r.get("timestamp_utc")))
    return out


def _contract_split(records: list[Mapping[str, Any]]) -> dict[str, str]:
    first: dict[str, datetime] = {}
    for r in records:
        c = str(r.get("contract") or "")
        if not c:
            continue
        t = research.dt(r.get("timestamp_utc"))
        if c not in first or t < first[c]:
            first[c] = t
    ordered = sorted(first, key=lambda c: first[c])
    cut = max(1, min(len(ordered), int(round(len(ordered) * 0.60)))) if ordered else 0
    return {c: ("DEVELOPMENT" if i < cut else "HOLDOUT") for i, c in enumerate(ordered)}


def _metrics(records: list[Mapping[str, Any]], threshold: float) -> dict[str, Any]:
    baseline = [r for r in records if r.get("btc30") is not None and float(r["btc30"]) >= 15.0]
    kept = [r for r in baseline if float(r["btc30"]) >= threshold]
    base_winners = [r for r in baseline if r.get("plus10")]
    kept_winners = [r for r in kept if r.get("plus10")]
    return {
        "btc30_min": threshold,
        "n": len(kept),
        "plus10_n": len(kept_winners),
        "plus10_rate": None if not kept else len(kept_winners) / len(kept),
        "plus20_rate": None if not kept else sum(bool(r.get("plus20")) for r in kept) / len(kept),
        "plus10_winner_retention": None if not base_winners else len(kept_winners) / len(base_winners),
        "selected_share_retained": None if not baseline else len(kept) / len(baseline),
    }


def analyze_records(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    records = [dict(r) for r in records]
    split = _contract_split(records)
    dev = [r for r in records if split.get(str(r.get("contract") or "")) == "DEVELOPMENT"]
    hold = [r for r in records if split.get(str(r.get("contract") or "")) == "HOLDOUT"]

    dev_rows = [_metrics(dev, t) for t in BTC30_THRESHOLDS]
    baseline = next((x for x in dev_rows if x["btc30_min"] == 15.0), None)
    eligible = [
        x for x in dev_rows
        if x["btc30_min"] > 15.0
        and x["n"] >= MIN_DEV_N
        and x["plus10_winner_retention"] is not None
        and x["plus10_winner_retention"] >= DEV_WINNER_RETENTION_MIN
        and baseline is not None
        and x["plus10_rate"] is not None
        and baseline["plus10_rate"] is not None
        and x["plus10_rate"] > baseline["plus10_rate"]
    ]
    eligible.sort(
        key=lambda x: (
            float(x.get("plus10_rate") or 0.0),
            float(x.get("plus10_winner_retention") or 0.0),
            -float(x.get("btc30_min") or 0.0),
        ),
        reverse=True,
    )
    nominee = eligible[0] if eligible else None
    nominee_threshold = None if nominee is None else float(nominee["btc30_min"])
    holdout_nominee = None if nominee_threshold is None else _metrics(hold, nominee_threshold)
    holdout_baseline = _metrics(hold, 15.0)

    holdout_review_ready = bool(
        nominee_threshold is not None
        and holdout_nominee is not None
        and int(holdout_nominee.get("n") or 0) >= MIN_HOLDOUT_N
    )

    return {
        "version": VERSION,
        "research_only": True,
        "orders": False,
        "manual_execution_only": True,
        "entry_price_filter_applied": False,
        "price_is_telemetry_only": True,
        "fixed_time_window_applied": False,
        "seconds_left_is_telemetry_only": True,
        "protected_thresholds_changed": False,
        "stop_loss_rule_selected": False,
        "records_n": len(records),
        "development_n": len(dev),
        "holdout_n": len(hold),
        "development_thresholds": dev_rows,
        "development_nominee_btc30_min": nominee_threshold,
        "development_nominee": nominee,
        "holdout_baseline": holdout_baseline,
        "holdout_nominee": holdout_nominee,
        "holdout_review_ready": holdout_review_ready,
        "auto_promote_allowed": False,
        "actionable_now": False,
        "note": (
            "A nominee only earns HOLDOUT review. Do not promote it unless fresh holdout "
            "evidence improves 10c precision without materially sacrificing real 10c opportunities."
        ),
    }


def audit(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    out = analyze_records(_records(rows))
    out["source"] = "ENDED_UNARMED_SERIAL_LIFECYCLE_PROJECTION"
    return out


if __name__ == "__main__":
    print(f"{VERSION} | import/use audit(rows) | RESEARCH ONLY | NO ORDERS")
