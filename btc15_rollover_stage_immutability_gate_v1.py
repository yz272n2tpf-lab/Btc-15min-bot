#!/usr/bin/env python3
"""Pure staged-metadata immutability guard."""
def same_stage(a,b):
 if a is None or b is None:return False
 return (a.ticker,a.open_time,a.close_time)==(b.ticker,b.open_time,b.close_time)
