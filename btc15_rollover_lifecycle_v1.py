#!/usr/bin/env python3
"""Pure staged-contract lifecycle coordinator. Offline regression artifact only."""
from btc15_rollover_alignment_gate_v1 import valid_15m
from btc15_rollover_handoff_model_v1 import transition
from btc15_rollover_provenance_gate_v1 import provenance_ok
from btc15_rollover_publication_gate_v1 import may_publish
def step(active,staged,now,open_tickers,quote_ticker=None,target_ticker=None,book_ready=False,source_fresh=False):
 new_active,new_staged,action=transition(active,staged,now,open_tickers)
 verified=action=="VERIFIED_HANDOFF"
 aligned=valid_15m(staged) if staged is not None else False
 prov=provenance_ok(staged.ticker,new_active,quote_ticker,target_ticker) if staged is not None and verified else False
 publish=may_publish(handoff_verified=verified,alignment_ok=aligned,provenance_ok=prov,book_ready=book_ready,source_fresh=source_fresh)
 return {"active":new_active,"staged":new_staged,"action":action,"publish":publish}
