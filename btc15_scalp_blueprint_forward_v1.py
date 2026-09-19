#!/usr/bin/env python3
"""
BTC15 final SCALP blueprint forward validator V1.

SHADOW VALIDATION ONLY | SIGNAL ONLY | NO ORDERS

Purpose:
- Continuously re-read the existing generalized scalp event tape from the
  read-only export bridge.
- Score untouched forward behavior from a fixed cutoff without changing the
  collector, entry rules, EARLY, FINAL, or production dashboard.
- Validate the user-confirmed scalp blueprint: scan the whole 15-minute
  contract, manage one scalp through EXIT, then reset and allow the next
  qualified scalp in the same contract, with no artificial scalp-count cap.
- Treat 10c+ as the meaningful-move reporting target while NEVER using Kalshi
  entry price as a trigger or suppression gate. Price bands are telemetry only.
- Audit primary scalps that never arm +5c, but do not invent a cut rule.
- Audit backend timer/contract alignment from the off-production shadow status.

No rule is promoted by this service. It only collects and scores evidence.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import statistics
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

import requests

import BTC15_SCALP_LADDER_RESEARCH_V1 as research

VERSION = "BTC15_SCALP_BLUEPRINT_FORWARD_V1"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(15, int(os.environ.get("SCALP_BLUEPRINT_POLL_SEC", "30")))
SOURCE_URL = os.environ.get(
    "SCALP_PATH_EXPORT_URL",
    "https://scalp-move-shadow-v1-production.up.railway.app/research/path-export",
).strip()
SOURCE_TOKEN = os.environ.get("SCALP_PATH_EXPORT_TOKEN", "").strip()
SHADOW_STATUS_URL = os.environ.get(
    "SCALP_SHADOW_STATUS_URL",
    "https://combined-dashboard-shadow-v1-production.up.railway.app/shadow-status",
).strip()
CUTOFF_RAW = os.environ.get("SCALP_BLUEPRINT_CUTOFF_UTC", "2026-09-14T21:08:00Z").strip()
MIN_REVIEW_OPPORTUNITIES = max(1, int(os.environ.get("SCALP_BLUEPRINT_MIN_REVIEW", "20")))

LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "cutoff_utc": CUTOFF_RAW,
    "status": "STARTING",
    "orders": False,
    "manual_execution_only": True,
    "shadow_only": True,
}
TIMER_SAMPLES: list[dict[str, Any]] = []


def dt(v: Any) -> datetime:
    return research.dt(v)


def cutoff_dt() -> datetime:
    x = dt(CUTOFF_RAW)
    if x == datetime.min.replace(tzinfo=timezone.utc):
        raise ValueError(f"invalid cutoff: {CUTOFF_RAW}")
    return x


def fetch_csv_raw() -> tuple[bytes, str]:
    headers = {"Cache-Control": "no-cache"}
    if SOURCE_TOKEN:
        headers["Authorization"] = f"Bearer {SOURCE_TOKEN}"
    r = requests.get(SOURCE_URL, headers=headers, timeout=30)
    r.raise_for_status()
    raw = r.content
    if not raw or b"record_type" not in raw[:4096]:
        raise ValueError("unexpected event export")
    return raw, hashlib.sha256(raw).hexdigest()

def parse_csv_raw(raw: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8", "replace"))))

def fetch_csv_rows() -> tuple[list[dict[str, str]], str]:
    raw, sha = fetch_csv_raw()
    return parse_csv_raw(raw), sha


def completed_ids(rows: list[Mapping[str, Any]]) -> set[str]:
    return {
        research.cid(r)
        for r in rows
        if research.typ(r) == "RESULT" and research.cid(r)
    }


def forward_candidates(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    cut = cutoff_dt()
    return [
        dict(r) for r in rows
        if research.typ(r) == "CANDIDATE"
        and research.contract(r)
        and research.cid(r)
        and dt(r.get("timestamp_utc")) >= cut
    ]


def build_serial_opportunities(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Unlimited serial scalp ladder, resetting only after prior protected EXIT.

    This intentionally mirrors the currently validated management rule. If a
    scalp never arms +5c and therefore never reaches protected EXIT, the serial
    ladder stops there; that blockage is reported separately instead of being
    hidden or solved with an unvalidated loss-cut rule.
    """
    done = completed_ids(rows)
    cands = forward_candidates(rows)
    by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    paths: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in cands:
        by_contract[research.contract(c)].append(c)
    for r in rows:
        if research.typ(r) == "PATH" and research.cid(r):
            paths[research.cid(r)].append(dict(r))

    out: list[dict[str, Any]] = []
    for contract, raw in by_contract.items():
        qualified = [
            c for c in sorted(raw, key=lambda x: dt(x.get("timestamp_utc")))
            if research.candidate_qualified(c)
        ]
        earliest = datetime.min.replace(tzinfo=timezone.utc)
        idx = 1
        used: set[str] = set()
        while True:
            cand = next(
                (c for c in qualified
                 if research.cid(c) not in used and dt(c.get("timestamp_utc")) > earliest),
                None,
            )
            if cand is None:
                break
            cid = research.cid(cand)
            used.add(cid)
            if cid not in done:
                break  # do not score an incomplete/current candidate as a result
            pm = research.measure_path(cand, research.path_rows_for(cand, paths))
            ask = research.f(cand.get("entry_ask"))
            rec = {
                "contract": contract,
                "opportunity_index": idx,
                "candidate_id": cid,
                "timestamp_utc": str(cand.get("timestamp_utc") or ""),
                "side": str(cand.get("side") or "").strip().upper(),
                "entry_ask": ask,
                "seconds_left": research.f(cand.get("seconds_left")),
                "btc30": research.f(cand.get("btc30")),
                "peak_gain": pm.peak_gain,
                "adverse_gain": pm.adverse_gain,
                "armed_plus5": pm.armed,
                "protected_exit_gain": pm.exit_gain,
                "protected_exit_time_utc": pm.exit_time_utc,
                "plus5": bool(pm.peak_gain is not None and pm.peak_gain >= .05),
                "plus10": bool(pm.peak_gain is not None and pm.peak_gain >= .10),
                "plus15": bool(pm.peak_gain is not None and pm.peak_gain >= .15),
                "plus20": bool(pm.peak_gain is not None and pm.peak_gain >= .20),
                "plus30": bool(pm.peak_gain is not None and pm.peak_gain >= .30),
                "plus40": bool(pm.peak_gain is not None and pm.peak_gain >= .40),
                "plus50": bool(pm.peak_gain is not None and pm.peak_gain >= .50),
                "meaningful_10c": bool(pm.peak_gain is not None and pm.peak_gain >= .10),
                "entry_price_is_telemetry_only": True,
            }
            out.append(rec)
            if not pm.exit_time_utc:
                break
            earliest = dt(pm.exit_time_utc)
            idx += 1
    return out


def price_band(ask: float | None) -> str:
    if ask is None:
        return "unknown"
    c = ask * 100.0
    if c < 10: return "<10c"
    if c < 20: return "10-20c"
    if c < 30: return "20-30c"
    if c < 45: return "30-45c"
    if c < 60: return "45-60c"
    if c < 70: return "60-70c"
    if c < 80: return "70-80c"
    return "80c+"


def rate(rows: list[dict[str, Any]], key: str) -> float | None:
    return None if not rows else sum(bool(r.get(key)) for r in rows) / len(rows)


def median_num(rows: list[dict[str, Any]], key: str) -> float | None:
    xs = [float(r[key]) for r in rows if r.get(key) is not None]
    return statistics.median(xs) if xs else None


def failed_primary_forward(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    done = completed_ids(rows)
    cands = forward_candidates(rows)
    by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    paths: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in cands:
        by_contract[research.contract(c)].append(c)
    for r in rows:
        if research.typ(r) == "PATH" and research.cid(r):
            paths[research.cid(r)].append(dict(r))

    failed_contracts = []
    grid_counts: dict[str, dict[str, Any]] = {}
    for contract, raw in by_contract.items():
        qualified = [c for c in sorted(raw, key=lambda x: dt(x.get("timestamp_utc"))) if research.candidate_qualified(c)]
        if not qualified:
            continue
        primary = qualified[0]
        cid = research.cid(primary)
        if cid not in done:
            continue
        pm = research.measure_path(primary, research.path_rows_for(primary, paths))
        if pm.armed:
            continue
        failed_contracts.append({
            "contract": contract,
            "candidate_id": cid,
            "side": str(primary.get("side") or "").upper(),
            "entry_ask": research.f(primary.get("entry_ask")),
            "peak_gain": pm.peak_gain,
            "adverse_gain": pm.adverse_gain,
        })
        ctime = dt(primary.get("timestamp_utc"))
        timeline = []
        for row in research.path_rows_for(primary, paths):
            e = research.elapsed(row, ctime)
            g = research.f(row.get("exec_gain"))
            if e is not None and g is not None:
                timeline.append((e, g))
        timeline.sort()
        for adverse in research.ADVERSE_LEVELS:
            for min_e in research.MIN_ELAPSED:
                hit = next(((i, e, g) for i, (e, g) in enumerate(timeline) if e >= min_e and g <= -adverse), None)
                if hit is None:
                    continue
                i, e, g = hit
                future = [x[1] for x in timeline[i:]]
                best = max(future) if future else None
                key = f"-{adverse*100:g}c_after_{min_e:g}s"
                cell = grid_counts.setdefault(key, {"n": 0, "recover_plus5": 0, "gains": [], "best_after": []})
                cell["n"] += 1
                cell["recover_plus5"] += int(best is not None and best >= .05)
                cell["gains"].append(g)
                if best is not None: cell["best_after"].append(best)

    grid = {}
    for key, cell in sorted(grid_counts.items()):
        grid[key] = {
            "n": cell["n"],
            "recover_plus5_rate": cell["recover_plus5"] / cell["n"] if cell["n"] else None,
            "avg_gain_at_trigger": statistics.fmean(cell["gains"]) if cell["gains"] else None,
            "median_best_after_trigger": statistics.median(cell["best_after"]) if cell["best_after"] else None,
            "actionable_now": False,
        }
    return {
        "completed_failed_primary_n": len(failed_contracts),
        "failed_primaries": failed_contracts,
        "prearm_grid": grid,
        "cut_rule_selected": False,
        "actionable_now": False,
    }


def poll_timer_status() -> None:
    sample: dict[str, Any] = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "ok": False}
    try:
        r = requests.get(SHADOW_STATUS_URL, timeout=5, headers={"Cache-Control": "no-cache"})
        r.raise_for_status()
        j = r.json()
        sample.update({
            "ok": True,
            "contract_match": j.get("contract_match") is True,
            "timer_delta_sec": j.get("cross_fetch_timer_delta_sec"),
            "canonical_clock_present": j.get("canonical_clock_present") is True,
            "safety_pass": j.get("all_safety_checks_pass") is True,
        })
    except Exception as exc:
        sample["error"] = f"{type(exc).__name__}:{exc}"
    TIMER_SAMPLES.append(sample)
    if len(TIMER_SAMPLES) > 2000:
        del TIMER_SAMPLES[: len(TIMER_SAMPLES) - 2000]


def timer_summary() -> dict[str, Any]:
    valid = [s for s in TIMER_SAMPLES if s.get("ok")]
    deltas = [float(s["timer_delta_sec"]) for s in valid if s.get("timer_delta_sec") is not None]
    return {
        "samples_total": len(TIMER_SAMPLES),
        "samples_valid": len(valid),
        "latest": TIMER_SAMPLES[-1] if TIMER_SAMPLES else None,
        "contract_match_rate": None if not valid else sum(s.get("contract_match") is True for s in valid) / len(valid),
        "canonical_clock_rate": None if not valid else sum(s.get("canonical_clock_present") is True for s in valid) / len(valid),
        "within_5s_rate": None if not deltas else sum(d <= 5.0 for d in deltas) / len(deltas),
        "median_delta_sec": None if not deltas else statistics.median(deltas),
        "max_delta_sec": None if not deltas else max(deltas),
        "display_timer_visual_check_still_required": True,
    }


def build_summary(rows: list[dict[str, str]], sha: str) -> dict[str, Any]:
    opps = build_serial_opportunities(rows)
    contracts = sorted({r["contract"] for r in opps})
    by_index: dict[str, dict[str, Any]] = {}
    for idx in sorted({int(r["opportunity_index"]) for r in opps}):
        x = [r for r in opps if int(r["opportunity_index"]) == idx]
        by_index[str(idx)] = {
            "n": len(x),
            "plus10_rate": rate(x, "plus10"),
            "plus15_rate": rate(x, "plus15"),
            "plus20_rate": rate(x, "plus20"),
            "median_peak_gain": median_num(x, "peak_gain"),
            "median_adverse_gain": median_num(x, "adverse_gain"),
        }

    bands: dict[str, dict[str, Any]] = {}
    for b in ("<10c", "10-20c", "20-30c", "30-45c", "45-60c", "60-70c", "70-80c", "80c+", "unknown"):
        x = [r for r in opps if price_band(r.get("entry_ask")) == b]
        if x:
            bands[b] = {
                "n": len(x),
                "plus10_rate": rate(x, "plus10"),
                "plus20_rate": rate(x, "plus20"),
                "median_peak_gain": median_num(x, "peak_gain"),
                "price_is_telemetry_only": True,
            }

    meaningful = sum(r["meaningful_10c"] for r in opps)
    status = "READY_FOR_REVIEW" if len(opps) >= MIN_REVIEW_OPPORTUNITIES else "COLLECTING"
    return {
        "ok": True,
        "version": VERSION,
        "status": status,
        "cutoff_utc": CUTOFF_RAW,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": sha,
        "source_rows": len(rows),
        "observed_contracts_with_completed_serial_opportunity": len(contracts),
        "completed_serial_opportunities": len(opps),
        "meaningful_10c_n": meaningful,
        "meaningful_10c_rate": None if not opps else meaningful / len(opps),
        "plus5_rate": rate(opps, "plus5"),
        "plus10_rate": rate(opps, "plus10"),
        "plus15_rate": rate(opps, "plus15"),
        "plus20_rate": rate(opps, "plus20"),
        "plus30_rate": rate(opps, "plus30"),
        "plus40_rate": rate(opps, "plus40"),
        "plus50_rate": rate(opps, "plus50"),
        "max_opportunities_in_one_contract": max((int(r["opportunity_index"]) for r in opps), default=0),
        "opportunities_by_index": by_index,
        "entry_price_bands": bands,
        "failed_primary": failed_primary_forward(rows),
        "timer_audit": timer_summary(),
        "blueprint": {
            "full_contract_scan": True,
            "unlimited_serial_reset_after_exit": True,
            "meaningful_move_reporting_target_cents": 10,
            "price_zone_trigger": False,
            "entry_price_filter_applied": False,
            "high_price_cutoff_selected": False,
            "high_price_cutoff_is_being_measured_not_enforced": True,
            "protect_after_plus5_then_4c_giveback": True,
            "failed_prearm_cut_rule_selected": False,
            "manual_execution_only": True,
            "orders": False,
        },
        "review_gate": {
            "minimum_completed_serial_opportunities": MIN_REVIEW_OPPORTUNITIES,
            "met": len(opps) >= MIN_REVIEW_OPPORTUNITIES,
            "ready_means_review_not_pass": True,
        },
        "orders": False,
        "manual_execution_only": True,
        "shadow_only": True,
        "no_rules_promoted_automatically": True,
    }


def cycle() -> None:
    rows, sha = fetch_csv_rows()
    poll_timer_status()
    summary = build_summary(rows, sha)
    with LOCK:
        STATE.clear(); STATE.update(summary)
    print(
        "SCALP BLUEPRINT FORWARD | "
        f"status={summary['status']} | contracts={summary['observed_contracts_with_completed_serial_opportunity']} | "
        f"opps={summary['completed_serial_opportunities']} | +10={summary['plus10_rate']} | "
        f"max_opp_index={summary['max_opportunities_in_one_contract']} | "
        f"failed_prearm={summary['failed_primary']['completed_failed_primary_n']} | "
        f"timer_samples={summary['timer_audit']['samples_valid']}/{summary['timer_audit']['samples_total']} | "
        "SHADOW ONLY | NO ORDERS",
        flush=True,
    )


def worker() -> None:
    while True:
        try:
            cycle()
        except Exception as exc:
            with LOCK:
                STATE.update({
                    "ok": False,
                    "status": "ERROR_RETRYING",
                    "last_error": f"{type(exc).__name__}: {exc}",
                    "orders": False,
                    "manual_execution_only": True,
                    "shadow_only": True,
                })
            print(f"SCALP BLUEPRINT FORWARD ERROR | {type(exc).__name__}: {exc} | RETRYING | NO ORDERS", flush=True)
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15ScalpBlueprintForward/1.0"
    def log_message(self, fmt, *args):
        print("SCALP_BLUEPRINT_HTTP | request", flush=True)
    def _json(self, code: int, obj: Any):
        raw = json.dumps(obj, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        path = urlparse(self.path).path
        if path in {"/", "/health", "/summary.json"}:
            with LOCK: data = dict(STATE)
            return self._json(200 if data.get("ok") else 503, data)
        return self._json(404, {"ok": False, "orders": False, "error": "not_found"})
    def _reject(self):
        return self._json(405, {"ok": False, "orders": False, "error": "read_only_shadow"})
    do_POST = _reject; do_PUT = _reject; do_PATCH = _reject; do_DELETE = _reject


def main() -> int:
    print(
        f"{VERSION} START | cutoff={CUTOFF_RAW} | poll={POLL_SEC}s | "
        "FULL-CONTRACT MULTI-SCALP BLUEPRINT | READ ONLY | SIGNAL ONLY | NO ORDERS",
        flush=True,
    )
    cycle()
    threading.Thread(target=worker, name="scalp-blueprint-forward", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
