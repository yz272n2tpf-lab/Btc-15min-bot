#!/usr/bin/env python3
"""
BTC15 scalp ladder selector V1.

RESEARCH ONLY | VALIDATION SELECTS | REPORT_ONLY CONFIRMS | NO ORDERS

Implements the pre-frozen mechanical gates in
BTC15_SCALP_LADDER_SELECTION_FREEZE_V1.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

MIN_N = 12
SECONDARY_PLUS5_MIN = 0.80
SECONDARY_PLUS10_MIN = 0.60
SECONDARY_MEDIAN_PEAK_MIN = 0.10
SECONDARY_AVG_ADVERSE_MIN = -0.10
FAILED_RECOVERY_MAX = 0.15
FAILED_MEDIAN_BEST_MAX = 0.05


def f(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, str) and not v.strip():
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def b(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def avg(xs):
    vals = [float(x) for x in xs if x is not None]
    return statistics.fmean(vals) if vals else None


def med(xs):
    vals = [float(x) for x in xs if x is not None]
    return statistics.median(vals) if vals else None


def pct(n, d):
    return None if not d else n / d


def opportunity_metrics(rows: list[dict[str, str]]) -> dict:
    n = len(rows)
    plus5 = sum(f(r.get("t5_sec")) is not None for r in rows)
    plus10 = sum(f(r.get("t10_sec")) is not None for r in rows)
    return {
        "n": n,
        "plus5_rate": pct(plus5, n),
        "plus10_rate": pct(plus10, n),
        "median_peak_gain": med(f(r.get("peak_gain")) for r in rows),
        "avg_adverse_gain": avg(f(r.get("adverse_gain")) for r in rows),
    }


def opportunity_viable(m: dict) -> bool:
    return bool(
        m["n"] >= MIN_N
        and m["plus5_rate"] is not None and m["plus5_rate"] >= SECONDARY_PLUS5_MIN
        and m["plus10_rate"] is not None and m["plus10_rate"] >= SECONDARY_PLUS10_MIN
        and m["median_peak_gain"] is not None and m["median_peak_gain"] >= SECONDARY_MEDIAN_PEAK_MIN
        and m["avg_adverse_gain"] is not None and m["avg_adverse_gain"] >= SECONDARY_AVG_ADVERSE_MIN
    )


def failed_cell_metrics(rows: list[dict[str, str]]) -> dict:
    n = len(rows)
    recover = sum(b(r.get("would_recover_to_plus5")) for r in rows)
    return {
        "n": n,
        "recover_plus5_rate": pct(recover, n),
        "avg_gain_at_trigger": avg(f(r.get("gain_at_trigger")) for r in rows),
        "median_best_after_trigger": med(f(r.get("best_gain_after_trigger")) for r in rows),
    }


def failed_eligible(m: dict) -> bool:
    return bool(
        m["n"] >= MIN_N
        and m["recover_plus5_rate"] is not None and m["recover_plus5_rate"] <= FAILED_RECOVERY_MAX
        and m["median_best_after_trigger"] is not None and m["median_best_after_trigger"] < FAILED_MEDIAN_BEST_MAX
        and m["avg_gain_at_trigger"] is not None
    )


def select_failed(validation_rows: list[dict[str, str]]) -> tuple[dict | None, list[dict]]:
    groups = defaultdict(list)
    for r in validation_rows:
        adv = f(r.get("adverse_trigger_cents"))
        elapsed = f(r.get("min_elapsed_sec"))
        if adv is None or elapsed is None:
            continue
        groups[(adv, elapsed)].append(r)

    scored = []
    for (adv, elapsed), rows in groups.items():
        m = failed_cell_metrics(rows)
        rec = {
            "adverse_trigger_cents": adv,
            "min_elapsed_sec": elapsed,
            **m,
            "eligible": failed_eligible(m),
        }
        scored.append(rec)

    eligible = [x for x in scored if x["eligible"]]
    if not eligible:
        return None, sorted(scored, key=lambda x: (x["adverse_trigger_cents"], x["min_elapsed_sec"]))

    # Frozen tie-break order:
    # 1) lowest recovery; 2) least-negative trigger gain = numerically highest;
    # 3) shortest elapsed; 4) smallest adverse threshold.
    chosen = sorted(
        eligible,
        key=lambda x: (
            x["recover_plus5_rate"],
            -x["avg_gain_at_trigger"],
            x["min_elapsed_sec"],
            x["adverse_trigger_cents"],
        ),
    )[0]
    return chosen, sorted(scored, key=lambda x: (x["adverse_trigger_cents"], x["min_elapsed_sec"]))


def matching_failed(rows, chosen):
    if not chosen:
        return []
    a = chosen["adverse_trigger_cents"]
    e = chosen["min_elapsed_sec"]
    return [
        r for r in rows
        if f(r.get("adverse_trigger_cents")) == a and f(r.get("min_elapsed_sec")) == e
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--opportunities", default="scalp_ladder_research_v1_opportunities.csv")
    ap.add_argument("--failed-grid", default="scalp_failed_primary_grid_v1.csv")
    ap.add_argument("--out", default="scalp_ladder_selection_v1.json")
    args = ap.parse_args()

    opps = read_csv(Path(args.opportunities))
    failed = read_csv(Path(args.failed_grid))

    opp_result = {}
    for idx, name in ((2, "secondary"), (3, "tertiary")):
        val = [r for r in opps if r.get("split") == "VALIDATION" and int(float(r.get("opportunity_index") or 0)) == idx]
        rep = [r for r in opps if r.get("split") == "REPORT_ONLY" and int(float(r.get("opportunity_index") or 0)) == idx]
        vm = opportunity_metrics(val)
        rm = opportunity_metrics(rep)
        opp_result[name] = {
            "rule": f"first frozen-qualified opportunity #{idx} after prior protected EXIT",
            "validation": vm,
            "validation_viable": opportunity_viable(vm),
            "report_only": rm,
            "report_only_confirmation_only": True,
            "requires_20_new_forward": True,
            "actionable_now": False,
        }

    val_failed = [r for r in failed if r.get("split") == "VALIDATION"]
    rep_failed = [r for r in failed if r.get("split") == "REPORT_ONLY"]
    chosen, all_cells = select_failed(val_failed)
    report_confirmation = failed_cell_metrics(matching_failed(rep_failed, chosen)) if chosen else None

    result = {
        "version": "BTC15_SCALP_LADDER_SELECTOR_V1",
        "research_only": True,
        "orders": False,
        "protected_primary_changed": False,
        "report_only_used_for_selection": False,
        "opportunities": opp_result,
        "failed_primary": {
            "validation_selected_cell": chosen,
            "validation_cells": all_cells,
            "report_only_same_cell_confirmation": report_confirmation,
            "requires_freeze_before_forward": chosen is not None,
            "requires_20_new_forward": chosen is not None,
            "actionable_now": False,
        },
    }

    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
