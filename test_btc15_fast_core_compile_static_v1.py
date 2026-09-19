#!/usr/bin/env python3
"""Compile/static gate for isolated optimized core."""
import ast,pathlib
p=pathlib.Path(__file__).with_name("bot_two_output_build_v4_13_profit_protection_shadow.py")
s=p.read_text(encoding="utf-8")
ast.parse(s,filename=str(p))
must=[
'Training history download: SKIPPED | certified artifact mode',
'GENERAL RF: CERTIFIED FITTED ARTIFACT | RETRAIN SKIPPED',
'GENERAL RF WALK-FORWARD/THRESHOLD DIAGNOSTICS: SKIPPED | certified artifact mode',
'FAIR HISTORICAL RECONSTRUCTION: SKIPPED | certified artifact mode',
'FINAL OUTCOME — END OF 15-MIN CONTRACT',
'EARLY OPPORTUNITY — TARGET-AWARE / NOT FINAL OUTCOME',
'DIRECT_BRTI_AUTH_MAX_AGE_SECONDS = 5.0',
'DIRECT_BRTI_AUTH_WAIT_DOLLARS = 11.0']
for x in must:
 if x not in s:raise SystemExit("STOP missing "+x)
print("FAST_CORE_COMPILE_STATIC_PASS")
