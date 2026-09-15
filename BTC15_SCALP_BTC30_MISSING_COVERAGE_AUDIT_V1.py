#!/usr/bin/env python3
"""
BTC15 SCALP BTC30-missing coverage audit V1.

DESCRIPTIVE / HYPOTHESIS GENERATION ONLY | READ ONLY | NO ORDERS

Measures completed raw collector candidates that the frozen V5 adapter rejects
because btc30 is missing while side and >=120s timing are otherwise valid.
This does NOT change the frozen btc30>=15 rule and does NOT promote a rule.
Price is telemetry only.
"""
from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from typing import Any, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import btc15_scalp_blueprint_forward_v1 as forward
from btc15_protected_module_adapter_v1 import scalp_state_from_events

VERSION = "BTC15_SCALP_BTC30_MISSING_COVERAGE_AUDIT_V1"


def f(v: Any) -> float | None:
    return research.f(v)


def price_band(ask: float | None) -> str:
    if ask is None: return "unknown"
    c = ask * 100
    if c < 25: return "<25c"
    if c <= 35: return "25-35c"
    if c <= 50: return "36-50c"
    return ">50c"


def audit(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    done = forward.completed_ids(rows)
    cands = forward.forward_candidates(rows)
    paths: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if research.typ(r) == "PATH" and research.cid(r):
            paths[research.cid(r)].append(dict(r))

    rejected_missing: list[dict[str, Any]] = []
    for c in cands:
        cid = research.cid(c)
        if not cid or cid not in done:
            continue
        baseline = scalp_state_from_events(c, ()).state != "PASS"
        side = str(c.get("side") or "").strip().upper()
        left = f(c.get("seconds_left"))
        b30 = f(c.get("btc30"))
        if baseline or side not in {"UP", "DOWN"} or left is None or left < 120 or b30 is not None:
            continue
        pm = research.measure_path(c, research.path_rows_for(c, paths))
        ask = f(c.get("entry_ask"))
        rejected_missing.append({
            "contract": research.contract(c),
            "candidate_id": cid,
            "timestamp_utc": str(c.get("timestamp_utc") or ""),
            "side": side,
            "entry_ask": ask,
            "entry_band": price_band(ask),
            "entry_at_or_below_50c": bool(ask is not None and ask <= 0.50 + 1e-12),
            "seconds_left": left,
            "first_minute": bool(left >= 840.0),
            "btc5": f(c.get("btc5")),
            "btc15": f(c.get("btc15")),
            "btc30": None,
            "brti5": f(c.get("brti5")),
            "brti15": f(c.get("brti15")),
            "peak_gain": pm.peak_gain,
            "adverse_gain": pm.adverse_gain,
            "armed_plus5": pm.armed,
            "plus10": bool(pm.peak_gain is not None and pm.peak_gain >= 0.10),
            "plus20": bool(pm.peak_gain is not None and pm.peak_gain >= 0.20),
            "protected_exit_gain": pm.exit_gain,
        })

    n = len(rejected_missing)
    bands = Counter(r["entry_band"] for r in rejected_missing)
    plus10_n = sum(r["plus10"] for r in rejected_missing)
    plus20_n = sum(r["plus20"] for r in rejected_missing)
    armed_n = sum(r["armed_plus5"] for r in rejected_missing)
    first_minute_n = sum(r["first_minute"] for r in rejected_missing)
    le50_n = sum(r["entry_at_or_below_50c"] for r in rejected_missing)
    peaks = [float(r["peak_gain"]) for r in rejected_missing if r["peak_gain"] is not None]
    adverse = [float(r["adverse_gain"]) for r in rejected_missing if r["adverse_gain"] is not None]

    return {
        "version": VERSION,
        "research_only": True,
        "hypothesis_generation_only": True,
        "orders": False,
        "manual_execution_only": True,
        "frozen_v5_rule_changed": False,
        "rule_selected": False,
        "price_filter_applied": False,
        "completed_missing_btc30_rejects": n,
        "unique_contracts": len({r["contract"] for r in rejected_missing}),
        "first_minute_n": first_minute_n,
        "first_minute_rate": None if not n else first_minute_n / n,
        "entry_at_or_below_50c_n": le50_n,
        "entry_at_or_below_50c_rate": None if not n else le50_n / n,
        "armed_plus5_n": armed_n,
        "armed_plus5_rate": None if not n else armed_n / n,
        "plus10_n": plus10_n,
        "plus10_rate": None if not n else plus10_n / n,
        "plus20_n": plus20_n,
        "plus20_rate": None if not n else plus20_n / n,
        "median_peak_gain": None if not peaks else statistics.median(peaks),
        "median_adverse_gain": None if not adverse else statistics.median(adverse),
        "entry_bands": dict(sorted(bands.items())),
        "records": rejected_missing,
        "note": (
            "Descriptive only. If the group is materially strong, predeclare a fresh-forward "
            "missing-btc30 hypothesis before changing V5. Do not validate on this same tape."
        ),
    }


def main() -> int:
    rows, sha = forward.fetch_csv_rows()
    out = audit(rows)
    out["source_sha256"] = sha
    print(
        "BTC30 MISSING COVERAGE | "
        f"n={out['completed_missing_btc30_rejects']} | contracts={out['unique_contracts']} | "
        f"first_min={out['first_minute_n']} | <=50c={out['entry_at_or_below_50c_n']} | "
        f"+5={out['armed_plus5_n']} | +10={out['plus10_n']} | +20={out['plus20_n']} | "
        f"median_peak={out['median_peak_gain']} | median_adverse={out['median_adverse_gain']} | "
        "DESCRIPTIVE ONLY | RULE UNCHANGED | NO ORDERS",
        flush=True,
    )
    print(json.dumps(out, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
