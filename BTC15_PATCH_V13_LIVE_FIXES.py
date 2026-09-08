#!/usr/bin/env python3
"""
Patch the packed BTC15 V13 dashboard installer on a safe development branch.

DISPLAY/ADAPTER ONLY:
- Prefer the persistent direct-BRTI log for BRTI value/freshness.
- Keep the unified snapshot as the source for model/quote state.
- Separate BRTI availability from BRTI freshness in the UI.
- Poll dashboard state every 2s (source cadence is still authoritative).
- Fix Signal Strength fallback and Flip Risk presentation.

Does NOT change trading thresholds, FINAL/Tier-1/scalp gates, order behavior,
Railway configuration, or the core bot.
"""
from __future__ import annotations

import ast
import base64
import gzip
from pathlib import Path

TARGET = Path("BTC15_INSTALL_LIVE_DASHBOARD_V13.py")
STATE_NAME = "BTC15_DASHBOARD_STATE_V2.py"
HTML_NAME = "BTC_Kalshi_App_Live_v13.html"


def load_payloads(src: str) -> dict[str, str]:
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "PAYLOADS" for t in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, dict):
                return value
    raise RuntimeError("PAYLOADS dictionary not found")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_state(text: str) -> str:
    text = replace_once(
        text,
        "    'protect': 'kalshi_final_position_protection_shadow_v3.csv',\n}",
        "    'protect': 'kalshi_final_position_protection_shadow_v3.csv',\n"
        "    'brti': 'kalshi_direct_brti_parity_v1.csv',\n}",
        "FILES direct BRTI",
    )
    text = replace_once(
        text,
        "    'protect': 128 * 1024,\n}",
        "    'protect': 128 * 1024,\n"
        "    'brti': 96 * 1024,\n}",
        "TAIL_BYTES direct BRTI",
    )

    old = """    brti_ready_raw = truthy(first(s, ['brti_ready']))
    brti_age = num(first(s, ['brti_age_seconds']))
    brti_gap = num(first(s, ['brti_gap_to_target', 'brti_gap']))
    brti_side = side(first(s, ['brti_side']))
    direct_brti_authority_ready = (
        brti_ready_raw
        and math.isfinite(brti_age) and brti_age <= DIRECT_BRTI_MAX_AGE_SECONDS
        and math.isfinite(brti_gap) and abs(brti_gap) > DIRECT_BRTI_WAIT_DOLLARS
        and brti_side in {'UP', 'DOWN'}
    )
"""
    new = """    # Prefer the persistent direct-BRTI collector for BRTI display/freshness.
    # The unified snapshot remains authoritative for model/quote state.
    brti_row, brti_t = latest_row(
        data['brti'],
        ['timestamp_utc', 'source_timestamp_utc', 'observed_utc', 'collector_timestamp_utc'],
    )
    unified_brti_ready = truthy(first(s, ['brti_ready']))
    unified_brti_age = num(first(s, ['brti_age_seconds']))
    unified_brti_gap = num(first(s, ['brti_gap_to_target', 'brti_gap']))
    unified_brti_side = side(first(s, ['brti_side']))
    unified_brti_value = num(first(s, ['brti_value']))

    brti_value = num(first(brti_row, [
        'brti_value', 'direct_brti_value', 'brti_price', 'value', 'price', 'benchmark_value'
    ]))
    brti_gap = num(first(brti_row, [
        'brti_gap_to_target', 'brti_gap', 'gap', 'target_gap'
    ]))
    brti_side = side(first(brti_row, ['brti_side', 'side', 'benchmark_side']))
    brti_age = num(first(brti_row, ['brti_age_seconds', 'age_seconds', 'age_sec']))
    if not math.isfinite(brti_age) and isinstance(brti_t, datetime):
        brti_age = max(0.0, (now_utc() - brti_t).total_seconds())

    target_value = num(first(s, ['target']))
    if not math.isfinite(brti_gap) and math.isfinite(brti_value) and math.isfinite(target_value):
        brti_gap = brti_value - target_value
    if not math.isfinite(brti_value) and math.isfinite(brti_gap) and math.isfinite(target_value):
        brti_value = target_value + brti_gap
    if brti_side not in {'UP', 'DOWN'} and math.isfinite(brti_gap):
        brti_side = 'UP' if brti_gap >= 0 else 'DOWN'

    # If the direct log is unavailable, retain the existing unified fallback.
    direct_sample_available = bool(
        isinstance(brti_t, datetime)
        and (math.isfinite(brti_value) or math.isfinite(brti_gap))
    )
    if not direct_sample_available:
        brti_value = unified_brti_value
        brti_gap = unified_brti_gap
        brti_side = unified_brti_side
        brti_age = unified_brti_age

    brti_ready_raw = bool(
        (direct_sample_available or unified_brti_ready)
        and math.isfinite(brti_age)
        and (math.isfinite(brti_value) or math.isfinite(brti_gap))
    )
    brti_fresh = bool(
        brti_ready_raw
        and math.isfinite(brti_age)
        and brti_age <= DIRECT_BRTI_MAX_AGE_SECONDS
    )
    direct_brti_authority_ready = (
        brti_fresh
        and math.isfinite(brti_gap) and abs(brti_gap) > DIRECT_BRTI_WAIT_DOLLARS
        and brti_side in {'UP', 'DOWN'}
    )
"""
    text = replace_once(text, old, new, "BRTI source block")

    text = replace_once(
        text,
        "            'brti_value': clean(num(first(s, ['brti_value']))),\n"
        "            'brti_age_seconds': clean(brti_age),\n"
        "            'brti_ready': brti_ready_raw,\n",
        "            'brti_value': clean(brti_value),\n"
        "            'brti_age_seconds': clean(brti_age),\n"
        "            'brti_ready': brti_ready_raw,\n"
        "            'brti_fresh': brti_fresh,\n"
        "            'brti_source': 'DIRECT_LOG' if direct_sample_available else 'UNIFIED_FALLBACK',\n",
        "market BRTI fields",
    )
    return text


def patch_html(text: str) -> str:
    if "setInterval(refresh,5000)" in text:
        text = replace_once(text, "setInterval(refresh,5000)", "setInterval(refresh,2000)", "polling")
    elif "const REFRESH_MS=5000" in text:
        text = replace_once(text, "const REFRESH_MS=5000", "const REFRESH_MS=2000", "polling")
    elif "const REFRESH_MS = 5000" in text:
        text = replace_once(text, "const REFRESH_MS = 5000", "const REFRESH_MS = 2000", "polling")
    else:
        raise RuntimeError("polling: supported 5-second marker not found")

    text = replace_once(
        text,
        "    const p=Number(m.preferred_side?conf:e.fair);",
        "    const p=Number(Number.isFinite(conf)?conf:e.fair);",
        "Signal Strength fallback",
    )

    text = replace_once(
        text,
        "    setText('flipRisk',rev);\n"
        "    setText('flipRiskSub',rev==='PUSH'?'Pressure supports call':rev==='AGAINST'?'Pressure against call':rev==='MIXED'?'Conflicting pressure':'Live reversal state');",
        "    const flip=Number.isFinite(conf)?Math.max(0,Math.min(1,1-conf)):NaN;\n"
        "    setText('flipRisk',fmtPct(flip,0));\n"
        "    setText('flipRiskSub',rev==='PUSH'?'Pressure supports call':rev==='AGAINST'?'Pressure against call':rev==='MIXED'?'Conflicting pressure':'Live reversal state');",
        "Flip Risk percentage",
    )

    text = text.replace("m.brti_ready?", "m.brti_fresh?")
    text = text.replace("const align=m.brti_ready &&", "const align=m.brti_fresh &&")
    return text


def encode_payload(text: str) -> str:
    return base64.b64encode(gzip.compress(text.encode("utf-8"), mtime=0)).decode("ascii")


def render_installer(original: str, payloads: dict[str, str]) -> str:
    tree = ast.parse(original)
    node = None
    for candidate in tree.body:
        if isinstance(candidate, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "PAYLOADS" for t in candidate.targets
        ):
            node = candidate
            break
    if node is None:
        raise RuntimeError("PAYLOADS assignment not found")
    lines = original.splitlines(keepends=True)
    start = sum(len(x) for x in lines[: node.lineno - 1])
    end = sum(len(x) for x in lines[: node.end_lineno])
    assignment = "PAYLOADS = " + repr(payloads)
    if end <= len(original) and original[end - 1:end] == "\n":
        assignment += "\n"
    return original[:start] + assignment + original[end:]


def validate_payload(name: str, data: str) -> None:
    if name.endswith(".py"):
        compile(data, name, "exec")
    if name == STATE_NAME:
        for marker in [
            "'brti': 'kalshi_direct_brti_parity_v1.csv'",
            "'brti_fresh': brti_fresh",
            "'brti_source': 'DIRECT_LOG'",
            "direct_brti_authority_ready = (",
        ]:
            if marker not in data:
                raise RuntimeError(f"state validation missing marker: {marker}")
    if name == HTML_NAME:
        for marker in [
            "setInterval(refresh,2000)",
            "Number.isFinite(conf)?conf:e.fair",
            "setText('flipRisk',fmtPct(flip,0))",
            "m.brti_fresh?",
        ]:
            if marker not in data:
                raise RuntimeError(f"HTML validation missing marker: {marker}")


def main() -> int:
    if not TARGET.exists():
        print(f"STOP: {TARGET} not found")
        return 2

    original = TARGET.read_text(encoding="utf-8")
    payloads = load_payloads(original)
    for required in [STATE_NAME, HTML_NAME]:
        if required not in payloads:
            raise RuntimeError(f"missing packed payload: {required}")

    state = gzip.decompress(base64.b64decode(payloads[STATE_NAME])).decode("utf-8")
    html = gzip.decompress(base64.b64decode(payloads[HTML_NAME])).decode("utf-8")

    patched_state = patch_state(state)
    patched_html = patch_html(html)
    validate_payload(STATE_NAME, patched_state)
    validate_payload(HTML_NAME, patched_html)

    payloads[STATE_NAME] = encode_payload(patched_state)
    payloads[HTML_NAME] = encode_payload(patched_html)
    updated = render_installer(original, payloads)
    compile(updated, str(TARGET), "exec")

    backup = TARGET.with_suffix(TARGET.suffix + ".pre_v13_live_fixes")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")
    TARGET.write_text(updated, encoding="utf-8")

    print("RESULT: PASS")
    print("Patched:", TARGET)
    print("Backup:", backup)
    print("Core/model thresholds/orders: UNCHANGED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
