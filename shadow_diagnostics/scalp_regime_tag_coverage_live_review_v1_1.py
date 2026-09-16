#!/usr/bin/env python3
"""Read-only live wrapper for Regime Tag Coverage Audit V1.1.

CAUSAL FEATURE AUDIT | SEMANTIC BOOLEAN REPAIR | NO THRESHOLD SELECTION |
NO ORDERS | NO PROMOTION

Reuses V1's already-tested read-only HTTP/fetch loop.  Only the audit module and
version marker are replaced with the V1.1 numeric-boolean semantic repair.
"""
from __future__ import annotations

import scalp_regime_tag_coverage_audit_v1_1 as audit_v11
import scalp_regime_tag_coverage_live_review_v1 as base

VERSION = "BTC15_SCALP_REGIME_TAG_COVERAGE_LIVE_REVIEW_V1_1_SEMANTIC_REPAIR"

# Narrow semantic swap only.  Source transport, HTTP endpoints, fail-closed loop,
# polling cadence and safety behavior remain the tested V1 implementation.
base.audit = audit_v11
base.VERSION = VERSION
base.STATE["version"] = VERSION
base.STATE["semantic_repair"] = "NUMERIC_FLOAT_BOOLEAN_FLAGS"

analyze_rows = base.analyze_rows
refresh_once = base.refresh_once
compact = base.compact
Handler = base.Handler


def main() -> int:
    print(
        f"{VERSION} START | CAUSAL FEATURE AUDIT | NUMERIC BOOLEAN REPAIR | "
        "NO THRESHOLD SELECTION | NO PROMOTION | NO ORDERS",
        flush=True,
    )
    base.threading.Thread(target=base.loop, name="regime-tag-audit-v11-loop", daemon=True).start()
    base.ThreadingHTTPServer(("0.0.0.0", base.PORT), base.Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
