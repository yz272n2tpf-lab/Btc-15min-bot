#!/usr/bin/env python3
"""Pure evidence snapshot for rollover promotion gate. Offline only."""
from btc15_rollover_promotion_gate_v1 import ready
EVIDENCE={
 "shadow_consecutive_passes":4,
 "exact_ticker_matches":4,
 "early_activations":0,
 "early_publications":0,
 "orders":0,
 "regression_suite_pass":False,
 "core_runtime_mapped":False,
}
if __name__=="__main__":
 print(EVIDENCE)
 print("PROMOTION_READY",ready(EVIDENCE))
