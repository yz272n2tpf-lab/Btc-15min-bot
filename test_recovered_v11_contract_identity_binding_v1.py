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
    "BTC15_INFORMATION_IDENTITY_V1",
    "payload.signal_only!==true",
    "payload.orders!==false",
    "typeof payload.ticker!=='string'",
    "typeof payload.native_epoch!=='string'",
    "typeof payload.anchor_id!=='string'",
    "!Number.isFinite(payload.observed_ts)",
    "p.ticker!==ident.contract",
    "now-i.received<=1500",
    "fetch('/information/identity'",
    "X-BTC15-Information-Nonce",
    "identityToken=null",
    "pollIdentity();poll();",
)
for token in required:
    assert token in script, token

for forbidden in (
    "currentContract", "textContent.match", "KALSHI_PRIVATE_KEY", "KALSHI_KEY_ID",
    "place_order(", "submit_order(", "create_order(", "finalAction", "earlyAction", "combinedScalpClean",
):
    assert forbidden not in script, forbidden

assert script.count("fetch('/information/identity'") == 1
assert "fetch('/combined-state'" not in script
assert "document.hidden" in script
assert "addEventListener('offline',invalidate)" in script
assert "visibilitychange" in script
print("RECOVERED V11 CONTRACT IDENTITY BINDING PASS | NATIVE SAME-TICKER | 1.5S LEASE | NONCE BOUND | FAIL-CLOSED | NO ORDERS")
