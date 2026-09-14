#!/usr/bin/env python3
"""
BTC15 EARLY ladder research pipeline V2.

READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS

V2 preserves the frozen V1 research sequence and adds a final contract-story
audit so each PRE-WATCH can be traced through handoff, Tier-1, repricing, flip,
or fade without inventing new thresholds.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BASE_PIPELINE = "BTC15_EARLY_LADDER_RESEARCH_PIPELINE_V1.py"
STORY = "BTC15_EARLY_LADDER_CONTRACT_STORY_V1.py"


def run(cmd: list[str], cwd: Path):
    print("\n" + "=" * 100, flush=True)
    print("RUN | " + " ".join(cmd), flush=True)
    print("=" * 100, flush=True)
    p = subprocess.run(cmd, cwd=str(cwd), check=False)
    if p.returncode != 0:
        raise SystemExit(f"PIPELINE V2 STOPPED | exit={p.returncode} | step={cmd[1]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="union_optimizer_processed_snapshot_cache.csv")
    ap.add_argument("--workdir", default=".")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    cache = Path(args.cache)
    if not cache.is_absolute():
        cache = Path.cwd() / cache
    cache = cache.resolve()
    if not cache.exists():
        raise SystemExit(f"Replay cache not found: {cache}")

    for name in [BASE_PIPELINE, STORY]:
        if not (here / name).exists():
            raise SystemExit(f"Missing required research script beside runner: {name}")

    print("BTC15 EARLY LADDER RESEARCH PIPELINE V2")
    print("READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS")
    print(f"cache={cache}")
    print(f"workdir={workdir}")

    # Run the already-frozen V1 sequence unchanged.
    run([
        sys.executable, str(here / BASE_PIPELINE),
        "--cache", str(cache),
        "--workdir", str(workdir),
    ], workdir)

    # Add diagnostic contract stories only after the frozen V1 outputs exist.
    run([
        sys.executable, str(here / STORY),
        "--cache", str(cache),
        "--calls", str(workdir / "early_prewatch_tournament_v1_champion_calls.csv"),
        "--actions", str(workdir / "early_prewatch_handoff_v1_champion_actions.csv"),
        "--rows-out", str(workdir / "early_ladder_contract_story_v1_rows.csv"),
        "--report-out", str(workdir / "early_ladder_contract_story_v1.txt"),
    ], workdir)

    print("\n" + "=" * 100)
    print("PIPELINE V2 COMPLETE")
    print("Frozen V1 methodology preserved | contract-story audit added | NO ORDERS")
    print("Primary decision reports:")
    print("  early_prewatch_tournament_v1.txt")
    print("  early_prewatch_progress_audit_v1.txt")
    print("  early_prewatch_handoff_v1.txt")
    print("  early_ladder_combined_scorecard_v1.txt")
    print("  early_ladder_contract_story_v1.txt")
    print("=" * 100)


if __name__ == "__main__":
    main()
