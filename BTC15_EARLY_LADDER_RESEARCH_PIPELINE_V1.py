#!/usr/bin/env python3
"""
BTC15 EARLY ladder research pipeline V1.

READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS

Runs the already-frozen EARLY research sequence in a fixed order:
1) PRE-WATCH tournament
2) PRE-WATCH progression audit
3) PRE-WATCH -> actionable handoff tournament
4) combined protected-Tier1 + extension scorecard

This wrapper chooses no thresholds and changes no live behavior. It exists only
so the entire offline EARLY ladder research can be reproduced with one command.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    "BTC15_EARLY_PREWATCH_TOURNAMENT_V1.py",
    "BTC15_EARLY_PREWATCH_PROGRESS_AUDIT_V1.py",
    "BTC15_EARLY_PREWATCH_HANDOFF_TOURNAMENT_V1.py",
    "BTC15_EARLY_LADDER_COMBINED_SCORECARD_V1.py",
]


def run(cmd: list[str], cwd: Path):
    print("\n" + "=" * 100, flush=True)
    print("RUN | " + " ".join(cmd), flush=True)
    print("=" * 100, flush=True)
    p = subprocess.run(cmd, cwd=str(cwd), check=False)
    if p.returncode != 0:
        raise SystemExit(f"PIPELINE STOPPED | exit={p.returncode} | step={cmd[1]}")


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

    print("BTC15 EARLY LADDER RESEARCH PIPELINE V1")
    print("READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS")
    print(f"cache={cache}")
    print(f"workdir={workdir}")

    run([
        sys.executable, str(here / SCRIPTS[0]),
        "--cache", str(cache),
        "--rules-out", "early_prewatch_tournament_v1_rules.csv",
        "--calls-out", "early_prewatch_tournament_v1_champion_calls.csv",
        "--report-out", "early_prewatch_tournament_v1.txt",
    ], workdir)

    run([
        sys.executable, str(here / SCRIPTS[1]),
        "--cache", str(cache),
        "--calls", "early_prewatch_tournament_v1_champion_calls.csv",
        "--rows-out", "early_prewatch_progress_audit_v1_rows.csv",
        "--report-out", "early_prewatch_progress_audit_v1.txt",
    ], workdir)

    run([
        sys.executable, str(here / SCRIPTS[2]),
        "--cache", str(cache),
        "--calls", "early_prewatch_tournament_v1_champion_calls.csv",
        "--rules-out", "early_prewatch_handoff_v1_rules.csv",
        "--actions-out", "early_prewatch_handoff_v1_champion_actions.csv",
        "--report-out", "early_prewatch_handoff_v1.txt",
    ], workdir)

    run([
        sys.executable, str(here / SCRIPTS[3]),
        "--cache", str(cache),
        "--actions", "early_prewatch_handoff_v1_champion_actions.csv",
        "--rows-out", "early_ladder_combined_scorecard_v1_rows.csv",
        "--report-out", "early_ladder_combined_scorecard_v1.txt",
    ], workdir)

    print("\n" + "=" * 100)
    print("PIPELINE COMPLETE")
    print("Protected Tier-1 unchanged | REPORT_ONLY not used for tuning | NO ORDERS")
    print("Primary reports:")
    print("  early_prewatch_tournament_v1.txt")
    print("  early_prewatch_progress_audit_v1.txt")
    print("  early_prewatch_handoff_v1.txt")
    print("  early_ladder_combined_scorecard_v1.txt")
    print("=" * 100)


if __name__ == "__main__":
    main()
