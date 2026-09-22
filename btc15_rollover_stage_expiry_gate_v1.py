#!/usr/bin/env python3
"""Pure stale-stage expiry guard. Offline only."""
def stage_usable(staged,now):
 if staged is None:return False
 # A staged 15m contract is metadata for exactly its own window; never reuse it after close.
 return staged.open_time <= now < staged.close_time
