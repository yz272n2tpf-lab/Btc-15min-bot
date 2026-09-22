#!/usr/bin/env python3
"""Static change-scope gate: rollover branch must not modify protected signal files."""
PROTECTED_TOKENS=("early","final","scalp","brti","order")
ALLOWED_NEW_PREFIXES=("btc15_rollover_","test_btc15_rollover_","replay_btc15_rollover_","expose_btc15_","test_expose_btc15_","run_btc15_rollover_","BTC15_ROLLOVER_","BTC15_GENERATED_RUNTIME_",".github/workflows/btc15_regression_")
def allowed(path):
 return any(path.startswith(x) for x in ALLOWED_NEW_PREFIXES)
def classify(paths):
 bad=[]
 for p in paths:
  q=p.lower()
  if any(t in q for t in PROTECTED_TOKENS) and not allowed(p):bad.append(p)
 return bad
