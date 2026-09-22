#!/usr/bin/env python3
"""Pure monotonic rollover guard. Prevents regression to older/equal windows."""
def monotonic(last_open,new_open):
 if new_open is None:return False
 if last_open is None:return True
 return new_open>last_open
