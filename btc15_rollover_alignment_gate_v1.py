#!/usr/bin/env python3
"""Offline timing/alignment invariant for BTC15 staged metadata."""
from datetime import timedelta
def valid_15m(staged):
 return staged.close_time-staged.open_time==timedelta(minutes=15) and staged.open_time.second==0 and staged.open_time.microsecond==0 and staged.open_time.minute%15==0
