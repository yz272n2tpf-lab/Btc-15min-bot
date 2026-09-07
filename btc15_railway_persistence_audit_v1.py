#!/usr/bin/env python3
"""
BTC15 RAILWAY PERSISTENCE / HARDENING AUDIT V1
Read-only. No bot logic changes. No orders.

Purpose:
- identify CSV/log/cache writes in the live Railway entrypoint
- flag relative writes that may disappear on redeploy
- show which files are already routed to /data
"""
from pathlib import Path
import ast

ENTRY = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
PERSIST_ROOT = "/data"

print("="*92)
print("BTC15 RAILWAY PERSISTENCE / HARDENING AUDIT V1")
print("="*92)
print(f"Live entrypoint: {ENTRY}")
print(f"Railway persistent volume: {PERSIST_ROOT}")
print()

if not ENTRY.exists():
    raise SystemExit(f"MISSING live entrypoint: {ENTRY}")

src = ENTRY.read_text(errors="replace")
tree = ast.parse(src)

hits = []

def literal(node):
    try:
        v = ast.literal_eval(node)
        return v if isinstance(v, str) else None
    except Exception:
        return None

for n in ast.walk(tree):
    # open("file","a/w/x")
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open":
        if n.args:
            p = literal(n.args[0])
            mode = literal(n.args[1]) if len(n.args) > 1 else "r"
            if p and mode and any(x in mode for x in "awx+"):
                hits.append((n.lineno, "open", p, mode))

    # df.to_csv("file"), Path(...).write_text, etc.
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
        name = n.func.attr
        if name in {"to_csv","to_json","to_pickle","write_text","write_bytes"} and n.args:
            p = literal(n.args[0])
            if p:
                hits.append((n.lineno, name, p, ""))

# Also catch literal Path("...csv") declarations because later .to_csv(PATH) won't be literal.
for n in ast.walk(tree):
    if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
        f=n.value.func
        if ((isinstance(f,ast.Name) and f.id=="Path") or
            (isinstance(f,ast.Attribute) and f.attr=="Path")) and n.value.args:
            p=literal(n.value.args[0])
            if p and any(p.lower().endswith(ext) for ext in (".csv",".json",".log",".txt",".pkl")):
                names=[]
                for t in n.targets:
                    if isinstance(t,ast.Name): names.append(t.id)
                hits.append((n.lineno, "Path declaration", p, ",".join(names)))

# dedupe
seen=set()
clean=[]
for h in sorted(hits):
    if h not in seen:
        clean.append(h); seen.add(h)

if not clean:
    print("No literal file-write targets found. Dynamic paths may still exist.")
else:
    print("FILE / CACHE TARGETS FOUND")
    print("-"*92)
    risky=0
    persistent=0
    for line,kind,p,detail in clean:
        is_persistent = p.startswith("/data/") or p == "/data"
        state = "PERSISTENT" if is_persistent else "RELATIVE"
        if is_persistent: persistent += 1
        else: risky += 1
        extra=f" | {detail}" if detail else ""
        print(f"L{line:<5} {state:<10} | {kind:<16} | {p}{extra}")

    print()
    print("SUMMARY")
    print("-"*92)
    print(f"Persistent /data targets: {persistent}")
    print(f"Relative targets:         {risky}")
    if risky:
        print("ACTION: relative runtime outputs should be reviewed before any production hardening change.")
        print("Do NOT mass-rewrite paths yet; first confirm which files are runtime state vs static inputs.")
    else:
        print("PASS: all detected literal runtime targets already point at /data.")

print()
print("GUARDRAILS")
print("-"*92)
print("READ-ONLY AUDIT. No source files changed. No thresholds changed. No orders.")
print("="*92)
