#!/usr/bin/env python3
"""
BTC15 live authoritative scoreboard V3.

Adds a private /viewmodel endpoint on top of LIVE V2. No score math changes.
READ ONLY | PRIVATE RAILWAY NETWORK | PRESENTATION ONLY | NO ORDERS
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import BTC15_AUTHORITATIVE_SCOREBOARD_LIVE_V1 as base
import BTC15_AUTHORITATIVE_SCOREBOARD_LIVE_V2 as v2
import BTC15_AUTHORITATIVE_SCOREBOARD_V2 as boardv2
import BTC15_AUTHORITATIVE_SCOREBOARD_VIEWMODEL_V1 as viewmod

VERSION = "BTC15_AUTHORITATIVE_SCOREBOARD_LIVE_V3"
SOURCES = v2.SOURCES
PORT = v2.PORT

base.boardmod = boardv2
base.VERSION = VERSION

fetch_source = base.fetch_source
collect_live = base.collect_live


class Handler(base.Handler):
    server_version = "BTC15AuthoritativeScoreboardLiveV3/1.0"

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/viewmodel":
            try:
                snap = collect_live()
                vm = viewmod.build_viewmodel(snap["scoreboard"])
                return self._json(200, {
                    "ok": True,
                    "version": VERSION,
                    "source_scoreboard_version": snap["scoreboard"].get("version"),
                    "all_sources_connected": snap.get("all_sources_connected"),
                    "source_health": snap.get("source_health"),
                    "viewmodel": vm,
                    "orders": False,
                    "manual_execution_only": True,
                    "production_behavior_changed": False,
                })
            except Exception as exc:
                return self._json(500, {
                    "ok": False,
                    "version": VERSION,
                    "error": f"{type(exc).__name__}: {exc}",
                    "orders": False,
                    "manual_execution_only": True,
                })
        return super().do_GET()


def main() -> int:
    base.boardmod = boardv2
    base.VERSION = VERSION
    base.Handler = Handler
    print(
        f"{VERSION} START | +/viewmodel APP-READY PRESENTATION | "
        "PRIVATE READS ONLY | NUMERIC FLIP HIDDEN | NO ORDERS",
        flush=True,
    )
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
