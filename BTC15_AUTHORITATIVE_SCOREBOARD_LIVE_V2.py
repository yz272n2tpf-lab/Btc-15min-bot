#!/usr/bin/env python3
"""BTC15 live authoritative scoreboard V2.

Thin runtime wrapper over LIVE V1 using Scoreboard V2 exact-field compatibility.
READ ONLY | PRIVATE RAILWAY NETWORK | NO ORDERS
"""
from __future__ import annotations

import BTC15_AUTHORITATIVE_SCOREBOARD_LIVE_V1 as livev1
import BTC15_AUTHORITATIVE_SCOREBOARD_V2 as boardv2

VERSION = "BTC15_AUTHORITATIVE_SCOREBOARD_LIVE_V2"
SOURCES = livev1.SOURCES
PORT = livev1.PORT

# Runtime-only presentation compatibility swap. No collector/model state is owned
# or mutated by this service.
livev1.boardmod = boardv2
livev1.VERSION = VERSION

fetch_source = livev1.fetch_source
collect_live = livev1.collect_live
Handler = livev1.Handler


def main() -> int:
    livev1.boardmod = boardv2
    livev1.VERSION = VERSION
    print(
        f"{VERSION} START | SCOREBOARD V2 EXACT COLLECTOR ALIASES | "
        "PRIVATE READS ONLY | NO CACHE | NO MODEL RECOMPUTE | NO ORDERS",
        flush=True,
    )
    return livev1.main()


if __name__ == "__main__":
    raise SystemExit(main())
