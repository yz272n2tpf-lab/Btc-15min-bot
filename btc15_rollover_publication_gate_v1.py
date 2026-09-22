#!/usr/bin/env python3
"""Pure publication guard for rollover readiness. Offline only."""
def may_publish(*,handoff_verified,alignment_ok,provenance_ok,book_ready,source_fresh):
 return all((handoff_verified,alignment_ok,provenance_ok,book_ready,source_fresh))
