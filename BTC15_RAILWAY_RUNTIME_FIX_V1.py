#!/usr/bin/env python3
from pathlib import Path
import ast
import importlib.metadata as md
import platform
import subprocess
import sys
import json

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
SHADOW = Path("BTC15_FINAL_POSITION_PROTECTION_SHADOW_V2.py")

if not BOT.exists():
    raise SystemExit(f"STOP: missing {BOT}")

def top_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names

imports = top_imports(BOT)
if SHADOW.exists():
    imports |= top_imports(SHADOW)

stdlib = set(getattr(sys, "stdlib_module_names", set()))
third_party = sorted(x for x in imports if x not in stdlib and x not in {"__future__"})

pkg_map = md.packages_distributions()
dist_names = set()
manual = {
    "sklearn": "scikit-learn",
    "dateutil": "python-dateutil",
    "bs4": "beautifulsoup4",
    "yaml": "PyYAML",
    "Crypto": "pycryptodome",
    "PIL": "Pillow",
}

unmapped = []
for mod in third_party:
    if mod in manual:
        dist_names.add(manual[mod])
        continue
    dists = pkg_map.get(mod)
    if dists:
        dist_names.add(dists[0])
    else:
        unmapped.append(mod)

requirements = []
for dist in sorted(dist_names, key=str.lower):
    try:
        requirements.append(f"{dist}=={md.version(dist)}")
    except md.PackageNotFoundError:
        requirements.append(dist)

Path("requirements.txt").write_text("\n".join(requirements) + "\n", encoding="utf-8")
pyver = platform.python_version()
Path(".python-version").write_text(pyver + "\n", encoding="utf-8")

railway_cfg = {
    "$schema": "https://railway.com/railway.schema.json",
    "deploy": {
        "startCommand": "python bot_two_output_build_v4_13_profit_protection_shadow.py",
        "restartPolicyType": "ON_FAILURE",
        "restartPolicyMaxRetries": 10
    }
}
Path("railway.json").write_text(json.dumps(railway_cfg, indent=2) + "\n", encoding="utf-8")

print("="*76)
print("BTC15 RAILWAY RUNTIME FIX V1")
print("="*76)
print("Correct start file:", BOT.name)
print("Python pinned to:", pyver)
print()
print("requirements.txt:")
for line in requirements:
    print(" -", line)
if unmapped:
    print()
    print("Local/unmapped imports skipped:")
    for x in unmapped:
        print(" -", x)

deploy_files = ["requirements.txt", ".python-version", "railway.json"]

def run(args, check=True):
    p = subprocess.run(args, text=True, capture_output=True)
    if check and p.returncode != 0:
        print((p.stdout or "") + (p.stderr or ""))
        raise SystemExit(p.returncode)
    return p

run(["git","add","--",*deploy_files])
staged = run(["git","diff","--cached","--name-only"]).stdout.splitlines()
unexpected = [x for x in staged if x not in deploy_files]
if unexpected:
    print("STOP: unexpected staged files:", unexpected)
    run(["git","reset"], check=False)
    raise SystemExit(3)

print()
print("STAGED DEPLOY FILES:")
for x in staged:
    print(" -", x)

if staged:
    c = run(["git","commit","-m","Fix Railway runtime and production start command"], check=False)
    print(c.stdout or c.stderr)
    text = (c.stdout or "") + (c.stderr or "")
    if c.returncode != 0 and "nothing to commit" not in text.lower():
        raise SystemExit(c.returncode)

push = run(["git","push","origin","main"], check=False)
print(push.stdout or push.stderr)
if push.returncode != 0:
    print("RESULT: COMMIT CREATED, PUSH NEEDS RETRY")
    print("Run: git push origin main")
    raise SystemExit(push.returncode)

print("="*76)
print("RESULT: PASS — Railway runtime fix pushed to GitHub.")
print("Railway should auto-redeploy from this commit.")
print("NEXT: watch the new Railway deployment; do NOT press Restart on the old crash.")
print("="*76)
