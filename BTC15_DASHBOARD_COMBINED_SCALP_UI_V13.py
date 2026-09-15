#!/usr/bin/env python3
"""
BTC15 combined SCALP dashboard UI V13.

SHADOW PRESENTATION ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

V13 applies the frozen whole-app plain-language cleanup spec to the SCALP card
without changing qualification, serial lifecycle, entry-price handling, +5c
protection arm, 4c giveback EXIT, EARLY, FINAL, canonical timer, Kalshi sync,
or order behavior.
"""
from pathlib import Path
import sys

import BTC15_DASHBOARD_COMBINED_SCALP_UI_V12 as v12

MARKER = "BTC15_COMBINED_SCALP_UI_V13_PLAIN_LANGUAGE"

# Exact display-text replacements only. patch_v13 operates on the rendered HTML,
# never on backend Python strategy/state code.
REPLACEMENTS = (
    ("◉ SCALP / REVERSAL", "◉ SCALP OPPORTUNITY", "card-title"),
    ("'SCALP / REVERSAL'", "'SCALP OPPORTUNITY'", "pass-title"),
    ("WAIT · FEED STALE", "WAIT · DATA NOT FRESH", "freshness-wait"),
    ("WAIT · INVALID ENVELOPE", "WAIT · CHECKING DATA", "envelope-wait"),
    ("WAIT · CONTRACT SYNC", "WAIT · SYNCING CONTRACT", "contract-sync-wait"),
    ("WAIT · SCALP ALIGNMENT", "WAIT · SYNCING SCALP", "scalp-sync-wait"),
    ("WAIT · SCALP SOURCE STALE", "WAIT · SCALP DATA NOT FRESH", "scalp-source-wait"),
    ("WAIT · SCALP INTEGRATION", "WAIT · SCALP NOT READY", "integration-wait"),
    ("WAITING FOR QUALIFIED SCALP", "WATCHING FOR SCALP", "scanning-copy"),
    ("EXIT / PROTECT PROFITS NOW", "EXIT NOW · PROTECT PROFITS", "exit-copy"),
    ("SCALP ACTIVE · BUILDING", "HOLD · MOVE STILL BUILDING", "active-copy"),
    ("MOVE VALID · NO ENTRY · DON'T CHASE", "TRACKING ONLY · DON'T CHASE", "no-entry-copy"),
    (" ENDED UNARMED · SCANNING ", " ENDED · NO PROTECTED EXIT · SCANNING ", "completed-unarmed-copy"),
    (" ended unarmed · reset only · now scanning ", " ended · no protected exit · scanning ", "lifecycle-note-copy"),
    ("Prior scalp ended unarmed · lifecycle reset only", "Prior scalp ended · no protected exit", "prior-note-copy"),
    ("Prior ended unarmed · reset only", "Prior scalp ended · no protected exit", "prior-row-copy"),
    ("Scanning for next qualified scalp", "Watching for next scalp", "next-scan-copy"),
    ("Scanning next qualified scalp", "Watching for next scalp", "next-row-copy"),
    ("`Opportunity #${opp}`", "`Scalp #${opp}`", "opportunity-label"),
    ("completedHold?'COMPLETED ENTRY':'ENTRY'", "completedHold?'COMPLETED ENTRY PRICE':'ENTRY PRICE'", "entry-label"),
    ("completedHold?'STATUS':'CURRENT BID'", "completedHold?'STATUS':'CURRENT SELL PRICE'", "sell-label"),
    ("completedHold?'EXIT / PEAK':'EXEC GAIN'", "completedHold?'EXIT / BEST':'PROFIT NOW'", "profit-label"),
    ("<span>Entry guidance</span>", "<span>Entry Quality</span>", "entry-guidance-label"),
    ("<span>Lifecycle</span>", "<span>Status</span>", "lifecycle-label"),
    ("<span>Protection</span>", "<span>Profit Protection</span>", "protection-label"),
    ("MODEL TRACKING ONLY · no manual position assumed", "TRACKING ONLY · NO POSITION ASSUMED", "no-position-copy"),
    ("Arm +5¢ · EXIT at 4¢ giveback", "+5¢ ARM · EXIT AFTER 4¢ GIVEBACK", "protection-rule-copy"),
    ("Generalized scalp feed is stale/unavailable", "Scalp data is not fresh", "reason-feed"),
    ("Invalid scalp safety envelope", "Checking scalp data", "reason-envelope"),
    ("Main/scalp contract IDs do not match", "Syncing contract", "reason-contract"),
    ("Scalp backend contract alignment pending", "Syncing scalp", "reason-alignment"),
    ("Scalp source is stale", "Scalp data is not fresh", "reason-source"),
    ("Scalp integration not ready", "Scalp not ready", "reason-integration"),
    ("No qualified generalized scalp", "Watching for scalp", "reason-pass"),
)


def patch_v13(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    changes: list[str] = []
    for old, new, label in REPLACEMENTS:
        if old in text:
            text = text.replace(old, new)
            changes.append(label)
        elif new not in text:
            # Some phrases are state-dependent variants that may be absent from
            # the rendered page. Only fail closed for core anchors below.
            if label in {
                "card-title", "freshness-wait", "contract-sync-wait",
                "scanning-copy", "exit-copy", "active-copy", "no-entry-copy",
                "entry-label", "sell-label", "profit-label",
                "entry-guidance-label", "lifecycle-label", "protection-label",
                "no-position-copy", "protection-rule-copy",
            }:
                raise RuntimeError(f"{label} anchor not found; refusing unsafe V13 patch")

    # Reason/explanation text must not resize the card unpredictably.
    css = """<style id=\"btc15-scalp-v13-language-style\">\n#combinedScalpClean .csc-reason{min-height:2.7em;max-height:2.7em;overflow:hidden;}\n#combinedScalpClean .csc-pill,#combinedScalpClean .csc-main{font-weight:950;}\n</style>"""
    if 'id="btc15-scalp-v13-language-style"' not in text:
        if "</head>" in text:
            text = text.replace("</head>", css + "\n</head>", 1)
        else:
            text = css + "\n" + text

    if MARKER not in text:
        text = text.replace("</body>", f"<!-- {MARKER} -->\n</body>", 1) if "</body>" in text else text + f"\n<!-- {MARKER} -->\n"

    path.write_text(text, encoding="utf-8")
    return changes or ["v13-already-present"]


def build_dashboard() -> Path:
    html = v12.build_dashboard()
    patch_v13(html)
    return html


def main() -> int:
    html = build_dashboard()
    rendered = html.read_text(encoding="utf-8", errors="replace")
    print("COMBINED SCALP UI V13 | PLAIN LANGUAGE | SHADOW ONLY | NO ORDERS")
    if "--self-test" in sys.argv:
        assert "◉ SCALP OPPORTUNITY" in rendered
        assert "WATCHING FOR SCALP" in rendered
        assert "HOLD · MOVE STILL BUILDING" in rendered
        assert "EXIT NOW · PROTECT PROFITS" in rendered
        assert "TRACKING ONLY · DON'T CHASE" in rendered
        assert "TRACKING ONLY · NO POSITION ASSUMED" in rendered
        assert "CURRENT SELL PRICE" in rendered
        assert "PROFIT NOW" in rendered
        assert "Entry Quality" in rendered
        assert "Profit Protection" in rendered
        assert "+5¢ ARM · EXIT AFTER 4¢ GIVEBACK" in rendered
        assert "WAIT · DATA NOT FRESH" in rendered
        assert "WAIT · SYNCING CONTRACT" in rendered
        assert "ENDED_UNARMED" not in rendered
        assert "ENDED UNARMED" not in rendered
        assert "ended unarmed" not in rendered
        assert "BTC15_COMBINED_STATE_BRIDGE_V6" in rendered
        assert "scalp_entry_price_filter_applied===false" in rendered
        assert "scalp_entry_guidance_is_display_only===true" in rendered
        assert "scalp_completed_display_actionable===false" in rendered
        assert "SIGNAL ONLY · MANUAL EXECUTION · NO ORDERS" in rendered
        assert "flip_risk_percent" not in rendered
        assert v12.MARKER in rendered
        assert MARKER in rendered
        print("COMBINED SCALP UI V13 SELFTEST PASS | DISPLAY ONLY | SAFETY PRESERVED | NO ORDERS")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
