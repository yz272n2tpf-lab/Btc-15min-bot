#!/usr/bin/env python3
from pathlib import Path
import subprocess

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
if not BOT.exists():
    raise SystemExit(f"STOP: missing {BOT}")

text = BOT.read_text(encoding="utf-8", errors="ignore")

bad = "KALSHI_KEY_ID = KALSHI_KEY_ID"
good = 'KALSHI_KEY_ID = (__import__("os").getenv("KALSHI_KEY_ID") or Path.home().joinpath(".kalshi/key_id").read_text()).strip()'

count = text.count(bad)
if count != 1:
    raise SystemExit(f"STOP: expected exactly 1 broken self-assignment, found {count}. Nothing changed.")

text = text.replace(bad, good, 1)
BOT.write_text(text, encoding="utf-8")

check = BOT.read_text(encoding="utf-8", errors="ignore")
if "KALSHI_KEY_ID = KALSHI_KEY_ID" in check:
    raise SystemExit("STOP: broken self-assignment still present.")
if 'os.getenv("KALSHI_KEY_ID")' not in check and '__import__("os").getenv("KALSHI_KEY_ID")' not in check:
    raise SystemExit("STOP: Railway KALSHI_KEY_ID environment read not found.")

subprocess.run(["python", "-m", "py_compile", str(BOT)], check=True)
print("PASS: fixed KALSHI_KEY_ID self-assignment.")
print("PASS: Railway KALSHI_KEY_ID env read confirmed.")
print("PASS: Python compile check.")

subprocess.run(["git", "add", "--", str(BOT)], check=True)
commit = subprocess.run(
    ["git", "commit", "-m", "Fix Railway Kalshi key ID initialization"],
    text=True, capture_output=True
)
combined = (commit.stdout or "") + (commit.stderr or "")
if commit.returncode != 0 and "nothing to commit" not in combined.lower():
    print(combined)
    raise SystemExit(commit.returncode)

push = subprocess.run(["git", "push", "origin", "main"], text=True, capture_output=True)
print(push.stdout or push.stderr)
if push.returncode != 0:
    raise SystemExit("STOP: fix committed but push failed.")

print("RESULT: PASS — key-ID initialization fixed and pushed to GitHub.")
print("NEXT: Railway should auto-redeploy. Do not change Variables.")
