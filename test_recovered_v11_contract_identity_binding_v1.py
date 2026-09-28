#!/usr/bin/env python3
"""Static adversarial gate for native-owner informational identity binding."""
from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parent
info=(ROOT/"btc15_information_v1.py").read_text(encoding="utf-8")
proxy=(ROOT/"btc15_information_proxy_v1.py").read_text(encoding="utf-8")
src=(ROOT/"BTC15_RECOVERED_V11_INFORMATION_SEAM_V1.py").read_text(encoding="utf-8")
tree=ast.parse(src);script=None
for node in tree.body:
    if isinstance(node,ast.Assign) and any(isinstance(x,ast.Name) and x.id=="SCRIPT" for x in node.targets):
        script=ast.literal_eval(node.value);break
assert isinstance(script,str)

# Native owner/anchor and independently sampled health must bind the same contract.
for token in ("native_epoch","anchor_id","ticker","h['native_epoch'] != a['epoch']",
              "h['anchor_id'] != frame['anchor_id']","h['ticker'] != a['ticker']",
              "HEALTH_LEASE = 1.0","SOURCE_HEALTH_OR_OWNER_CHANGED"):
    assert token in info,token

# Public information transport must remain closed and <=5s fresh.
for token in ("BTC15_INFORMATION_V1","INFORMATIONAL_READ_ONLY",
              "value.get('orders') is not False","value.get('signal_only') is not True",
              "now-value['brti_source_ts'] > 5","now < min(value['expires_at'],value['display_until'])"):
    assert token in proxy,token

# Browser consumes only the closed information contract; historical SCALP bridge is not its identity oracle.
for token in ("fetch('/information'","p.schema!=='BTC15_INFORMATION_V1'",
              "p.authority!=='INFORMATIONAL_READ_ONLY'","p.status!=='AVAILABLE'",
              "p.signal_only!==true||p.orders!==false","nowS-p.brti_source_ts>5"):
    assert token in script,token
for forbidden in ("fetch('/combined-state'","identityToken","identityView","ident.contract",
                  "finalAction","earlyAction","combinedScalpClean","place_order(","submit_order(","create_order("):
    assert forbidden not in script,forbidden
assert "document.hidden" in script
assert "addEventListener('offline',invalidate)" in script
assert "visibilitychange" in script
print("RECOVERED V11 CONTRACT IDENTITY BINDING PASS | NATIVE OWNER+HEALTH | <=5S | FAIL-CLOSED | NO ORDERS")
