#!/usr/bin/env python3
"""
BTC15 multi-opportunity scalp ladder research V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Reads the existing generalized scalp event CSV without modifying it.
Protected primary logic is reproduced exactly:
  seconds_left >= 120
  side-aligned btc30 >= 15
  no entry-price filter
  arm +5c
  protected exit at 4c giveback from running executable peak

V1 then describes:
1) later frozen-qualified candidates that occur only AFTER the prior displayed
   scalp reaches protected EXIT (secondary / tertiary ladder), and
2) pre-arm failed PRIMARY paths across the pre-frozen adverse/time grid.

No thresholds are promoted by this script and REPORT_ONLY is never used to
select a rule.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

SCALP_MIN_SECONDS_LEFT = 120.0
SCALP_MIN_BTC30 = 15.0
SCALP_ARM_GAIN = 0.05
SCALP_GIVEBACK = 0.04
ADVERSE_LEVELS = (0.03, 0.05, 0.07, 0.10)
MIN_ELAPSED = (10.0, 20.0, 30.0, 45.0, 60.0)


def f(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, str) and not v.strip():
        return None
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def dt(v: Any) -> datetime:
    raw = str(v or "").strip()
    if not raw:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        x = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if x.tzinfo is None:
            x = x.replace(tzinfo=timezone.utc)
        return x.astimezone(timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def typ(row: Mapping[str, Any]) -> str:
    return str(row.get("record_type") or "").strip().upper()


def contract(row: Mapping[str, Any]) -> str:
    return str(row.get("contract") or "").strip()


def cid(row: Mapping[str, Any]) -> str:
    return str(row.get("candidate_id") or "").strip()


def candidate_qualified(row: Mapping[str, Any]) -> bool:
    side = str(row.get("side") or "").strip().upper()
    left = f(row.get("seconds_left"))
    btc30 = f(row.get("btc30"))
    return bool(
        side in {"UP", "DOWN"}
        and left is not None and left >= SCALP_MIN_SECONDS_LEFT
        and btc30 is not None and btc30 >= SCALP_MIN_BTC30
    )


def elapsed(row: Mapping[str, Any], candidate_time: datetime) -> float | None:
    e = f(row.get("elapsed_sec"))
    if e is not None:
        return max(0.0, e)
    t = dt(row.get("timestamp_utc"))
    if t != datetime.min.replace(tzinfo=timezone.utc) and candidate_time != datetime.min.replace(tzinfo=timezone.utc):
        return max(0.0, (t - candidate_time).total_seconds())
    return None


def path_rows_for(candidate: Mapping[str, Any], paths_by_cid: Mapping[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    key = cid(candidate)
    ctime = dt(candidate.get("timestamp_utc"))
    rows = list(paths_by_cid.get(key, ()))
    rows.sort(key=lambda r: (elapsed(r, ctime) if elapsed(r, ctime) is not None else float("inf"), dt(r.get("timestamp_utc"))))
    return rows


@dataclass
class PathMetrics:
    peak_gain: float | None = None
    adverse_gain: float | None = None
    armed: bool = False
    exit_gain: float | None = None
    exit_elapsed_sec: float | None = None
    exit_time_utc: str | None = None
    t5_sec: float | None = None
    t10_sec: float | None = None
    t15_sec: float | None = None
    t20_sec: float | None = None


def measure_path(candidate: Mapping[str, Any], rows: Iterable[Mapping[str, Any]]) -> PathMetrics:
    ctime = dt(candidate.get("timestamp_utc"))
    peak = None
    adverse = None
    armed = False
    out = PathMetrics()
    targets = ((0.05, "t5_sec"), (0.10, "t10_sec"), (0.15, "t15_sec"), (0.20, "t20_sec"))

    for row in rows:
        gain = f(row.get("exec_gain"))
        e = elapsed(row, ctime)
        if gain is None or e is None:
            continue
        peak = gain if peak is None else max(peak, gain)
        adverse = gain if adverse is None else min(adverse, gain)
        for target, attr in targets:
            if getattr(out, attr) is None and gain >= target:
                setattr(out, attr, e)
        if peak >= SCALP_ARM_GAIN:
            armed = True
        if armed and peak - gain >= SCALP_GIVEBACK - 1e-12:
            out.exit_gain = gain
            out.exit_elapsed_sec = e
            t = dt(row.get("timestamp_utc"))
            if t == datetime.min.replace(tzinfo=timezone.utc):
                t = ctime + timedelta(seconds=e)
            out.exit_time_utc = t.isoformat()
            break

    # Keep full-path peak/adverse even when protected EXIT happens early; this is
    # useful descriptive context, not a change to realized management.
    all_gains = [f(r.get("exec_gain")) for r in rows]
    all_gains = [x for x in all_gains if x is not None]
    if all_gains:
        out.peak_gain = max(all_gains)
        out.adverse_gain = min(all_gains)
    else:
        out.peak_gain = peak
        out.adverse_gain = adverse
    out.armed = bool(out.peak_gain is not None and out.peak_gain >= SCALP_ARM_GAIN)
    return out


def split_contracts(candidates_by_contract: Mapping[str, list[dict[str, str]]]) -> dict[str, str]:
    ordered = []
    for c, rows in candidates_by_contract.items():
        if not rows:
            continue
        ordered.append((min(dt(r.get("timestamp_utc")) for r in rows), c))
    ordered.sort()
    cut = len(ordered) // 2
    return {c: ("VALIDATION" if i < cut else "REPORT_ONLY") for i, (_, c) in enumerate(ordered)}


def pct(n: int, d: int) -> str:
    return "—" if not d else f"{100.0*n/d:.1f}%"


def med(values: Iterable[float | None]) -> float | None:
    xs = [float(x) for x in values if x is not None]
    return statistics.median(xs) if xs else None


def avg(values: Iterable[float | None]) -> float | None:
    xs = [float(x) for x in values if x is not None]
    return statistics.fmean(xs) if xs else None


def fmtc(x: float | None) -> str:
    return "—" if x is None else f"{100*x:+.2f}c"


def build_opportunity_ladder(
    candidates_by_contract: Mapping[str, list[dict[str, str]]],
    paths_by_cid: Mapping[str, list[dict[str, str]]],
    split_map: Mapping[str, str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c, all_candidates in candidates_by_contract.items():
        qualified = [x for x in sorted(all_candidates, key=lambda r: dt(r.get("timestamp_utc"))) if candidate_qualified(x)]
        if not qualified:
            continue
        earliest_allowed = datetime.min.replace(tzinfo=timezone.utc)
        opp_index = 1
        used: set[str] = set()
        while opp_index <= 3:
            cand = next((x for x in qualified if cid(x) not in used and dt(x.get("timestamp_utc")) > earliest_allowed), None)
            if cand is None:
                break
            used.add(cid(cand))
            pm = measure_path(cand, path_rows_for(cand, paths_by_cid))
            rec = {
                "split": split_map.get(c, ""),
                "contract": c,
                "opportunity_index": opp_index,
                "candidate_id": cid(cand),
                "timestamp_utc": str(cand.get("timestamp_utc") or ""),
                "side": str(cand.get("side") or "").upper(),
                "entry_ask": f(cand.get("entry_ask")),
                "seconds_left": f(cand.get("seconds_left")),
                "btc30": f(cand.get("btc30")),
                **asdict(pm),
            }
            out.append(rec)
            # A later opportunity is eligible in V1 only after protected EXIT.
            if pm.exit_time_utc is None:
                break
            earliest_allowed = dt(pm.exit_time_utc)
            opp_index += 1
    return out


def build_failed_primary_grid(
    candidates_by_contract: Mapping[str, list[dict[str, str]]],
    paths_by_cid: Mapping[str, list[dict[str, str]]],
    split_map: Mapping[str, str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c, all_candidates in candidates_by_contract.items():
        qualified = [x for x in sorted(all_candidates, key=lambda r: dt(r.get("timestamp_utc"))) if candidate_qualified(x)]
        if not qualified:
            continue
        primary = qualified[0]
        rows = path_rows_for(primary, paths_by_cid)
        pm = measure_path(primary, rows)
        if pm.armed:
            continue
        ctime = dt(primary.get("timestamp_utc"))
        timeline = []
        for row in rows:
            e = elapsed(row, ctime)
            g = f(row.get("exec_gain"))
            if e is not None and g is not None:
                timeline.append((e, g))
        if not timeline:
            continue
        timeline.sort()
        for adverse in ADVERSE_LEVELS:
            for min_e in MIN_ELAPSED:
                trig_idx = next((i for i, (e, g) in enumerate(timeline) if e >= min_e and g <= -adverse), None)
                if trig_idx is None:
                    continue
                te, tg = timeline[trig_idx]
                future = [g for _, g in timeline[trig_idx:]]
                best_after = max(future) if future else None
                out.append({
                    "split": split_map.get(c, ""),
                    "contract": c,
                    "candidate_id": cid(primary),
                    "side": str(primary.get("side") or "").upper(),
                    "entry_ask": f(primary.get("entry_ask")),
                    "entry_seconds_left": f(primary.get("seconds_left")),
                    "adverse_trigger_cents": round(adverse * 100, 4),
                    "min_elapsed_sec": min_e,
                    "trigger_elapsed_sec": te,
                    "gain_at_trigger": tg,
                    "best_gain_after_trigger": best_after,
                    "would_recover_to_plus5": bool(best_after is not None and best_after >= SCALP_ARM_GAIN),
                    "full_peak_gain": pm.peak_gain,
                    "full_adverse_gain": pm.adverse_gain,
                })
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader(); w.writerows(rows)


def summary_text(opps: list[dict[str, Any]], failed: list[dict[str, Any]]) -> str:
    lines = [
        "BTC15 SCALP LADDER RESEARCH V1",
        "RESEARCH ONLY | SIGNAL ONLY | NO ORDERS",
        "Protected primary rule unchanged: >=120s, btc30>=15, no price filter, +5c arm, 4c giveback EXIT.",
        "",
        "MULTI-OPPORTUNITY LADDER (only after prior protected EXIT)",
    ]
    for split in ("VALIDATION", "REPORT_ONLY"):
        lines.append(f"[{split}]")
        for idx in (1, 2, 3):
            rows = [r for r in opps if r["split"] == split and r["opportunity_index"] == idx]
            n = len(rows)
            if not n:
                lines.append(f"  opp{idx}: n=0")
                continue
            hits = {t: sum(r[f"t{t}_sec"] is not None for r in rows) for t in (5, 10, 15, 20)}
            exited = [r for r in rows if r["exit_gain"] is not None]
            lines.append(
                f"  opp{idx}: n={n} | +5 {pct(hits[5],n)} | +10 {pct(hits[10],n)} | "
                f"+15 {pct(hits[15],n)} | +20 {pct(hits[20],n)} | "
                f"median peak {fmtc(med(r['peak_gain'] for r in rows))} | "
                f"avg adverse {fmtc(avg(r['adverse_gain'] for r in rows))} | protected EXIT n={len(exited)}"
            )
        lines.append("")

    lines.append("PRE-ARM FAILED-PRIMARY GRID (descriptive; no stop selected)")
    for split in ("VALIDATION", "REPORT_ONLY"):
        lines.append(f"[{split}]")
        grid = defaultdict(list)
        for r in failed:
            if r["split"] == split:
                grid[(r["adverse_trigger_cents"], r["min_elapsed_sec"])].append(r)
        if not grid:
            lines.append("  no triggered failed-primary cells")
            continue
        for key in sorted(grid):
            rows = grid[key]
            recover = sum(bool(r["would_recover_to_plus5"]) for r in rows)
            lines.append(
                f"  adverse -{key[0]:g}c after >= {key[1]:g}s: n={len(rows)} | "
                f"later +5 recovery {pct(recover,len(rows))} | "
                f"avg trigger {fmtc(avg(r['gain_at_trigger'] for r in rows))} | "
                f"median later best {fmtc(med(r['best_gain_after_trigger'] for r in rows))}"
            )
        lines.append("")
    lines += [
        "No rule is promoted by this report.",
        "REPORT_ONLY must not be used to tune thresholds.",
        "Any actionable secondary/re-entry or pre-arm cut rule requires a separate freeze and untouched forward confirmation.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default="/data/scalp_move_shadow_v1_events.csv")
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()
    src = Path(args.csv)
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    rows = read_rows(src)

    candidates_by_contract: dict[str, list[dict[str, str]]] = defaultdict(list)
    paths_by_cid: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if typ(row) == "CANDIDATE" and contract(row):
            candidates_by_contract[contract(row)].append(row)
        elif typ(row) == "PATH" and cid(row):
            paths_by_cid[cid(row)].append(row)

    split_map = split_contracts(candidates_by_contract)
    opps = build_opportunity_ladder(candidates_by_contract, paths_by_cid, split_map)
    failed = build_failed_primary_grid(candidates_by_contract, paths_by_cid, split_map)

    write_csv(outdir / "scalp_ladder_research_v1_opportunities.csv", opps)
    write_csv(outdir / "scalp_failed_primary_grid_v1.csv", failed)
    report = summary_text(opps, failed)
    (outdir / "scalp_ladder_research_v1.txt").write_text(report, encoding="utf-8")
    print(report, end="")
    print(f"SOURCE_ROWS={len(rows)} CONTRACTS={len(candidates_by_contract)} OPPORTUNITY_ROWS={len(opps)} FAILED_GRID_ROWS={len(failed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
