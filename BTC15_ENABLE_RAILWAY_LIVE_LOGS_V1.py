#!/usr/bin/env python3
from pathlib import Path
import json
import subprocess

CFG = Path("railway.json")
if not CFG.exists():
    raise SystemExit("STOP: railway.json not found")

data = json.loads(CFG.read_text(encoding="utf-8"))
deploy = data.setdefault("deploy", {})
old = deploy.get("startCommand", "")

target = "python -u bot_two_output_build_v4_13_profit_protection_shadow.py"
deploy["startCommand"] = target

CFG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print("PASS: Railway logging set to unbuffered mode.")
print("Start command:", target)

subprocess.run(["git", "add", "--", str(CFG)], check=True)
commit = subprocess.run(
    ["git", "commit", "-m", "Enable live Railway logs"],
    text=True, capture_output=True
)
combined = (commit.stdout or "") + (commit.stderr or "")
if commit.returncode != 0 and "nothing to commit" not in combined.lower():
    print(combined)
    raise SystemExit(commit.returncode)

push = subprocess.run(["git", "push", "origin", "main"], text=True, capture_output=True)
print(push.stdout or push.stderr)
if push.returncode != 0:
    raise SystemExit("STOP: config changed, but push failed. Run: git push origin main")

print("RESULT: PASS — live Railway logging enabled and pushed.")
