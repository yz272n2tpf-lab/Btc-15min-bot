#!/usr/bin/env python3
"""Adversarial boundary for informational BRTI freshness and guard presentation."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "BTC15_RECOVERED_V11_INFORMATION_SEAM_V1.py"
src = SOURCE.read_text(encoding="utf-8")
ast.parse(src)

required = (
    "btc15QualifiedBrtiFreshness",
    "Qualified BRTI: fresh",
    "live qualification feed",
    "waiting for ≤5s frame",
    "p.brti_age_seconds",
    "INFORMATIONAL_READ_ONLY",
    "nowS-p.brti_source_ts>5",
    "btc15QualifiedGuardState",
    "3M GUARD",
    "5M CAUTION",
    "NORMAL WINDOW",
    "GUARD STATE · DATA NOT FRESH",
)
for token in required:
    assert token in src, token

tree = ast.parse(src)
script = None
for node in tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SCRIPT" for t in node.targets):
        script = ast.literal_eval(node.value)
        break
assert isinstance(script, str)

for forbidden in (
    "brtiAge", "brtiStatus", "btcPrice", "brtiPrice", "targetPrice",
    "dashboard_state.json", "finalAction", "earlyAction", "combinedScalpClean",
    "place_order", "order_action=",
):
    assert forbidden not in script, forbidden

print("RECOVERED V11 BRTI FRESHNESS PRESENTATION PASS | INFORMATIONAL ONLY | LEGACY BRTI UNTOUCHED | <=5S CONTRACT PRESERVED | GUARD STATES BOUND | NO ORDERS")
