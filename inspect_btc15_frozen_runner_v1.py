#!/usr/bin/env python3
"""Inspect generated frozen V13 runner without launching it. Read-only. NO ORDERS."""
import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer
p=installer.install()/"BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py"
s=p.read_text()
print("FROZEN_RUNNER_BEGIN")
for i,line in enumerate(s.splitlines(),1):
 if any(k in line for k in ["subprocess","Popen","parity","PARITY","rescue","RESCUE","python","exec","BTC15_"]):
  print(f"{i}: {line}")
print("FROZEN_RUNNER_END | NO ORDERS")
