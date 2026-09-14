#!/usr/bin/env python3
"""
BTC15 scalp ladder research report service V1.

ISOLATED RESEARCH ONLY | READ ONLY | SIGNAL ONLY | NO ORDERS

Downloads one immutable snapshot of the existing generalized scalp event CSV
from the read-only PATH export bridge, runs the pre-frozen multi-opportunity /
failed-primary scorer, then applies the separately pre-frozen VALIDATION-only
selector. REPORT_ONLY is confirmation only.

This service never writes to the live collector, never changes strategy rules,
and never places or manages orders.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import requests

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import BTC15_SCALP_LADDER_SELECTOR_V1 as selector

VERSION = "BTC15_SCALP_LADDER_RESEARCH_SERVICE_V1"
PORT = int(os.environ.get("PORT", "8080"))
SOURCE_URL = os.environ.get(
    "SCALP_PATH_EXPORT_URL",
    "https://scalp-move-shadow-v1-production.up.railway.app/research/path-export",
).strip()
SOURCE_TOKEN = os.environ.get("SCALP_PATH_EXPORT_TOKEN", "").strip()

SNAPSHOT_DIR = Path(tempfile.mkdtemp(prefix="btc15_scalp_ladder_snapshot_"))
SNAPSHOT_CSV = SNAPSHOT_DIR / "scalp_move_shadow_v1_events.csv"
REPORT_TXT = SNAPSHOT_DIR / "scalp_ladder_research_v1.txt"
OPPS_CSV = SNAPSHOT_DIR / "scalp_ladder_research_v1_opportunities.csv"
FAILED_CSV = SNAPSHOT_DIR / "scalp_failed_primary_grid_v1.csv"
SELECTION_JSON = SNAPSHOT_DIR / "scalp_ladder_selection_v1.json"

STATE: dict = {
    "ok": False,
    "version": VERSION,
    "orders": False,
    "manual_execution_only": True,
    "research_only": True,
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fetch_snapshot() -> bytes:
    headers = {"Cache-Control": "no-cache"}
    if SOURCE_TOKEN:
        headers["Authorization"] = f"Bearer {SOURCE_TOKEN}"
    r = requests.get(SOURCE_URL, headers=headers, timeout=30)
    r.raise_for_status()
    raw = r.content
    if not raw or b"record_type" not in raw[:4096]:
        raise ValueError("export response is not the expected event CSV")
    return raw


def build_selection(opps: list[dict], failed: list[dict]) -> dict:
    opp_result = {}
    for idx, name in ((2, "secondary"), (3, "tertiary")):
        val = [r for r in opps if r.get("split") == "VALIDATION" and int(r.get("opportunity_index") or 0) == idx]
        rep = [r for r in opps if r.get("split") == "REPORT_ONLY" and int(r.get("opportunity_index") or 0) == idx]
        vm = selector.opportunity_metrics(val)
        rm = selector.opportunity_metrics(rep)
        opp_result[name] = {
            "rule": f"first frozen-qualified opportunity #{idx} after prior protected EXIT",
            "validation": vm,
            "validation_viable": selector.opportunity_viable(vm),
            "report_only": rm,
            "report_only_confirmation_only": True,
            "requires_20_new_forward": True,
            "actionable_now": False,
        }

    val_failed = [r for r in failed if r.get("split") == "VALIDATION"]
    rep_failed = [r for r in failed if r.get("split") == "REPORT_ONLY"]
    chosen, all_cells = selector.select_failed(val_failed)
    rep_same = selector.matching_failed(rep_failed, chosen)
    report_confirmation = selector.failed_cell_metrics(rep_same) if chosen else None

    return {
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


def run_research(raw: bytes) -> dict:
    SNAPSHOT_CSV.write_bytes(raw)
    rows = research.read_rows(SNAPSHOT_CSV)

    candidates_by_contract: dict[str, list[dict[str, str]]] = defaultdict(list)
    paths_by_cid: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if research.typ(row) == "CANDIDATE" and research.contract(row):
            candidates_by_contract[research.contract(row)].append(row)
        elif research.typ(row) == "PATH" and research.cid(row):
            paths_by_cid[research.cid(row)].append(row)

    split_map = research.split_contracts(candidates_by_contract)
    opps = research.build_opportunity_ladder(candidates_by_contract, paths_by_cid, split_map)
    failed = research.build_failed_primary_grid(candidates_by_contract, paths_by_cid, split_map)

    research.write_csv(OPPS_CSV, opps)
    research.write_csv(FAILED_CSV, failed)
    report = research.summary_text(opps, failed)
    REPORT_TXT.write_text(report, encoding="utf-8")

    selection = build_selection(opps, failed)
    SELECTION_JSON.write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    per_split = {}
    for split in ("VALIDATION", "REPORT_ONLY"):
        per_split[split] = {
            "opportunity_1": sum(r["split"] == split and r["opportunity_index"] == 1 for r in opps),
            "opportunity_2": sum(r["split"] == split and r["opportunity_index"] == 2 for r in opps),
            "opportunity_3": sum(r["split"] == split and r["opportunity_index"] == 3 for r in opps),
            "failed_grid_rows": sum(r["split"] == split for r in failed),
        }

    return {
        "ok": True,
        "version": VERSION,
        "orders": False,
        "manual_execution_only": True,
        "research_only": True,
        "snapshot_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": sha256_bytes(raw),
        "source_rows": len(rows),
        "contracts_with_candidates": len(candidates_by_contract),
        "opportunity_rows": len(opps),
        "failed_grid_rows": len(failed),
        "split_counts": per_split,
        "selection": selection,
        "protected_primary_changed": False,
        "secondary_actionable": False,
        "failed_primary_cut_actionable": False,
        "report_only_used_for_selection": False,
    }


def load_once() -> None:
    global STATE
    try:
        raw = fetch_snapshot()
        STATE = run_research(raw)
        print(
            "SCALP LADDER RESEARCH SNAPSHOT READY | "
            f"rows={STATE['source_rows']} | contracts={STATE['contracts_with_candidates']} | "
            f"opportunity_rows={STATE['opportunity_rows']} | failed_grid_rows={STATE['failed_grid_rows']} | "
            f"sha256={STATE['source_sha256'][:12]}... | NO ORDERS",
            flush=True,
        )
        print(REPORT_TXT.read_text(encoding="utf-8"), flush=True)
        print("SCALP LADDER VALIDATION-ONLY SELECTION", flush=True)
        print(SELECTION_JSON.read_text(encoding="utf-8"), flush=True)
    except Exception as exc:
        STATE = {
            "ok": False,
            "version": VERSION,
            "orders": False,
            "manual_execution_only": True,
            "research_only": True,
            "error": f"{type(exc).__name__}: {exc}",
        }
        print(f"SCALP LADDER RESEARCH ERROR | {STATE['error']} | NO ORDERS", flush=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15ScalpLadderResearch/1.0"

    def log_message(self, fmt, *args):
        print("SCALP_LADDER_RESEARCH_HTTP | request", flush=True)

    def _send(self, code: int, ctype: str, raw: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _json(self, code: int, obj):
        self._send(code, "application/json", json.dumps(obj, separators=(",", ":")).encode())

    def do_GET(self):
        path = urlparse(self.path).path
        if path in {"/", "/summary.json", "/health"}:
            return self._json(200 if STATE.get("ok") else 503, STATE)
        if path == "/report.txt" and REPORT_TXT.exists():
            return self._send(200, "text/plain; charset=utf-8", REPORT_TXT.read_bytes())
        if path == "/selection.json" and SELECTION_JSON.exists():
            return self._send(200, "application/json", SELECTION_JSON.read_bytes())
        if path == "/opportunities.csv" and OPPS_CSV.exists():
            return self._send(200, "text/csv; charset=utf-8", OPPS_CSV.read_bytes())
        if path == "/failed-grid.csv" and FAILED_CSV.exists():
            return self._send(200, "text/csv; charset=utf-8", FAILED_CSV.read_bytes())
        return self._json(404, {"ok": False, "orders": False, "error": "not_found"})

    def _reject(self):
        return self._json(405, {"ok": False, "orders": False, "error": "read_only_research"})

    do_POST = _reject
    do_PUT = _reject
    do_PATCH = _reject
    do_DELETE = _reject


def main() -> int:
    load_once()
    print(f"{VERSION} START | port={PORT} | IMMUTABLE SNAPSHOT | READ ONLY | NO ORDERS", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
