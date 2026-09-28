#!/usr/bin/env python3
"""Single qualification gate for recovered V11 UI candidate.

Run only on the exact candidate commit. Any code change invalidates this result.
"""
import subprocess,sys
from pathlib import Path

checks=[
 ("V12_UI",[sys.executable,"BTC15_DASHBOARD_COMBINED_SCALP_UI_V12.py","--self-test"]),
 ("V13_UI",[sys.executable,"BTC15_DASHBOARD_COMBINED_SCALP_UI_V13.py","--self-test"]),
 ("HOST",[sys.executable,"-m","unittest","-q","test_btc15_combined_dashboard_shadow_v1.py","test_btc15_combined_dashboard_shadow_v7.py"]),
 ("INFO_SEAM",[sys.executable,"BTC15_RECOVERED_V11_INFORMATION_SEAM_V1.py","--self-test"]),
 ("FINAL_V2",[sys.executable,"BTC15_RECOVERED_V11_FINAL_PROBABILITY_V1.py","--self-test"]),
 ("FINAL_ADVERSARIAL",[sys.executable,"test_recovered_v11_final_probability_static_v1.py"]),
 ("LIVE_HOST_STATIC",[sys.executable,"test_recovered_v11_live_host_static_v1.py"]),
]
failed=[]
for name,cmd in checks:
    print("\n=== "+name+" ===",flush=True)
    rc=subprocess.run(cmd).returncode
    if rc!=0:failed.append(name)
# Static product/process invariants for this branch.
for required in ("BTC15_DEVELOPMENT_OPERATING_CONTRACT_V1.md","RECOVERED_V11_APP_INTEGRATION_CONTRACT_V1.md"):
    if not Path(required).exists():failed.append("MISSING_"+required)
if failed:
    print("\nBTC15 CANDIDATE REJECTED — "+", ".join(failed))
    raise SystemExit(1)
print("\nBTC15 CANDIDATE QUALIFIED — ALL REQUIRED GATES PASS")
