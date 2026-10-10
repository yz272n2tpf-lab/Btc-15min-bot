#!/usr/bin/env bash
# BTC15 read-only MAIN journal discovery; no downloads or writes.
set -u
python3 - <<'PY'
import json,subprocess
vol='6ced6b1a-3755-4518-a240-c895e936d443'
base='/btc15_v2_product/BTC15_V2_PRODUCT_20261004_R1'
def listing(path):
 p=subprocess.run(['railway','volume','files','--volume',vol,'list',path,'--json'],capture_output=True,text=True)
 if p.returncode:
  print('LIST FAILED',path,'code',p.returncode, p.stderr[-300:]);return None
 try:
  # Railway may include informational output before the JSON object.
  t=p.stdout
  j=json.loads(t[t.index('{'):])
  return j.get('files',[])
 except Exception as e:
  print('PARSE FAILED',path,str(e),p.stdout[-200:]);return None
print('BTC15 READ-ONLY JOURNAL DISCOVERY')
folders=listing(base)
if folders is None:raise SystemExit(1)
print('REVISION FOLDERS:',len(folders))
for item in folders:
 if item.get('type')!='directory':continue
 p=item.get('path')
 print('FOLDER:',item.get('name'))
 children=listing(p)
 if children is None:continue
 for c in children:
  n=c.get('name','')
  if n.endswith('.sqlite3') or n.endswith('.sqlite3-wal') or n.endswith('.sqlite3-shm') or n.endswith('.json') or n.endswith('.gz'):
   print('  FILE:',n,'SIZE:',c.get('size'))
  elif c.get('type')=='directory':
   print('  SUBDIR:',n)
print('DISCOVERY COMPLETE: no files downloaded, changed or deployed')
PY
