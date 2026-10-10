"""Prepare a reviewed BTC15 MAIN manifest candidate without mutating source or production.
The protected frozen model and SCALP inputs remain byte-identical to the
existing release manifest. Output is an artifact for release review only.
"""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parent
original=json.loads((root/'BTC15_V2_PRODUCT_RELEASE_R1.json').read_text())
protected=original['lane_protected_files']['main']
for name, expected in protected.items():
    actual=hashlib.sha256((root/name).read_bytes()).hexdigest()
    if actual!=expected:
        raise SystemExit('PROTECTED_MAIN_CHANGED: '+name)
candidate=json.loads(json.dumps(original))
changes=[]
for name, expected in original['files_sha256'].items():
    actual=hashlib.sha256((root/name).read_bytes()).hexdigest()
    candidate['files_sha256'][name]=actual
    if actual!=expected:
        changes.append(name)
allowed={
    'btc15_v2_product/directional.py',
    'btc15_v2_product/early_entry.py',
    'btc15_v2_product/early_management.py',
    'btc15_v2_product/trade_clarity.py',
    'btc15_v2_product/early_origin_transfer.py',
    'btc15_v2_product/panel.js',
}
if set(changes)-allowed:
    raise SystemExit('UNREVIEWED_FILE_CHANGES: '+repr(sorted(set(changes)-allowed)))
out=root/'qualification'/'early-release-review'
out.mkdir(parents=True,exist_ok=True)
payload=json.dumps(candidate,indent=2,ensure_ascii=False)+'\n'
(out/'BTC15_V2_PRODUCT_RELEASE_R1.candidate.json').write_text(payload)
summary={'changed_manifest_files':changes,
         'protected_main_unchanged':True,
         'candidate_manifest_sha256':hashlib.sha256(payload.encode()).hexdigest(),
         'approval_status':'MANIFEST_COMMITTED_PRODUCTION_DEPLOYMENT_NOT_AUTHORIZED'}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print('HANDOFF_SHA256:',candidate['files_sha256']['btc15_v2_product/early_origin_transfer.py'])
print(json.dumps(summary,indent=2))
