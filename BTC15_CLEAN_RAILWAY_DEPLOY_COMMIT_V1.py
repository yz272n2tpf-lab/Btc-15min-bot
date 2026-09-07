#!/usr/bin/env python3
"""
BTC15 CLEAN RAILWAY DEPLOY COMMIT V1

Stages ONLY the production-deployment files listed below.
It does NOT stage the other hundreds of untracked research files.

It then creates one clean Git commit and pushes main to origin.
If push fails (for auth/network), the commit remains local and the script prints
the exact one-line push command to run.

No trading logic is modified.
"""

from pathlib import Path
import subprocess, sys

FILES = [
    "bot_two_output_build_v4_13_profit_protection_shadow.py",
    "BTC15_CORE_PRODUCTION_CANDIDATE_LOCK_V1.py",
    "score_v4_13_forward_run.py",
    "score_union_coverage_gap_audit_v1.py",
    "BTC15_FINAL_POSITION_PROTECTION_SHADOW_V2.py",
]

def run(args, check=True):
    p = subprocess.run(args, text=True, capture_output=True)
    if check and p.returncode != 0:
        print("COMMAND FAILED:", " ".join(args))
        print((p.stdout or "") + (p.stderr or ""))
        raise SystemExit(p.returncode)
    return p

print("="*72)
print("BTC15 CLEAN RAILWAY DEPLOY COMMIT V1")
print("="*72)

missing = [f for f in FILES if not Path(f).exists()]
if missing:
    print("STOP — required file(s) missing:")
    for f in missing:
        print(" -", f)
    raise SystemExit(2)

branch = run(["git","branch","--show-current"]).stdout.strip()
print("Branch:", branch)
if branch != "main":
    print("STOP — expected branch main.")
    raise SystemExit(2)

# Stage only the exact deployment files.
run(["git","add","--",*FILES])

staged = run(["git","diff","--cached","--name-only"]).stdout.splitlines()
print()
print("STAGED FILES:")
for f in staged:
    print(" -", f)

unexpected = [f for f in staged if f not in FILES]
if unexpected:
    print()
    print("STOP — unexpected staged files found:")
    for f in unexpected:
        print(" -", f)
    print("Nothing was committed.")
    run(["git","reset"], check=False)
    raise SystemExit(3)

if not staged:
    print("Nothing new to commit. Files may already be committed.")
else:
    msg = "Lock BTC15 production candidate for Railway deployment"
    commit = run(["git","commit","-m",msg], check=False)
    print()
    print(commit.stdout or commit.stderr)
    if commit.returncode != 0:
        text = (commit.stdout or "") + (commit.stderr or "")
        if "nothing to commit" not in text.lower():
            raise SystemExit(commit.returncode)

print()
print("PUSHING origin/main...")
push = run(["git","push","origin","main"], check=False)
if push.returncode == 0:
    print(push.stdout or push.stderr)
    print()
    print("="*72)
    print("RESULT: PASS — clean production deploy commit is on GitHub.")
    print("NEXT: return to Railway and choose GitHub Repository.")
    print("="*72)
else:
    print((push.stdout or "") + (push.stderr or ""))
    print()
    print("="*72)
    print("RESULT: COMMIT CREATED, BUT PUSH NEEDS AUTH/RETRY.")
    print("Run exactly: git push origin main")
    print("="*72)
