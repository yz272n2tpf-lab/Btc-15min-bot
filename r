#!/usr/bin/env bash
# BTC15 read-only production checkpoint preflight. No deploys or DB writes.
set -euo pipefail
python3 - <<'PY'
import subprocess,sys
remote = r'''
import json,sqlite3
from pathlib import Path
from btc15_v2_product import REVISION
from btc15_v2_product.directional import Directional
dep="4b33134d-d832-409e-bf35-f80689beb66b"
build="6d5897c26fc83e62a5425148a773d648dfcbacde"
p=Path("/data/btc15_v2_product")/REVISION/dep/"main.sqlite3"
if not p.is_file():raise SystemExit("BLOCKED: journal missing "+str(p))
with sqlite3.connect(p.resolve().as_uri()+"?mode=ro",uri=True) as db:
 db.execute("PRAGMA query_only=ON")
 assert db.execute("PRAGMA quick_check").fetchone()[0]=="ok","SQLite integrity failure"
 meta=dict(db.execute("SELECT k,v FROM meta"))
 for k,v in dict(product_revision=REVISION,deployment=dep,build=build,lane="main").items():
  assert meta.get(k)==v,"Identity mismatch: "+k
 state=json.loads(meta["state"])
 engine=Directional();engine.restore(state)
 count,last=db.execute("SELECT COUNT(*),MAX(seq) FROM events").fetchone()
 assert count>0,"Empty event journal"
 print(json.dumps(dict(status="PASS_READ_ONLY",deployment=dep,build=build,event_count=count,last_seq=last,origin_id=(engine.origin or {}).get("origin_id"),terminal_origin_id=(engine.terminal or {}).get("origin_id"),history_count=len(engine.signal_history),orders=False)))
'''
args=['railway','ssh','-p','baea4e22-d004-4434-b2c5-81a7fbc05086','-e','61775c5d-c583-4dfc-af41-f25578856fd9','-s','ab28dca6-7bea-4956-bdb9-dbb7b4c74635','-d','4b33134d-d832-409e-bf35-f80689beb66b','python','-c',remote]
print('BTC15 read-only MAIN checkpoint verification; no deploy or data changes',flush=True)
sys.exit(subprocess.call(args))
PY
