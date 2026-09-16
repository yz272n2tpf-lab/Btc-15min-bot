#!/usr/bin/env python3
"""Build exact V13 shadow HTML and print a fail-closed DOM/text inventory.

PRESENTATION AUDIT ONLY | NO NETWORK WRITES | NO ORDERS
Does not modify production, signal thresholds, or collectors.
"""
from __future__ import annotations

import re
from pathlib import Path

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V13 as v13

TERMS = (
    "FINAL OUTCOME",
    "EARLY OPPORTUNITY",
    "CONTRACT TIMER",
    "REMAINING",
    "BTC",
    "CURRENT PRICE",
    "LIVE BTC",
)

ID_RE = re.compile(r'\bid=["\']([^"\']+)["\']', re.I)
CLASS_RE = re.compile(r'\bclass=["\']([^"\']+)["\']', re.I)
TAG_RE = re.compile(r'<([a-zA-Z0-9]+)([^>]*)>(.*?)</\1>', re.I | re.S)
SCRIPT_STYLE_RE = re.compile(r'<(?:script|style)\b.*?</(?:script|style)>', re.I | re.S)
COMMENT_RE = re.compile(r'<!--.*?-->', re.S)
SPACE_RE = re.compile(r'\s+')


def norm(s: str) -> str:
    return SPACE_RE.sub(" ", re.sub(r'<[^>]+>', ' ', s or '')).strip()


def inventory(html: str) -> dict:
    visible = SCRIPT_STYLE_RE.sub('', COMMENT_RE.sub('', html))
    rows = []
    for m in TAG_RE.finditer(visible):
        tag, attrs, inner = m.groups()
        text = norm(inner)
        if not text:
            continue
        if not any(t.lower() in text.lower() for t in TERMS):
            continue
        ids = ID_RE.findall(attrs)
        classes = CLASS_RE.findall(attrs)
        rows.append({
            "tag": tag.lower(),
            "ids": ids,
            "classes": classes,
            "text": text[:260],
        })
    # Raw ID/class inventory helps when text lives in nested children.
    ids = sorted(set(ID_RE.findall(visible)))
    classes = sorted({c for raw in CLASS_RE.findall(visible) for c in raw.split()})
    return {"rows": rows, "ids": ids, "classes": classes}


def main() -> int:
    path: Path = v13.build_dashboard(run_preflight=False)
    html = path.read_text(encoding="utf-8", errors="replace")
    inv = inventory(html)
    print("BTC15 V13 DOM INVENTORY | GENERATED EXACT HTML | PRESENTATION AUDIT ONLY | NO ORDERS")
    for row in inv["rows"]:
        print("DOM ROW | tag={tag} | ids={ids} | classes={classes} | text={text}".format(**row))
    print("DOM IDS | " + ",".join(inv["ids"]))
    print("DOM CLASSES | " + ",".join(inv["classes"]))
    print(f"DOM COUNTS | rows={len(inv['rows'])} ids={len(inv['ids'])} classes={len(inv['classes'])}")
    # Existing safety invariants remain visible in generated page.
    assert "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS" in html
    assert "flip_risk_percent" not in html
    assert "BTC15_COMBINED_SCALP_UI_V12_NO_POSITION_TRACKING" in html
    assert "BTC15_COMBINED_SCALP_UI_V13_PLAIN_LANGUAGE" in html
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
