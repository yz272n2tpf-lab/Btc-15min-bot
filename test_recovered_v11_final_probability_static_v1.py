#!/usr/bin/env python3
"""Whole-candidate adversarial qualification for recovered FINAL V2."""
from pathlib import Path
import ast,re
src=Path('BTC15_RECOVERED_V11_FINAL_PROBABILITY_V1.py').read_text(encoding='utf-8')
tree=ast.parse(src)
vals={}
for n in ast.walk(tree):
    if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and isinstance(n.value,ast.Constant):
        vals[n.targets[0].id]=n.value.value
renderer=vals['RENDERER']
assert vals['MARKER']=='BTC15_RECOVERED_V11_FINAL_PROBABILITY_V2'
assert vals['HOOK_MARKER']=='BTC15_INFO_TO_FINAL_HOOK_V2'
for token in ('INFORMATIONAL_READ_ONLY',"status!=='AVAILABLE'",'signal_only!==true','orders!==false'):assert token in renderer
assert "up>=down?'UP':'DOWN'" in renderer
assert 'Math.max(up,down)' in renderer
assert 'FINAL qualified' in renderer
assert '!safeNonFinal()' in renderer
targets=re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)",renderer)
assert targets==['finalActionSub'],targets
for bad in ('final.ready=','final_status=','early.ready=','scalp.ready=','latchedFinal=','place_order','order_action'):assert bad not in renderer
assert 'fetch(' not in renderer
assert 'btc15RenderInformationalFinal(null)' in src
assert 'btc15RenderInformationalFinal(p)' in src
print('RECOVERED V11 FINAL V2 STATIC ADVERSARIAL PASS | FRESH+STALE | ONLY finalActionSub | QUALIFIED FINAL PROTECTED | NO ORDERS')
