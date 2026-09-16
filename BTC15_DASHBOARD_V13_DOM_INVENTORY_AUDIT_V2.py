#!/usr/bin/env python3
"""Build exact V13 shadow HTML and print a fail-closed DOM/text inventory.

V2 corrects the V13 builder signature discovered by isolated V14 audit V1.
PRESENTATION AUDIT ONLY | NO NETWORK WRITES | NO ORDERS
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
OPEN_TAG_RE = re.compile(r'<([a-zA-Z0-9]+)([^>]*)>', re.I)
SCRIPT_STYLE_RE = re.compile(r'<(?:script|style)\b.*?</(?:script|style)>', re.I | re.S)
COMMENT_RE = re.compile(r'<!--.*?-->', re.S)
SPACE_RE = re.compile(r'\s+')


def norm(s: str) -> str:
    return SPACE_RE.sub(" ", re.sub(r'<[^>]+>', ' ', s or '')).strip()


def snippets(html: str) -> list[dict]:
    visible = SCRIPT_STYLE_RE.sub('', COMMENT_RE.sub('', html))
    out = []
    # Search compact windows around each visible term, then identify nearest opening tag.
    lower = visible.lower()
    seen = set()
    for term in TERMS:
        pos = 0
        needle = term.lower()
        while True:
            i = lower.find(needle, pos)
            if i < 0:
                break
            pos = i + len(needle)
            start = max(0, visible.rfind('<', 0, i))
            lo = max(0, i - 600)
            hi = min(len(visible), i + 600)
            window = visible[lo:hi]
            # Last opening tag before the term inside local window.
            local_before = visible[lo:i]
            matches = list(OPEN_TAG_RE.finditer(local_before))
            tag = matches[-1].group(1).lower() if matches else ''
            attrs = matches[-1].group(2) if matches else ''
            ids = ID_RE.findall(attrs)
            classes = CLASS_RE.findall(attrs)
            key = (term, tag, tuple(ids), tuple(classes), norm(window)[:180])
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "term": term,
                "tag": tag,
                "ids": ids,
                "classes": classes,
                "text": norm(window)[:360],
            })
    return out


def main() -> int:
    path: Path = v13.build_dashboard()
    html = path.read_text(encoding="utf-8", errors="replace")
    visible = SCRIPT_STYLE_RE.sub('', COMMENT_RE.sub('', html))
    rows = snippets(html)
    ids = sorted(set(ID_RE.findall(visible)))
    classes = sorted({c for raw in CLASS_RE.findall(visible) for c in raw.split()})
    print("BTC15 V13 DOM INVENTORY V2 | GENERATED EXACT HTML | PRESENTATION AUDIT ONLY | NO ORDERS")
    for row in rows:
        print("DOM ROW | term={term} | tag={tag} | ids={ids} | classes={classes} | text={text}".format(**row))
    print("DOM IDS | " + ",".join(ids))
    print("DOM CLASSES | " + ",".join(classes))
    print(f"DOM COUNTS | rows={len(rows)} ids={len(ids)} classes={len(classes)}")
    assert "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS" in html
    assert "flip_risk_percent" not in html
    assert "BTC15_COMBINED_SCALP_UI_V12_NO_POSITION_TRACKING" in html
    assert "BTC15_COMBINED_SCALP_UI_V13_PLAIN_LANGUAGE" in html
    assert "FINAL OUTCOME" in html
    assert "CONTRACT TIMER" in html
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
