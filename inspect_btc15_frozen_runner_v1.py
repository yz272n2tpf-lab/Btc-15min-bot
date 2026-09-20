#!/usr/bin/env python3
"""Long-running frozen V13 handoff inspector. Read-only. NO ORDERS."""
import time
import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer
p=installer.install()/"BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py"
s=p.read_text()
print("FROZEN_RUNNER_BEGIN",flush=True)
for i,line in enumerate(s.splitlines(),1):
 if any(k.lower() in line.lower() for k in ["subprocess","popen","parity","rescue","exec","btc15_"]):
  print(f"{i}: {line}",flush=True)
print("FROZEN_RUNNER_END | NO ORDERS",flush=True)
while True: time.sleep(60)
