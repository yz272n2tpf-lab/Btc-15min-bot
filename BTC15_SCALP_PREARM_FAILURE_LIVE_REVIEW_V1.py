#!/usr/bin/env python3
"""One-shot live prearm false-start profile. Hypothesis generation only. NO ORDERS."""
from __future__ import annotations

import json

import BTC15_SCALP_PREARM_FAILURE_PROFILE_V1 as profile
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_PREARM_FAILURE_LIVE_REVIEW_V1"


def main() -> int:
    rows, sha = forward.fetch_csv_rows()
    out = profile.audit(rows)
    compact = {}
    for field, raw in (out.get("field_profiles") or {}).items():
        groups = raw.get("groups") or {}
        compact[field] = {
            "plus10_median": (groups.get("PLUS10_OR_BETTER") or {}).get("median"),
            "armed_sub10_median": (groups.get("ARMED_SUB10") or {}).get("median"),
            "unarmed_sub5_median": (groups.get("UNARMED_SUB5") or {}).get("median"),
            "unarmed_minus_plus10": raw.get("unarmed_minus_plus10_median"),
        }
    print(
        "SCALP PREARM FAILURE PROFILE | "
        f"records={out.get('records_n')} | groups={json.dumps(out.get('group_counts') or {}, separators=(',', ':'))} | "
        f"profiles={json.dumps(compact, separators=(',', ':'))} | "
        f"source_sha256={sha} | HYPOTHESIS GENERATION ONLY | NEW FUTURE HOLDOUT REQUIRED | NO ORDERS",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
