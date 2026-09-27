#!/usr/bin/env python3
"""Static adversarial qualification for recovered V11 FINAL probability patch."""
from pathlib import Path
import ast,re
P=Path('BTC15_RECOVERED_V11_FINAL_PROBABILITY_V1.py')
src=P.read_text(encoding='utf-8'); tree=ast.parse(src)
assign=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(getattr(t,'id',None)=='PATCH' for t in n.targets)]
assert len(assign)==1 and isinstance(assign[0].value,ast.Constant)
patch=assign[0].value.value
for token in ("INFORMATIONAL_READ_ONLY","status!=='AVAILABLE'","signal_only!==true","orders!==false"): assert token in patch
assert "up>=down?'UP':'DOWN'" in patch and 'Math.max(up,down)' in patch
writes=re.findall(r"_set\(\s*['\"]([^'\"]+)['\"]",patch)
assert writes==['finalActionSub'], writes
for forbidden in ('final.ready=','final_status=','early.ready=','scalp.ready=','latchedFinal='): assert forbidden not in patch
for pattern in (r'\bfetch\s*\(',r'\bplace_order\s*\(',r'\border_action\s*\(',r"method\s*:\s*['\"](?:POST|PUT|PATCH|DELETE)['\"]"):
    assert not re.search(pattern,patch,re.I), pattern
print('RECOVERED V11 FINAL STATIC ADVERSARIAL PASS | ONLY finalActionSub WRITABLE | NO ACTION AUTHORITY | NO ORDERS')
