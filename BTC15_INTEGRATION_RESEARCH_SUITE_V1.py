#!/usr/bin/env python3
"""
BTC15 integration research suite V1.

READ-ONLY / LOCAL CONTAINER VALIDATION | SIGNAL ONLY | NO ORDERS

Runs the next safe offline checks in one pass:
1. generalized dashboard patch unit tests,
2. combined live-smoke monitor envelope tests,
3. frozen EARLY high-confidence scorer guardrail tests,
4. generalized dashboard installer/patch self-test,
5. frozen EARLY high-confidence historical scorer.

No live production service is mutated by this script. The dashboard installer
writes only inside this runner container; scorer outputs go to the chosen workdir.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def run(cmd: list[str], *, cwd: Path) -> None:
    print("\n" + "="*100, flush=True)
    print("RUN | " + " ".join(cmd), flush=True)
    print("="*100, flush=True)
    p=subprocess.run(cmd,cwd=str(cwd),check=False)
    if p.returncode != 0:
        raise SystemExit(f"RESEARCH SUITE STOPPED | exit={p.returncode} | step={cmd[1] if len(cmd)>1 else cmd[0]}")


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--cache",default="union_optimizer_processed_snapshot_cache.csv")
    ap.add_argument("--workdir",default="/tmp/btc15_integration_research_v1")
    args=ap.parse_args()

    here=Path(__file__).resolve().parent
    work=Path(args.workdir).resolve();work.mkdir(parents=True,exist_ok=True)
    cache=Path(args.cache)
    if not cache.is_absolute(): cache=(here/cache).resolve()
    if not cache.exists(): raise SystemExit(f"replay cache missing: {cache}")

    tests=[
        "test_BTC15_DASHBOARD_GENERALIZED_SCALP_V1.py",
        "test_btc15_combined_live_smoke_monitor_v1.py",
        "test_BTC15_EARLY_HIGH_CONFIDENCE_SCORER_V1.py",
    ]
    for name in tests:
        if not (here/name).exists(): raise SystemExit(f"missing test: {name}")

    run([sys.executable,"-m","unittest",*tests],cwd=here)

    run([
        sys.executable,str(here/"BTC15_DASHBOARD_GENERALIZED_SCALP_V1.py"),"--self-test"
    ],cwd=here)

    run([
        sys.executable,str(here/"BTC15_EARLY_HIGH_CONFIDENCE_SCORER_V1.py"),
        "--cache",str(cache),
        "--rules-out",str(work/"early_high_confidence_v1_rules.csv"),
        "--calls-out",str(work/"early_high_confidence_v1_calls.csv"),
        "--report-out",str(work/"early_high_confidence_v1.txt"),
    ],cwd=work)

    print("\n"+"="*100)
    print("BTC15 INTEGRATION RESEARCH SUITE V1 COMPLETE | ALL STEPS EXIT 0 | NO ORDERS")
    print(f"outputs={work}")
    print("="*100)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
