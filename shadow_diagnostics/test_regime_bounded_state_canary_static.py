#!/usr/bin/env python3
"""Static semantic gate for Regime bounded-state scaffold."""
import ast,pathlib
p=pathlib.Path(__file__).with_name("scalp_regime_bounded_state_canary_v1.py")
s=p.read_text();ast.parse(s)
must=["2026-09-16T11:03:16+00:00",">=840","<=60","orders=False","first < CUTOFF"]
for x in must:assert x in s,x
for x in ["requests.post(","requests.put(","requests.patch(","requests.delete("]:
    assert x not in s,x
print("REGIME_BOUNDED_STATE_STATIC_OK")
