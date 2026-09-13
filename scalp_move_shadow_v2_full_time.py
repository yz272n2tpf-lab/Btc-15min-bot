#!/usr/bin/env python3
"""Surgical full-time V2 launcher derived from the frozen V1 payload. NO ORDERS."""
import ast, base64, gzip, hashlib
from pathlib import Path

BASE = Path(__file__).with_name('scalp_move_shadow_v1.py')
V1_SHA256 = '3fdb2ef60f184e1ce2cef306c1db2a9de03b3e7b1a27c32b6bfffabb2cf60c48'
V2_SHA256 = '52b79e239c0be2b5ece93e3387063185ce51be8a01413f6b76bc5939924fb3ad'

src = BASE.read_text(encoding='utf-8')
tree = ast.parse(src, filename=str(BASE))
payload = None
for node in tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PAYLOAD' for t in node.targets):
        payload = ast.literal_eval(node.value)
        break
if payload is None:
    raw = src
else:
    raw = gzip.decompress(base64.b64decode(payload)).decode('utf-8')

if hashlib.sha256(raw.encode()).hexdigest() != V1_SHA256:
    raise RuntimeError('V1 payload SHA mismatch; refusing V2 transformation')

replacements = (
    ('PRICE-AGNOSTIC BTC15 SCALP MOVE SHADOW V1', 'PRICE-AGNOSTIC BTC15 SCALP MOVE SHADOW V2 FULL-TIME'),
    ('MIN_LEFT = 120.0', 'MIN_LEFT = 0.0'),
    ('MOVE_BASED_PRICE_AGNOSTIC|SIGNAL_ONLY|NO_ORDERS', 'MOVE_BASED_PRICE_AGNOSTIC|FULL_TIME_V2|SIGNAL_ONLY|NO_ORDERS'),
    ('PATH_TELEMETRY|PRICE_AGNOSTIC|NO_ORDERS', 'PATH_TELEMETRY|PRICE_AGNOSTIC|FULL_TIME_V2|NO_ORDERS'),
    ('SHADOW_RESULT|PRICE_BUCKET_TELEMETRY_ONLY|NO_ORDERS', 'SHADOW_RESULT|PRICE_BUCKET_TELEMETRY_ONLY|FULL_TIME_V2|NO_ORDERS'),
    ('SCALP MOVE SHADOW V1 START | PRICE-AGNOSTIC | EXECUTABLE ASK->BID | ', 'SCALP MOVE SHADOW V2 START | PRICE-AGNOSTIC | FULL-TIME 15:00->0:00 | EXECUTABLE ASK->BID | '),
)
for old, new in replacements:
    if raw.count(old) != 1:
        raise RuntimeError(f'expected one occurrence for surgical replacement: {old!r}')
    raw = raw.replace(old, new)

sha = hashlib.sha256(raw.encode()).hexdigest()
if sha != V2_SHA256:
    raise RuntimeError(f'V2 payload SHA mismatch: {sha}')
print(f'SCALP MOVE BOOTSTRAP V2 | SHA256 {sha} | FULL-TIME 15:00->0:00 | SIGNAL ONLY | NO ORDERS', flush=True)
exec(compile(raw, 'scalp_move_shadow_v2_full_time.py', 'exec'), globals())
