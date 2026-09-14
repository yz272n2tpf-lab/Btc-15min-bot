#!/usr/bin/env python3
"""
Runtime-only syntax repair wrapper for BTC15_EARLY_PREWATCH_HANDOFF_TOURNAMENT_V1.py.

READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS

This wrapper changes NO research rule, threshold, ranking, split, or metric. It only
repairs two malformed nested f-string display lines in the frozen handoff scorer
before compiling the exact source in memory. The scorer logic itself is unchanged.
"""
from pathlib import Path

src_path = Path(__file__).with_name("BTC15_EARLY_PREWATCH_HANDOFF_TOURNAMENT_V1.py")
src = src_path.read_text(encoding="utf-8")
lines = src.splitlines()
out = []
fixed = 0
for line in lines:
    if "median lead to Tier-1=" in line and "val_s[" in line:
        indent = line[: len(line) - len(line.lstrip())]
        out.append(
            indent
            + 'f"median lead to Tier-1={(\'—\' if pd.isna(val_s[\'median_tier1_lead_sec\']) else format(val_s[\'median_tier1_lead_sec\'], \'.0f\') + \'s\')}"'
        )
        fixed += 1
    elif "median lead to Tier-1=" in line and "rep_s[" in line:
        indent = line[: len(line) - len(line.lstrip())]
        out.append(
            indent
            + 'f"median lead to Tier-1={(\'—\' if pd.isna(rep_s[\'median_tier1_lead_sec\']) else format(rep_s[\'median_tier1_lead_sec\'], \'.0f\') + \'s\')}"'
        )
        fixed += 1
    else:
        out.append(line)

if fixed != 2:
    raise RuntimeError(f"Expected exactly 2 malformed display lines; found {fixed}. Refusing to alter scorer.")

patched = "\n".join(out) + "\n"
print("EARLY HANDOFF FIXED RUNNER V1 | syntax-only repair=2 | frozen logic unchanged | NO ORDERS", flush=True)
g = {"__name__": "__main__", "__file__": str(src_path)}
exec(compile(patched, str(src_path), "exec"), g, g)
