#!/usr/bin/env python3
"""Static adversarial qualification for recovered V11 FINAL probability patch."""
from pathlib import Path
import ast

P=Path('BTC15_RECOVERED_V11_FINAL_PROBABILITY_V1.py')
src=P.read_text(encoding='utf-8')
tree=ast.parse(src)
assign=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(getattr(t,'id',None)=='PATCH' for t in n.targets)]
assert len(assign)==1 and isinstance(assign[0].value,ast.Constant)
patch=assign[0].value.value
# Informational envelope must be explicit.
for token in ("INFORMATIONAL_READ_ONLY","status!=='AVAILABLE'","signal_only!==true","orders!==false"): assert token in patch
# Symmetric descriptive probability only.
assert "up>=down?'UP':'DOWN'" in patch and 'Math.max(up,down)' in patch
# Only the existing descriptive subtext may be written.
assert "_set('finalActionSub'" in patch
for forbidden in ('finalAction','finalReason','final.ready','final_status','early','scalp','latchedFinal','PROTECT','EXIT'): assert forbidden not in patch
# No trading/network mutation primitives.
for forbidden in ('POST','PUT','PATCH','DELETE','order_action','place_order','fetch('): assert forbidden not in patch
print('RECOVERED V11 FINAL STATIC ADVERSARIAL PASS | ONLY finalActionSub WRITABLE | NO ACTION AUTHORITY | NO ORDERS')
