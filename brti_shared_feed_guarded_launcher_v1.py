#!/usr/bin/env python3
"""Guarded launcher for shared BRTI feed V1.

Default state is PARKED and makes ZERO upstream BRTI requests. The feed only
starts when BRTI_SHARED_ENABLE=1 is explicitly present. Infrastructure only.
SIGNAL ONLY. NO ORDERS.
"""
from __future__ import annotations
import os
import sys
import time

ENABLE_ENV = "BRTI_SHARED_ENABLE"


def enabled(env=None) -> bool:
    e = os.environ if env is None else env
    return str(e.get(ENABLE_ENV, "")).strip() == "1"


def self_test() -> int:
    assert enabled({}) is False
    assert enabled({ENABLE_ENV: "0"}) is False
    assert enabled({ENABLE_ENV: "true"}) is False
    assert enabled({ENABLE_ENV: "1"}) is True
    print("BRTI_SHARED_GUARDED_LAUNCHER_SELFTEST | PASS | DEFAULT PARKED | EXPLICIT ENABLE ONLY | NO ORDERS")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    if not enabled():
        print("BRTI SHARED FEED PARKED | BRTI_SHARED_ENABLE!=1 | ZERO UPSTREAM POLLING | NO ORDERS", flush=True)
        while True:
            time.sleep(3600)
    from brti_shared_feed_v1 import main as feed_main
    print("BRTI SHARED FEED ENABLED | EXPLICIT BRTI_SHARED_ENABLE=1 | NO ORDERS", flush=True)
    feed_main()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
