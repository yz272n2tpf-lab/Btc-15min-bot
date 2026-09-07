#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")

def run(args, check=True):
    p = subprocess.run(args, text=True, capture_output=True)
    if check and p.returncode != 0:
        print((p.stdout or "") + (p.stderr or ""))
        raise SystemExit(p.returncode)
    return p

if not BOT.exists():
    raise SystemExit(f"STOP: missing {BOT}")

text = BOT.read_text(encoding="utf-8", errors="ignore")

required = [
    'print("Training rows:", len(training_data))',
    "current_prediction = model.predict(current_features)[0]",
    '_v3_cal = pd.read_csv("brti_calibration_results.csv")',
    "_strict_model_ready = False",
    "_fair_ready = False",
    'BRTI_PATH = "/trade-api/v2/cfbenchmarks/values"',
    "KEY_ID = KALSHI_KEY_ID",
    "PRIVATE_KEY = kalshi_private_key",
]
missing = [x for x in required if x not in text]
if missing:
    raise SystemExit(
        "STOP: restored production file is incomplete. Missing: "
        + ", ".join(missing)
    )

if len(text.splitlines()) < 3400:
    raise SystemExit("STOP: restored production file is unexpectedly short.")

# Remove trailing spaces/tabs ONLY. No logic changes.
cleaned = "\n".join(line.rstrip(" \t") for line in text.splitlines()) + "\n"
BOT.write_text(cleaned, encoding="utf-8")

run([sys.executable, "-m", "py_compile", str(BOT)])

print("PASS: full restored production file still present.")
print(f"PASS: {len(cleaned.splitlines())} lines verified.")
print("PASS: trailing whitespace cleaned only.")
print("PASS: Python compile check.")

run(["git", "add", "--", str(BOT)])
check = run(["git", "diff", "--cached", "--check"], check=False)
if check.returncode != 0:
    print((check.stdout or "") + (check.stderr or ""))
    raise SystemExit("STOP: git whitespace check still failed. Nothing pushed.")

commit = run(
    ["git", "commit", "-m", "Restore full BTC15 production core and secure Railway auth"],
    check=False,
)
combined = (commit.stdout or "") + (commit.stderr or "")
if commit.returncode != 0 and "nothing to commit" not in combined.lower():
    print(combined)
    raise SystemExit(commit.returncode)

push = run(["git", "push", "origin", "main"], check=False)
print(push.stdout or push.stderr)
if push.returncode != 0:
    raise SystemExit("STOP: commit succeeded but push failed.")

print("RESULT: PASS — full production restore committed and pushed.")
print("NEXT: Railway should auto-redeploy. Do NOT change keys or Variables.")
