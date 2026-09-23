#!/usr/bin/env python3
"""
BTC15 existing Rescue V2 wrapper + independent Kalshi/BRTI parity shadow.

The already-tested Rescue V2 wrapper remains unchanged.
Parity runs as a separate child process.
If parity ever exits, the Rescue/core process is allowed to keep running.
NO ORDERS.
"""
from pathlib import Path
import signal
import subprocess
import sys
import time
from btc15_shadow_supervisor_v1 import ShadowChild

CORE = Path("btc15_run_with_rescue_v2_shadow_v1.py")
PARITY = Path("btc15_kalshi_parity_shadow_v1.py")

def main():
    if "--self-test" in sys.argv:
        missing = [str(p) for p in (CORE,PARITY) if not p.exists()]
        if missing:
            raise SystemExit("SELF-TEST FAIL: missing " + ", ".join(missing))
        print("BTC15 RESCUE + PARITY META-WRAPPER SELF-TEST: PASS")
        print("Existing Rescue wrapper present: YES")
        print("Parity collector present: YES")
        print("Orders enabled: NO")
        return 0

    for p in (CORE,PARITY):
        if not p.exists():
            raise SystemExit(f"STOP: missing {p}")

    print("="*84, flush=True)
    print("BTC15 RESCUE V2 + KALSHI PARITY SHADOW RUNNER: STARTING", flush=True)
    print("Existing Rescue V2 wrapper: UNCHANGED", flush=True)
    print("Kalshi/BRTI parity collector: SHADOW / READ-ONLY", flush=True)
    print("NO ORDERS", flush=True)
    print("="*84, flush=True)

    core = subprocess.Popen([sys.executable,"-u",str(CORE)])
    parity = ShadowChild(PARITY)

    def stop(signum, frame):
        parity.stop()
        if core.poll() is None:
            core.terminate()

    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)

    try:
        while True:
            rc = core.poll()
            if rc is not None:
                break

            parity.maintain()

            time.sleep(2)
    finally:
        parity.stop()
        if core.poll() is None:
            core.terminate()

    return core.returncode or 0

if __name__ == "__main__":
    raise SystemExit(main())
