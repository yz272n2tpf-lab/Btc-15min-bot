#!/usr/bin/env python3
"""Pure promotion-readiness evaluator for rollover regression."""
REQUIRED=("shadow_consecutive_passes","exact_ticker_matches","early_activations","early_publications","orders","regression_suite_pass","core_runtime_mapped")
def ready(e):
 return (e.get("shadow_consecutive_passes",0)>=3 and e.get("exact_ticker_matches",0)>=3
  and e.get("early_activations")==0 and e.get("early_publications")==0 and e.get("orders")==0
  and e.get("regression_suite_pass") is True and e.get("core_runtime_mapped") is True)
