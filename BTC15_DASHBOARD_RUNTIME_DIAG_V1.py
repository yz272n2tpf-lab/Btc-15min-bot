#!/usr/bin/env python3
"""Runtime source diagnostics for the BTC15 dashboard.

Prints small excerpts from the decoded dashboard HTML before launching the existing
UI-stability wrapper. No trading, scoring, Kalshi, or signal logic changes.
"""
from pathlib import Path
import os
import re
import sys

TERMS = [
    "dashboard_state.json",
    "innerHTML",
    "outerHTML",
    "replaceChildren",
    "setInterval",
    "FINAL OUTCOME",
    "WAITING",
    "LOCK",
    "confidence",
    "chart",
    "price",
]


def excerpt(text: str, term: str, radius: int = 420) -> str | None:
    i = text.lower().find(term.lower())
    if i < 0:
        return None
    a = max(0, i - radius)
    b = min(len(text), i + len(term) + radius)
    s = text[a:b]
    s = re.sub(r"\s+", " ", s)
    return s


def main() -> int:
    import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer
    d = installer.install()
    html = d / "BTC_Kalshi_App_Live_v13.html"
    print("DASH SOURCE DIAG | begin")
    if html.exists():
        text = html.read_text(encoding="utf-8", errors="replace")
        print(f"DASH SOURCE DIAG | html_bytes={len(text)}")
        for term in TERMS:
            hit = excerpt(text, term)
            if hit:
                print(f"DASH SOURCE DIAG | TERM={term} | {hit}")
            else:
                print(f"DASH SOURCE DIAG | TERM={term} | NOT_FOUND")
    else:
        print(f"DASH SOURCE DIAG | missing={html}")
    print("DASH SOURCE DIAG | end")

    target = Path(__file__).with_name("BTC15_DASHBOARD_UI_STABILITY_PATCH_V1.py")
    os.execv(sys.executable, [sys.executable, "-u", str(target), *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
