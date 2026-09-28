#!/usr/bin/env python3
"""Static adversarial gate for informational contract identity binding."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent
src = (ROOT / "BTC15_RECOVERED_V11_INFORMATION_SEAM_V1.py").read_text(encoding="utf-8")
tree = ast.parse(src)
script = None
for node in tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SCRIPT" for t in node.targets):
        script = ast.literal_eval(node.value)
        break
assert isinstance(script, str)

required = (
    "BTC15_COMBINED_STATE_BRIDGE_V6",
    "manual_execution_only!==true",
    "payload.orders!==false",
    "payload.order_action!==null",
    "scalp_display_contract_match!==true",
    "typeof payload.contract!=='string'",
    "p.ticker!==ident.contract",
    "now-i.received<=3500",
    "fetch('/combined-state'",
    "identityToken=null",
    "pollIdentity();poll();",
)
for token in required:
    assert token in script, token

for forbidden in (
    "currentContract", "textContent.match", "KALSHI_PRIVATE_KEY", "KALSHI_KEY_ID",
    "place_order", "order_action=", "finalAction", "earlyAction", "combinedScalpClean",
):
    assert forbidden not in script, forbidden

assert script.count("fetch('/combined-state'") == 1
assert "document.hidden" in script
assert "addEventListener('offline',invalidate)" in script
assert "visibilitychange" in script
print("RECOVERED V11 CONTRACT IDENTITY BINDING PASS | STRUCTURED SAME-TICKER | 3.5S LEASE | FAIL-CLOSED | NO ORDERS")
