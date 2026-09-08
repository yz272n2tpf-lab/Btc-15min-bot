#!/usr/bin/env python3
"""Read-only verifier for the V13 dashboard live-fix patch. No production writes."""
from __future__ import annotations
import ast, base64, gzip, sys
from pathlib import Path

TARGET = Path("BTC15_INSTALL_LIVE_DASHBOARD_V13.py")
STATE = "BTC15_DASHBOARD_STATE_V2.py"
HTML = "BTC_Kalshi_App_Live_v13.html"


def payloads(src: str) -> dict[str, str]:
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PAYLOADS" for t in node.targets):
            out = ast.literal_eval(node.value)
            if isinstance(out, dict): return out
    raise RuntimeError("PAYLOADS not found")


def unpack(p: dict[str, str], name: str) -> str:
    return gzip.decompress(base64.b64decode(p[name])).decode("utf-8")


def require(text: str, marker: str, label: str, failures: list[str]) -> None:
    if marker not in text: failures.append(f"MISSING {label}: {marker}")


def forbid(text: str, marker: str, label: str, failures: list[str]) -> None:
    if marker in text: failures.append(f"UNEXPECTED {label}: {marker}")


def main() -> int:
    failures: list[str] = []
    src = TARGET.read_text(encoding="utf-8")
    compile(src, str(TARGET), "exec")
    p = payloads(src)
    for name in (STATE, HTML):
        if name not in p: failures.append(f"missing payload {name}")
    if failures:
        print("RESULT: FAIL"); print("\n".join(failures)); return 1

    state, html = unpack(p, STATE), unpack(p, HTML)
    compile(state, STATE, "exec")

    require(state, "'brti': 'kalshi_direct_brti_parity_v1.csv'", "direct BRTI file", failures)
    require(state, "'brti_fresh': brti_fresh", "freshness field", failures)
    require(state, "'brti_source': 'DIRECT_LOG' if direct_sample_available else 'UNIFIED_FALLBACK'", "source field", failures)
    require(state, "direct_brti_authority_ready = (", "authority gate", failures)
    require(state, "brti_fresh\n        and math.isfinite(brti_gap)", "fresh authority condition", failures)

    require(html, "setInterval(refresh,2000)", "2-second dashboard polling", failures)
    forbid(html, "setInterval(refresh,5000)", "old 5-second polling", failures)
    require(html, "Number.isFinite(conf)?conf:e.fair", "signal-strength fallback", failures)
    require(html, "setText('flipRisk',fmtPct(flip,0))", "flip-risk percentage", failures)
    require(html, "m.brti_fresh?", "freshness-driven BRTI UI", failures)

    # Safety invariants: patch is display/adapter only. These forbidden strings
    # catch accidental expansion into execution/order placement inside the patch.
    patch = Path("BTC15_PATCH_V13_LIVE_FIXES.py").read_text(encoding="utf-8")
    for marker in ("place_order(", "create_order(", "submit_order(", "requests.post("):
        forbid(patch, marker, "order/execution code in patcher", failures)

    if failures:
        print("RESULT: FAIL")
        for f in failures: print(" -", f)
        return 1
    print("RESULT: PASS")
    print("V13 packed installer compiles and required live-fix markers are present.")
    print("Order/execution expansion: NONE DETECTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
