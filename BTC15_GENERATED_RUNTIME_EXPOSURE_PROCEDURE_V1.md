# Generated Runtime Exposure Procedure V1

Purpose: obtain the exact generated full-validation wrapper source without executing it.

Already present on this branch:
- expose_btc15_generated_runtime_v1.py
- test_expose_btc15_generated_runtime_v1.py
- .github/workflows/btc15_regression_inspect_runtime.yml

Safe local command when execution access is available:
python -m unittest -q test_expose_btc15_generated_runtime_v1.py && python expose_btc15_generated_runtime_v1.py > generated_runtime_readonly.py

Then inspect only:
grep -nE '^(import|from) |execv|subprocess|main\(|install\(' generated_runtime_readonly.py

Do not execute generated_runtime_readonly.py.
Do not edit main.
Do not deploy this branch to the production service.
Do not modify protected EARLY/FINAL/SCALP/BRTI or NO-ORDERS behavior.
