#!/usr/bin/env python3
"""
BTC15 full validation runner.

Existing Rescue V2 + parity runner remains unchanged.
Adds FINAL position-protection telemetry as a separate shadow child.
Any protection collector failure must NOT stop the core bot.
NO ORDERS.
"""
from pathlib import Path
import signal
import subprocess
import sys
import time
from btc15_shadow_supervisor_v1 import ShadowChild

CORE = Path("btc15_run_with_rescue_v2_and_parity_v1.py")
PROTECT = Path("btc15_final_position_protection_shadow_v3.py")
OBSERVER = Path("btc15_qualified_forward_observer_v1.py")

def main():
    if "--self-test" in sys.argv:
        missing = [str(p) for p in (CORE,PROTECT,OBSERVER) if not p.exists()]
        if missing:
            raise SystemExit("SELF-TEST FAIL: missing " + ", ".join(missing))
        print("BTC15 FULL VALIDATION RUNNER SELF-TEST: PASS")
        print("Rescue + parity runner present: YES")
        print("Position-protection collector present: YES")
        print("Orders enabled: NO")
        return 0

    for p in (CORE,PROTECT,OBSERVER):
        if not p.exists():
            raise SystemExit(f"STOP: missing {p}")

    print("="*88, flush=True)
    print("BTC15 FULL VALIDATION RUNNER: STARTING", flush=True)
    print("Core + Rescue V2 + parity: UNCHANGED", flush=True)
    print("FINAL position protection: PROSPECTIVE SHADOW / RAW TELEMETRY", flush=True)
    print("NO ORDERS", flush=True)
    print("="*88, flush=True)

    core = subprocess.Popen([sys.executable,"-u",str(CORE)])
    protect = ShadowChild(PROTECT)
    observer = ShadowChild(OBSERVER)

    def stop(signum, frame):
        protect.stop()
        observer.stop()
        if core.poll() is None:
            core.terminate()

    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)

    try:
        while True:
            rc = core.poll()
            if rc is not None:
                break

            protect.maintain()
            observer.maintain()

            time.sleep(2)
    finally:
        protect.stop()
        observer.stop()
        if core.poll() is None:
            core.terminate()

    return core.returncode or 0

if __name__ == "__main__":
    raise SystemExit(main())
