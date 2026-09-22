#!/usr/bin/env python3
"""Pure provenance guard for staged-to-active handoff."""
def provenance_ok(staged_ticker, active_ticker, quote_ticker, target_ticker=None):
 if not staged_ticker or active_ticker!=staged_ticker:return False
 if quote_ticker!=active_ticker:return False
 if target_ticker is not None and target_ticker!=active_ticker:return False
 return True
