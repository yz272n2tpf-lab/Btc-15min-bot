#!/usr/bin/env python3
"""Disposable shadow wrapper for v81-live-diagnostics using shared BRTI only.

It does not alter V8.1 gate thresholds, price bands, confirmation, timing, or
orders. It rewrites exactly one runtime plumbing point: after the existing
unified V8 prefix is loaded, the global brti() callable is replaced with the
strict shared-feed adapter. Intended only for a separate shadow service.
"""
from pathlib import Path
import sys

TARGET = Path('v81_30_45_live_feed.py')
ANCHOR = "exec(compile(_prefix,'scalp_lead_unified_v8.py','exec'),globals())"
INJECT = ANCHOR + "\n" + r'''from brti_shared_cutover_adapter_v1 import SharedBrtiQualificationAdapter
_shared_brti_adapter = SharedBrtiQualificationAdapter.from_env()
def brti():
    return _shared_brti_adapter.fetch_value()
'''


def patched_source(text: str) -> str:
    if text.count(ANCHOR) != 1:
        raise RuntimeError('expected exactly one V8 prefix anchor; refusing patch')
    if 'SharedBrtiQualificationAdapter' in text:
        raise RuntimeError('target already contains shared-BRTI adapter; refusing double patch')
    out = text.replace(ANCHOR, INJECT, 1)
    if out == text:
        raise RuntimeError('shared-BRTI injection did not apply')
    return out


def self_test() -> int:
    fixture = "x=1\n" + ANCHOR + "\ny=2\n"
    out = patched_source(fixture)
    assert out.count(ANCHOR) == 1
    assert out.count('SharedBrtiQualificationAdapter') == 2
    assert 'def brti()' in out
    assert ('external' + '-api.kalshi.com') not in INJECT
    assert 'order' not in INJECT.lower()
    print('V81_SHARED_BRTI_SHADOW_WRAPPER_SELFTEST | PASS | ONE PLUMBING OVERRIDE | NO ORDERS')
    return 0


def main() -> int:
    if '--self-test' in sys.argv:
        return self_test()
    if not TARGET.exists():
        raise SystemExit(f'missing target: {TARGET}')
    text = TARGET.read_text(encoding='utf-8')
    out = patched_source(text)
    glb = {'__name__': '__main__', '__file__': str(TARGET)}
    exec(compile(out, str(TARGET), 'exec'), glb, glb)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
