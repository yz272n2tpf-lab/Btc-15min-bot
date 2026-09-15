#!/usr/bin/env python3
"""One-shot live review for SCALP sub-10c outcome taxonomy. NO ORDERS."""
from __future__ import annotations

import json

import BTC15_SCALP_SUB10_OUTCOME_TAXONOMY_V1 as taxonomy
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_SUB10_OUTCOME_LIVE_REVIEW_V1"


def _fmt(v, digits=3):
    if v is None:
        return "NA"
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return str(v)


def main() -> int:
    rows, sha = forward.fetch_csv_rows()
    out = taxonomy.audit(rows)
    print(
        "SCALP SUB10 OUTCOME REVIEW | "
        f"n={out.get('n')} | +5={out.get('plus5_n')}/{out.get('n')} ({_fmt(out.get('plus5_rate'))}) | "
        f"+10={out.get('plus10_n')}/{out.get('n')} ({_fmt(out.get('plus10_rate'))}) | "
        f"sub10={out.get('sub10_n')} | unarmed_sub5={out.get('unarmed_sub5_n')} | "
        f"armed_sub10={out.get('armed_sub10_n')} | "
        f"armed_sub10_exit={out.get('armed_sub10_protected_exit_n')} | "
        f"armed_sub10_no_exit={out.get('armed_sub10_no_validated_exit_n')} | "
        f"positive_sub10_protected_exits={out.get('positive_protected_exit_sub10_n')} | "
        f"positive_sub10_exit_rate={_fmt(out.get('positive_protected_exit_sub10_rate_among_protected_sub10'))} | "
        "DESCRIPTIVE ONLY | NO RULE CHANGE | NO ORDERS",
        flush=True,
    )
    print(
        "SCALP SUB10 OUTCOME DETAIL | "
        f"peak_bands={json.dumps(out.get('peak_band_counts') or {}, separators=(',', ':'))} | "
        f"classes={json.dumps(out.get('classification_counts') or {}, separators=(',', ':'))} | "
        f"stats={json.dumps(out.get('category_stats') or {}, separators=(',', ':'))} | "
        f"source_sha256={sha} | DESCRIPTIVE ONLY | NO ORDERS",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
