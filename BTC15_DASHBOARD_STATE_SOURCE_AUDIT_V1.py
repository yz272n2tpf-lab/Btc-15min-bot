#!/usr/bin/env python3
"""Read-only source ownership audit for the packed dashboard bundle.

Decodes every embedded text payload and determines whether KXBTC15M active-market
discovery lives inside the dashboard installer or in the external bot runtime.
Also prints the runner lines that reveal which child process owns live collection.
No network calls, service mutations, signal changes, or orders.
"""
from __future__ import annotations

import base64
import gzip
from typing import Iterable

import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer

STATE_TARGET = "BTC15_DASHBOARD_STATE_V2.py"
RUNNER_TARGET = "BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py"
DISCOVERY_PHRASE = "NO ACTIVE KXBTC15M CONTRACT"


def decode_payload(name: str) -> str:
    raw = installer.PAYLOADS.get(name)
    if not raw:
        raise RuntimeError(f"packed payload missing: {name}")
    return gzip.decompress(base64.b64decode(raw)).decode("utf-8", errors="replace")


def decoded_source() -> str:
    return decode_payload(STATE_TARGET)


def payload_inventory() -> dict[str, str]:
    out = {}
    for name in sorted(installer.PAYLOADS):
        try:
            out[name] = decode_payload(name)
        except Exception as exc:
            out[name] = f"<DECODE ERROR {type(exc).__name__}: {exc}>"
    return out


def discovery_owners() -> list[str]:
    return [name for name, src in payload_inventory().items() if DISCOVERY_PHRASE in src]


def _interesting_lines(src: str, needles: Iterable[str]) -> list[tuple[int, str]]:
    lows = tuple(str(n).lower() for n in needles)
    out = []
    for i, line in enumerate(src.splitlines(), start=1):
        low = line.lower()
        if any(n in low for n in lows):
            out.append((i, line))
    return out


def audit() -> dict[str, object]:
    inv = payload_inventory()
    owners = [name for name, src in inv.items() if DISCOVERY_PHRASE in src]
    state = inv.get(STATE_TARGET, "")
    runner = inv.get(RUNNER_TARGET, "")
    runner_lines = _interesting_lines(
        runner,
        (
            "subprocess", "popen", "exec", "bot", "python", "dashboard",
            "run_full_validation", "railway", "child", "main",
        ),
    )
    state_contract_lines = _interesting_lines(
        state,
        ("latest_unified_snapshot", "contract =", "dashboard_state.json", "read_csv_tail"),
    )
    return {
        "payload_names": sorted(inv),
        "discovery_phrase_found_in_payloads": bool(owners),
        "discovery_owner_payloads": owners,
        "state_builder_is_file_tail_adapter": (
            "latest_unified_snapshot" in state
            and "read_csv_tail" in state
            and DISCOVERY_PHRASE not in state
        ),
        "runner_lines": runner_lines,
        "state_contract_lines": state_contract_lines,
    }


def print_audit() -> None:
    a = audit()
    print("=" * 96)
    print("BTC15 PACKED DASHBOARD SOURCE OWNERSHIP AUDIT V2 | READ ONLY | NO ORDERS")
    print("payloads=" + ",".join(a["payload_names"]))
    print(f"discovery_phrase_found_in_payloads={a['discovery_phrase_found_in_payloads']}")
    print("discovery_owner_payloads=" + ",".join(a["discovery_owner_payloads"]))
    print(f"state_builder_is_file_tail_adapter={a['state_builder_is_file_tail_adapter']}")
    print(f"--- {STATE_TARGET} CONTRACT-STATE LINES ---")
    for n, line in a["state_contract_lines"]:
        print(f"STATE L{n:04d} | {line}")
    print(f"--- {RUNNER_TARGET} PROCESS-OWNERSHIP LINES ---")
    for n, line in a["runner_lines"]:
        print(f"RUNNER L{n:04d} | {line}")
    if not a["discovery_phrase_found_in_payloads"]:
        print("DISCOVERY_OWNER=OUTSIDE_PACKED_DASHBOARD_BUNDLE")
    print("RESULT=PASS")
    print("=" * 96)


def main() -> int:
    a = audit()
    assert STATE_TARGET in a["payload_names"]
    assert RUNNER_TARGET in a["payload_names"]
    assert a["state_builder_is_file_tail_adapter"] is True
    print_audit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
