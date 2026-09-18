#!/usr/bin/env python3
"""Static safety tests for Regime incremental transport canary."""
import ast, pathlib
P=pathlib.Path(__file__).with_name("scalp_specialist_union_live_review_v1.py")
s=P.read_text()
ast.parse(s)
required=[
 "X-Chunk-SHA256","incremental offset mismatch",
 "incremental reconstructed snapshot parity mismatch",
 "NO ORDERS",
]
for x in required:
    assert x in s, x
for forbidden in ["requests.post(","requests.put(","requests.patch(","requests.delete("]:
    assert forbidden not in s, forbidden
print("REGIME_INCREMENTAL_CANARY_STATIC_TESTS_OK")
