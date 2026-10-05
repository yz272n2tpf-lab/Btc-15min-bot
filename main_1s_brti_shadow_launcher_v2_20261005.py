#!/usr/bin/env python3
"""Isolated MAIN qualification launcher. Never production-authorized."""
import fcntl
import os
from pathlib import Path

from btc15_v2_product.release import ROOT, verify_files

DATA_ROOT = Path("/data/btc15_main_shadow_1s")
ASSEMBLY = Path("/tmp/btc15_v2_shadow_1s")
SHADOW_CHILD = ROOT / "btc15_v2_native_shadow_1s_20261005.py"


def main():
    if os.getenv("RAILWAY_VOLUME_MOUNT_PATH") != "/data" or not os.getenv("RAILWAY_VOLUME_ID"):
        raise RuntimeError("SHADOW_VOLUME_REQUIRED")
    if os.getenv("BTC15_ENABLE_INFORMATION_EXPORT") != "1":
        raise RuntimeError("INFORMATION_EXPORT_OPT_IN_REQUIRED")
    verify_files("main")
    os.environ["BTC15_LADDER_DATA_ROOT"] = str(DATA_ROOT)
    os.environ["BTC15_COHORT_EVIDENCE_PATH"] = str(DATA_ROOT / "native-cohort.jsonl")
    from btc15_information_install_v1 import supervise
    from btc15_v2_product.installer import assemble
    d = assemble(ASSEMBLY)
    wrapper = d / "btc15_run_with_rescue_v2_shadow_v1.py"
    text = wrapper.read_text()
    old = str(ROOT / "btc15_v2_native.py")
    if text.count(old) != 1:
        raise RuntimeError("SHADOW_NATIVE_SEAM")
    wrapper.write_text(text.replace(old, str(SHADOW_CHILD)))
    with open("/tmp/btc15-two-clock-shadow-1s.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print("BTC15 MAIN 1S BRTI SHADOW | FROZEN FILES VERIFIED | TEMP ASSEMBLY CHILD OVERRIDE ONLY | SIGNAL ONLY | NO ORDERS", flush=True)
        return supervise(d, worker_script=ROOT / "btc15_v2_product/worker.py")


if __name__ == "__main__":
    raise SystemExit(main())
