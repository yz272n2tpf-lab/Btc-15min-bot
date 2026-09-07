#!/usr/bin/env python3
from pathlib import Path
import subprocess

CRITICAL = [
    "bot_two_output_build_v4_13_profit_protection_shadow.py",
    "BTC15_CORE_PRODUCTION_CANDIDATE_LOCK_V1.py",
    "score_v4_13_forward_run.py",
    "score_union_coverage_gap_audit_v1.py",
]

def run(*args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip()

print("="*64)
print("BTC15 RAILWAY DEPLOY PRECHECK")
print("="*64)

branch = run("git","branch","--show-current") or "UNKNOWN"
status = run("git","status","--porcelain")
short = run("git","status","-sb")

print("BRANCH:", branch)
print("REPO:", short.splitlines()[0] if short else "UNKNOWN")
print()

print("PRODUCTION-CRITICAL FILES")
for name in CRITICAL:
    p = Path(name)
    tracked = run("git","ls-files","--error-unmatch",name)
    is_tracked = bool(tracked) and "error" not in tracked.lower()
    state = "MISSING" if not p.exists() else ("TRACKED" if is_tracked else "UNTRACKED")
    print(f"{state:10s} {name}")

print()
changed = []
for line in status.splitlines():
    path = line[3:] if len(line) > 3 else ""
    if any(path.endswith(x) for x in CRITICAL):
        changed.append(line)

print("CRITICAL GIT CHANGES")
if changed:
    for line in changed:
        print(line)
else:
    print("NONE")

print()
print("TOTAL UNCOMMITTED ITEMS:", len(status.splitlines()) if status else 0)

print("="*64)
if any(not Path(x).exists() for x in CRITICAL):
    print("RESULT: STOP — a required production file is missing.")
elif changed or any("UNTRACKED" in line for line in []):
    print("RESULT: REVIEW — production-critical files need a clean deploy commit.")
else:
    print("RESULT: PRODUCTION FILES FOUND. NEXT: create clean Railway deploy commit.")
print("="*64)
