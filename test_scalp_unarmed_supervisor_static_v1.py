#!/usr/bin/env python3
"""Static safety gate for scalp one-shot worker/supervisor. NO ORDERS."""
import ast,pathlib
for n in ("btc15_scalp_unarmed_analysis_once_v1.py","btc15_scalp_unarmed_supervisor_v1.py"):
 s=pathlib.Path(__file__).with_name(n).read_text();ast.parse(s)
 for bad in ("requests.post(","requests.put(","requests.patch(","requests.delete(","create_order","place_order"):
  if bad in s:raise SystemExit("STOP write capability in "+n+": "+bad)
for need in ("subprocess.run","timeout=840","worker_running","NO ORDERS"):
 if need not in pathlib.Path(__file__).with_name("btc15_scalp_unarmed_supervisor_v1.py").read_text():raise SystemExit("STOP missing supervisor invariant "+need)
print("SCALP_UNARMED_SUPERVISOR_STATIC_PASS | one worker | timeout | NO ORDERS")

# trigger-supervisor-canary-v1
