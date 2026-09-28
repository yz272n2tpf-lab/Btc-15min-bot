#!/usr/bin/env python3
"""Adversarial boundary for informational BRTI freshness presentation."""
from pathlib import Path
import ast
src=Path("BTC15_RECOVERED_V11_INFORMATION_SEAM_V1.py").read_text()
ast.parse(src)
for required in ("btc15QualifiedBrtiFreshness","Qualified BRTI: fresh","live qualification feed","waiting for ≤5s frame","p.brti_age_seconds","INFORMATIONAL_READ_ONLY","nowS-p.brti_source_ts>5"):assert required in src,required
tree=ast.parse(src)
script=None
for node in tree.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="SCRIPT" for t in node.targets):
        script=ast.literal_eval(node.value);break
assert isinstance(script,str)
for forbidden in ("brtiAge","brtiStatus","btcPrice","brtiPrice","targetPrice","dashboard_state.json","finalAction","earlyAction","combinedScalpClean","place_order","order_action="):assert forbidden not in script,forbidden
print("RECOVERED V11 BRTI FRESHNESS PRESENTATION PASS | INFORMATIONAL ONLY | LEGACY BRTI UNTOUCHED | <=5S CONTRACT PRESERVED | NO ORDERS")
