"""Apply ONLY to an isolated checkout of the pinned production source.

No network, no deployment, no branch manipulation. Refuses unexpected source.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
from pathlib import Path

MAIN = 'bot_two_output_build_v4_13_profit_protection_shadow.py'
BASE_COMMIT = '191fa114b9910b4a02c8ed201a29fd3d41d4e268'
EXPECTED_BLOB = '5893985d7f4f442ef48f64e38f9da92bc171dd76'
OLD = '''def kalshi_get(path, params=None):
    r = requests.get(
        KALSHI_BASE_URL + path,
        headers=kalshi_headers("GET", path),
        params=params,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()'''
NEW = '''def kalshi_get(path, params=None):
    # Measurement only: record the LAST binding used by the continuous loop.
    _rd = _ctx = None
    try:
        import btc15_rollover_discovery_diag_v2 as _rd
        _ctx = _rd.begin(path, params)
    except Exception:
        pass
    try:
        r = requests.get(
            KALSHI_BASE_URL + path,
            headers=kalshi_headers("GET", path),
            params=params,
            timeout=10,
        )
    except Exception:
        try:
            _rd.failed(_ctx, "transport")
        except Exception:
            pass
        raise
    try:
        _rd.response(_ctx, r)
    except Exception:
        pass
    try:
        r.raise_for_status()
    except Exception:
        try:
            _rd.failed(_ctx, "http_status")
        except Exception:
            pass
        raise
    try:
        data = r.json()
    except Exception:
        try:
            _rd.failed(_ctx, "json_decode")
        except Exception:
            pass
        raise
    try:
        _rd.decoded(_ctx, data)
    except Exception:
        pass
    return data'''


def blob_sha(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def replace_last_binding(source):
    tree = ast.parse(source)
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == 'kalshi_get']
    if len(definitions) != 2:
        raise ValueError('Expected exactly two top-level kalshi_get definitions')
    node = definitions[-1]
    lines = source.splitlines(keepends=True)
    actual = ''.join(lines[node.lineno-1:node.end_lineno]).rstrip('\n')
    if actual != OLD:
        raise ValueError('Final runtime function does not match pinned source')
    changed = ''.join(lines[:node.lineno-1]) + NEW + '\n' + ''.join(lines[node.end_lineno:])
    restored = changed.replace(NEW + '\n', actual + '\n', 1)
    if restored != source:
        raise ValueError('Unexpected changes outside runtime diagnostic hook')
    ast.parse(changed)
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()
    path = args.root / MAIN
    raw = path.read_bytes()
    if blob_sha(raw) != EXPECTED_BLOB:
        raise SystemExit('REFUSED: source Git blob differs from ' + EXPECTED_BLOB)
    helper = args.root / 'btc15_rollover_discovery_diag_v2.py'
    if not helper.is_file():
        raise SystemExit('REFUSED: diagnostic helper is absent')
    source = raw.decode('utf-8')
    changed = replace_last_binding(source)
    path.write_text(changed, encoding='utf-8')
    print('PATCH_APPLIED_TO_LOCAL_CHECKOUT_ONLY')
    print('base_commit=' + BASE_COMMIT)
    print('before_blob=' + EXPECTED_BLOB)
    print('after_blob=' + blob_sha(path.read_bytes()))
    print('NO DEPLOYMENT / NO ORDERS')


if __name__ == '__main__':
    main()
