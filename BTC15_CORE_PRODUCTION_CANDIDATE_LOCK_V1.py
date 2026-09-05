#!/usr/bin/env python3
"""
BTC15 CORE PRODUCTION CANDIDATE LOCK V1

Creates a read-only snapshot/copy of the current core candidate so later parity
and integration work cannot accidentally change the proven source.

Does NOT modify the live bot, rules, thresholds, models, or data.
Does NOT include any rejected gap/chop detector.
"""

from pathlib import Path
import hashlib
import json
import shutil
from datetime import datetime, timezone

ROOT = Path(".")
LOCK_DIR = ROOT / "BTC15_CORE_PRODUCTION_CANDIDATE_LOCK_V1"

required = [
    "bot_two_output_build_v4_13_profit_protection_shadow.py",
    "score_v4_13_forward_run.py",
    "score_union_coverage_gap_audit_v1.py",
]

optional = [
    "kalshi_true_scalp_forward_shadow_v1.csv",
    "kalshi_profit_protection_forward_shadow_v1.csv",
    "kalshi_subminute_unified_v1_1.csv",
    "union_coverage_gap_audit_v1_contracts.csv",
    "union_coverage_gap_audit_v1_gaps.csv",
]

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

missing = [name for name in required if not (ROOT / name).exists()]
if missing:
    print("=" * 78)
    print("BTC15 CORE PRODUCTION CANDIDATE LOCK V1")
    print("=" * 78)
    print("STOP: required file(s) missing:")
    for name in missing:
        print(" -", name)
    print("Nothing was locked.")
    raise SystemExit(2)

LOCK_DIR.mkdir(exist_ok=True)

files_to_copy = required + [x for x in optional if (ROOT / x).exists()]
manifest_files = []

for name in files_to_copy:
    src = ROOT / name
    dst = LOCK_DIR / name
    shutil.copy2(src, dst)
    manifest_files.append({
        "name": name,
        "bytes": src.stat().st_size,
        "sha256": sha256(src),
    })

notes = {
    "lock_name": "BTC15_CORE_PRODUCTION_CANDIDATE_LOCK_V1",
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "core_bot": "bot_two_output_build_v4_13_profit_protection_shadow.py",
    "status": "production candidate; not yet production-ready",
    "included_modules": [
        "Frozen FINAL",
        "Frozen primary true scalp",
        "Profit-protection shadow",
        "Direct BRTI authority / parity data",
        "Unified 5-second logging",
    ],
    "excluded_modules": [
        "Rejected early-settlement prediction models",
        "Rejected secondary scalp/gap filler",
        "Rejected chop/reversal gap detector",
        "Rejected 45-second FINAL guardrail",
    ],
    "next_gate": "Kalshi-app parity across consecutive live contracts",
    "signal_only": True,
    "orders_intended": False,
    "files": manifest_files,
}

(LOCK_DIR / "LOCK_MANIFEST.json").write_text(
    json.dumps(notes, indent=2), encoding="utf-8"
)

readme = """BTC15 CORE PRODUCTION CANDIDATE LOCK V1

This folder is a frozen snapshot of the current core candidate.

INCLUDED
- Frozen FINAL
- Frozen primary true scalp
- Profit-protection shadow
- Direct BRTI authority / parity data
- Unified 5-second logging

EXCLUDED
- Early-settlement models that failed validation
- Secondary scalp/gap filler
- Chop/reversal gap detector
- 45-second FINAL guardrail

IMPORTANT
This is NOT yet the final production bot.
Next required gate: Kalshi-app parity across consecutive live contracts.
No automatic order placement is intended.
"""
(LOCK_DIR / "README.txt").write_text(readme, encoding="utf-8")

print("=" * 78)
print("BTC15 CORE PRODUCTION CANDIDATE LOCK V1")
print("=" * 78)
print("LOCK CREATED:", LOCK_DIR)
print()
print("Core bot:", notes["core_bot"])
print("Files locked:", len(manifest_files))
for item in manifest_files:
    print(f"  {item['name']} | sha256 {item['sha256'][:16]}...")
print()
print("INCLUDED: FINAL + primary scalp + profit protection + BRTI + logging")
print("EXCLUDED: rejected early/gap/45s branches")
print("NEXT GATE: Kalshi-app parity across consecutive live contracts")
print("NO CORE LOGIC WAS CHANGED.")
print("=" * 78)
