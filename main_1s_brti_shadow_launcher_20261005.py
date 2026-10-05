#!/usr/bin/env python3
"""Isolated MAIN qualification launcher. Never production-authorized."""
import fcntl
import os
from pathlib import Path

from btc15_v2_product.release import ROOT, verify_files

DATA_ROOT = Path("/data/btc15_main_shadow_1s")
ASSEMBLY = Path("/tmp/btc15_v2_shadow_1s")


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
    with open("/tmp/btc15-two-clock-shadow-1s.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print("BTC15 MAIN 1S BRTI SHADOW | VERIFIED FROZEN FILES | SIGNAL ONLY | NO ORDERS", flush=True)
        return supervise(assemble(ASSEMBLY), worker_script=ROOT / "btc15_v2_product/worker.py")


if __name__ == "__main__":
    raise SystemExit(main())
