#!/usr/bin/env python3
"""Pure outage policy for staged rollover metadata."""
def outage_action(staged,now):
 if staged is None:return "NO_STAGE"
 if now < staged.open_time:return "HOLD_PREOPEN"
 if now >= staged.close_time:return "EXPIRE_FAIL_CLOSED"
 return "HOLD_VERIFY_RETRY"
