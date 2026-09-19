#!/usr/bin/env python3
"""Offline gate for bounded scalp-unarmed reanalysis. NO NETWORK. NO ORDERS."""
import ast,pathlib
p=pathlib.Path(__file__).with_name("btc15_scalp_unarmed_live_tape_validator_v1.py")
s=p.read_text();ast.parse(s)
for x in ["MIN_REANALYZE_SEC","_LAST_SOURCE_SHA","analysis_skipped_unchanged_source","del rows","NO ORDERS"]:
 if x not in s:raise SystemExit("STOP missing optimization invariant: "+x)
# No protected rule constants or order capability are introduced by this optimization.
for x in ["requests.post(","requests.put(","requests.patch(","requests.delete("]:
 if x in s:raise SystemExit("STOP write-capable HTTP introduced: "+x)
print("SCALP_UNARMED_MEMORY_OPT_STATIC_PASS | bounded unchanged-source reanalysis | NO ORDERS")
