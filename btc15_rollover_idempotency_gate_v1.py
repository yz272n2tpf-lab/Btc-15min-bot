#!/usr/bin/env python3
"""Pure idempotency guard for rollover handoff/publication."""
def accept_once(last_verified_ticker,candidate_ticker):
 if not candidate_ticker:return last_verified_ticker,False
 if candidate_ticker==last_verified_ticker:return last_verified_ticker,False
 return candidate_ticker,True
