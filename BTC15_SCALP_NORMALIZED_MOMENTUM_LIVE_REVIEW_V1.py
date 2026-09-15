#!/usr/bin/env python3
"""One-shot live review for predeclared normalized-momentum research. NO ORDERS."""
from __future__ import annotations

import json

import BTC15_SCALP_NORMALIZED_MOMENTUM_RESEARCH_V1 as study
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_NORMALIZED_MOMENTUM_LIVE_REVIEW_V1"


def _fmt(v, digits=3):
    if v is None:
        return "NA"
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return str(v)


def main() -> int:
    rows, sha = forward.fetch_csv_rows()
    out = study.audit(rows)
    nominee = out.get("development_nominee") or {}
    hold = out.get("holdout_nominee") or {}
    dev_base = out.get("development_baseline") or {}
    hold_base = out.get("holdout_baseline") or {}
    decision = (
        "HOLDOUT_SUPPORTS_NOMINEE"
        if out.get("holdout_supports_nominee") is True
        else "HOLDOUT_REJECTS_NOMINEE"
        if out.get("holdout_review_ready") is True
        else "NO_DEVELOPMENT_NOMINEE"
        if not nominee
        else "WAITING_FOR_HOLDOUT"
    )
    print(
        "SCALP NORMALIZED MOMENTUM REVIEW | "
        f"decision={decision} | records={out.get('records_n')} | "
        f"dev_n={out.get('development_n')} | dev_base_+10={_fmt(dev_base.get('plus10_rate'))} | "
        f"feature={nominee.get('feature','-')} | q={_fmt(nominee.get('development_quantile'),2)} | "
        f"threshold={_fmt(nominee.get('threshold'),6)} | "
        f"dev_nom_n={nominee.get('n','-')} | dev_nom_+10={_fmt(nominee.get('plus10_rate'))} | "
        f"dev_lift={_fmt(nominee.get('plus10_precision_lift'))} | "
        f"dev_winner_retention={_fmt(nominee.get('plus10_winner_retention'))} | "
        f"dev_selected_retention={_fmt(nominee.get('selected_share_retained'))} | "
        f"hold_n={out.get('holdout_n')} | hold_base_+10={_fmt(hold_base.get('plus10_rate'))} | "
        f"hold_nom_n={hold.get('n','-')} | hold_nom_+10={_fmt(hold.get('plus10_rate'))} | "
        f"hold_lift={_fmt(hold.get('plus10_precision_lift'))} | "
        f"hold_winner_retention={_fmt(hold.get('plus10_winner_retention'))} | "
        f"hold_selected_retention={_fmt(hold.get('selected_share_retained'))} | "
        f"support={out.get('holdout_supports_nominee')} | "
        "RESEARCH ONLY | NO AUTO-PROMOTE | NO ORDERS",
        flush=True,
    )
    print(
        "SCALP NORMALIZED MOMENTUM CELLS | "
        f"cells={json.dumps(out.get('development_cells') or [], separators=(',', ':'))} | "
        f"source_sha256={sha} | RESEARCH ONLY | NO ORDERS",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
