#!/usr/bin/env python3
"""
BTC15 EARLY ladder research pipeline V3.

READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS

V3 preserves every frozen V1/V2 research rule. The only change is routing the
handoff step through BTC15_EARLY_HANDOFF_FIXED_RUNNER_V1.py, which repairs the
known nested-f-string print syntax without changing any scorer logic.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PREWATCH = "BTC15_EARLY_PREWATCH_TOURNAMENT_V1.py"
PROGRESS = "BTC15_EARLY_PREWATCH_PROGRESS_AUDIT_V1.py"
HANDOFF = "BTC15_EARLY_HANDOFF_FIXED_RUNNER_V1.py"
COMBINED = "BTC15_EARLY_LADDER_COMBINED_SCORECARD_V1.py"
STORY = "BTC15_EARLY_LADDER_CONTRACT_STORY_V1.py"
SCRIPTS = [PREWATCH, PROGRESS, HANDOFF, COMBINED, STORY]


def run(cmd: list[str], cwd: Path):
    print("\n" + "=" * 100, flush=True)
    print("RUN | " + " ".join(cmd), flush=True)
    print("=" * 100, flush=True)
    p = subprocess.run(cmd, cwd=str(cwd), check=False)
    if p.returncode != 0:
        raise SystemExit(f"PIPELINE V3 STOPPED | exit={p.returncode} | step={cmd[1]}")


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

    missing = [name for name in SCRIPTS if not (here / name).exists()]
    if missing:
        raise SystemExit("Missing pipeline scripts beside runner: " + ", ".join(missing))

    print("BTC15 EARLY LADDER RESEARCH PIPELINE V3")
    print("READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS")
    print("Frozen methodology unchanged | handoff syntax repair only")
    print(f"cache={cache}")
    print(f"workdir={workdir}")

    run([
        sys.executable, str(here / PREWATCH),
        "--cache", str(cache),
        "--rules-out", "early_prewatch_tournament_v1_rules.csv",
        "--calls-out", "early_prewatch_tournament_v1_champion_calls.csv",
        "--report-out", "early_prewatch_tournament_v1.txt",
    ], workdir)

    run([
        sys.executable, str(here / PROGRESS),
        "--cache", str(cache),
        "--calls", "early_prewatch_tournament_v1_champion_calls.csv",
        "--rows-out", "early_prewatch_progress_audit_v1_rows.csv",
        "--report-out", "early_prewatch_progress_audit_v1.txt",
    ], workdir)

    run([
        sys.executable, str(here / HANDOFF),
        "--cache", str(cache),
        "--calls", "early_prewatch_tournament_v1_champion_calls.csv",
        "--rules-out", "early_prewatch_handoff_v1_rules.csv",
        "--actions-out", "early_prewatch_handoff_v1_champion_actions.csv",
        "--report-out", "early_prewatch_handoff_v1.txt",
    ], workdir)

    run([
        sys.executable, str(here / COMBINED),
        "--cache", str(cache),
        "--actions", "early_prewatch_handoff_v1_champion_actions.csv",
        "--rows-out", "early_ladder_combined_scorecard_v1_rows.csv",
        "--report-out", "early_ladder_combined_scorecard_v1.txt",
    ], workdir)

    run([
        sys.executable, str(here / STORY),
        "--cache", str(cache),
        "--calls", "early_prewatch_tournament_v1_champion_calls.csv",
        "--actions", "early_prewatch_handoff_v1_champion_actions.csv",
        "--rows-out", "early_ladder_contract_story_v1_rows.csv",
        "--report-out", "early_ladder_contract_story_v1.txt",
    ], workdir)

    print("\n" + "=" * 100)
    print("PIPELINE V3 COMPLETE")
    print("Frozen research methodology preserved | syntax repair only | NO ORDERS")
    print("Primary reports:")
    print("  early_prewatch_tournament_v1.txt")
    print("  early_prewatch_progress_audit_v1.txt")
    print("  early_prewatch_handoff_v1.txt")
    print("  early_ladder_combined_scorecard_v1.txt")
    print("  early_ladder_contract_story_v1.txt")
    print("=" * 100)


if __name__ == "__main__":
    main()
