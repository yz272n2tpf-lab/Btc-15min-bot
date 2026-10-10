#!/usr/bin/env bash
# BTC15 PHASE A: READ/DOWNLOAD ONLY. NO RAILWAY OR VOLUME MODIFICATIONS.
set -Eeuo pipefail
PROJECT=baea4e22-d004-4434-b2c5-81a7fbc05086
ENV=61775c5d-c583-4dfc-af41-f25578856fd9
SERVICE=ab28dca6-7bea-4956-bdb9-dbb7b4c74635
VOL=6ced6b1a-3755-4518-a240-c895e936d443
echo 'BTC15 PHASE A — QUiescent historical archive copy, no uploads/deploys'
AVAILABLE_KB="$(df -Pk /workspaces | awk 'NR==2 {print $4}')"
if [ "$AVAILABLE_KB" -lt 11534336 ]; then
  echo 'BLOCKED: NEED_AT_LEAST_11GB_FREE_IN_CODESPACE'; exit 1
fi
ROOT="$(mktemp -d /workspaces/btc15-phasea-20261010.XXXXXXXX)"
echo "PRESERVE_LOCAL_FOLDER: $ROOT"
echo '[1/4] Download maintenance receipt and consistent SQLite snapshot'
railway service files --project "$PROJECT" --environment "$ENV" --service "$SERVICE" download /tmp/btc15-cutover "$ROOT/receipt" --concurrency 4 --json
export BTC15_PHASE_A_LOCAL="$ROOT"
python3 - <<'PY_RECEIPT'
import json, os, sqlite3
from pathlib import Path
root=Path(os.environ['BTC15_PHASE_A_LOCAL'])
report=json.loads((root/'receipt/report.json').read_text())
assert report.get('status')=='BLOCKED',report
assert str(report.get('error','')).startswith('HANDOFF_MISSING_HISTORY:'),report
v=json.loads((root/'receipt/committed-verifier.json').read_text())
assert v.get('status')=='READ_ONLY_MAIN_CHECKPOINT_VERIFIED',v
snap=root/'receipt/main.consistent.sqlite3'
assert snap.exists() and snap.stat().st_size>1000000,'MISSING_CONSISTENT_SQLITE_SNAPSHOT'
with sqlite3.connect(snap.as_uri()+'?mode=ro',uri=True) as db:
    db.execute('PRAGMA query_only=ON')
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLITE_SNAPSHOT_INTEGRITY'
    meta=dict(db.execute('SELECT k,v FROM meta'))
    assert meta['deployment']=='4b33134d-d832-409e-bf35-f80689beb66b'
    assert meta['build']=='6d5897c26fc83e62a5425148a773d648dfcbacde'
    event_count,last_seq=db.execute('SELECT count(*), max(seq) FROM events').fetchone()
    assert event_count>0 and last_seq==int(meta['sequence'])
print('PASS: SNAPSHOT_INTEGRITY_AND_PREDECESSOR_IDENTITY')
print('KNOWN_CUTOVER_BLOCKER:',report['error'])
print('SNAPSHOT_EVENTS:',event_count,'LAST_SEQ:',last_seq)
PY_RECEIPT
echo '[2/4] Download entire quiet MAIN volume: this may take several minutes'
railway service files --project "$PROJECT" --environment "$ENV" --service "$SERVICE" download /data "$ROOT/data" --concurrency 4 --json
echo '[3/4] Hash every local file and verify both SQLite copies'
python3 - <<'PY_ARCHIVE'
import hashlib, json, os, sqlite3
from pathlib import Path
root=Path(os.environ['BTC15_PHASE_A_LOCAL']).resolve()
data=root/'data'
snapshot=root/'receipt/main.consistent.sqlite3'
prior=Path('btc15_v2_product/BTC15_INTEGRATED_OFFLINE_20261006/4b33134d-d832-409e-bf35-f80689beb66b/main.sqlite3')
live=data/prior
assert data.is_dir() and live.is_file(),'MISSING_VOLUME_PREDECESSOR_COPY'
def signature(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def journal_facts(path):
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok',str(path)
        meta=dict(db.execute('SELECT k,v FROM meta'))
        count,last=db.execute('SELECT count(*),max(seq) FROM events').fetchone()
        assert meta['deployment']=='4b33134d-d832-409e-bf35-f80689beb66b'
        assert meta['build']=='6d5897c26fc83e62a5425148a773d648dfcbacde'
        assert count>0 and last==int(meta['sequence'])
        return (count,last,meta['state'],meta['latest'])
assert journal_facts(live)==journal_facts(snapshot),'SNAPSHOT_VS_VOLUME_CHECKPOINT_MISMATCH'
rows=[]
for item in data.rglob('*'):
    if item.is_symlink(): raise RuntimeError('LOCAL_SYMLINK_NOT_PRESERVED: '+str(item))
    if item.is_file():
        rows.append(dict(path=item.relative_to(data).as_posix(),bytes=item.stat().st_size,sha256=signature(item)))
assert rows and len(rows)>4
rows.sort(key=lambda x:x['path'])
(root/'local-volume-sha256.json').write_text(json.dumps(rows,indent=2)+'\n')
events,last,_,_=journal_facts(snapshot)
summary=dict(status='LOCAL_ARCHIVE_AND_SQLITE_CHECKS_PASS',volume_files=len(rows),
    volume_bytes=sum(row['bytes'] for row in rows),events=events,last_seq=last,
    snapshot_sha256=signature(snapshot),snapshot_bytes=snapshot.stat().st_size,
    original_handoff_status='BLOCKED_HANDOFF_MISSING_HISTORY',
    source_checksum_inventory_available=False,orders=False)
(root/'PHASE_A_COPY_RESULT.json').write_text(json.dumps(summary,indent=2)+'\n')
print('=== PHASE A COPY RESULT ===')
print(json.dumps(summary,indent=2))
PY_ARCHIVE
echo '[4/4] Independent backup kept in Codespace (no source data changed)'
echo "PRESERVE_LOCAL_FOLDER: $ROOT"
echo 'Do not delete Codespace or restore/overwrite Railway volume.'
echo 'Phase B is blocked by HANDOFF_MISSING_HISTORY. Send the final result only.'