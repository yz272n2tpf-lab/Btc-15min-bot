#!/usr/bin/env python3
"""Static regression gate for rollover pre-discovery integration.
No network, no production launch, no orders.
"""
from pathlib import Path
PROTECTED=[
"BTC15_DASHBOARD_INLINE_SCALP_DIAG_V2.py",
"BTC15_DASHBOARD_INLINE_SCALP_V1.py",
]
FORBIDDEN=("create_order","place_order","submit_order")
def scan(root=Path(".")):
 problems=[]
 for p in map(Path,PROTECTED):
  if not (root/p).exists(): problems.append(f"missing:{p}"); continue
  s=(root/p).read_text(encoding="utf-8",errors="replace").lower()
  for x in FORBIDDEN:
   if x in s: problems.append(f"order-token:{p}:{x}")
 return problems
if __name__=="__main__":
 x=scan()
 if x: raise SystemExit("\n".join(x))
 print("BTC15 ROLLOVER STATIC REGRESSION GATE PASS | PROTECTED WRAPPERS PRESENT | NO ORDER TOKENS")
