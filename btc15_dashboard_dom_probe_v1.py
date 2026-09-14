#!/usr/bin/env python3
"""
BTC15 production dashboard DOM probe V1.

READ ONLY | DOM IDS + RENDER FUNCTION NAMES ONLY | NO VALUES | NO ORDERS

Used only to wire the already-proven combined state into the existing locked
cards without guessing element IDs or creating a second layout.
"""
from __future__ import annotations

from html.parser import HTMLParser
import re
import requests

DASHBOARD_URL = "https://btc-15min-bot-production.up.railway.app/"
KEYWORDS = (
    "final", "early", "scalp", "reversal", "timer", "clock", "contract",
    "kalshi", "quote", "up", "down", "conflict", "status", "action",
    "reason", "state", "flow", "entry", "protect", "exit", "price",
)


class IdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        ident = d.get("id")
        if ident:
            self.ids.append((str(tag), str(ident)))


def relevant_ids(html: str) -> list[str]:
    p = IdParser()
    p.feed(html)
    out = []
    for tag, ident in p.ids:
        low = ident.lower()
        if any(k in low for k in KEYWORDS):
            out.append(f"{tag}#{ident}")
    return sorted(set(out), key=str.lower)


def relevant_functions(html: str) -> list[str]:
    names = set(re.findall(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(", html))
    names.update(re.findall(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", html))
    return sorted(
        n for n in names
        if any(k in n.lower() for k in (
            "render", "apply", "state", "final", "early", "scalp", "timer",
            "clock", "quote", "kalshi", "flow", "price", "reason",
        ))
    )


def fetch_html() -> str:
    r = requests.get(DASHBOARD_URL, timeout=5.0, headers={"Cache-Control":"no-cache"})
    r.raise_for_status()
    return r.text


def main() -> int:
    html = fetch_html()
    ids = relevant_ids(html)
    funcs = relevant_functions(html)
    print("DASHBOARD_DOM_PROBE_V1 | IDS + FUNCTION NAMES ONLY | NO VALUES | NO ORDERS", flush=True)
    print("DASHBOARD_RELEVANT_IDS | " + " | ".join(ids), flush=True)
    print("DASHBOARD_RELEVANT_FUNCTIONS | " + " | ".join(funcs), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
