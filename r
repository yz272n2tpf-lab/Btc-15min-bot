#!/usr/bin/env bash
# BTC15 read-only journal metadata listing. No file downloads or writes.
set -u
python3 - <<'PY'
import json,subprocess
vol='6ced6b1a-3755-4518-a240-c895e936d443'
base='/btc15_v2_product/BTC15_V2_PRODUCT_20261004_R1'
def ls(path):
 p=subprocess.run(['railway','volume','files','--volume',vol,'list',path,'--json'],capture_output=True,text=True)
 if p.returncode:
  print('FAILED',path,'exit',p.returncode,p.stderr[-150:]);return None
 try:
  data=p.stdout[p.stdout.index('{'):]
  return json.loads(data)['files']
 except Exception as e:
  print('PARSE FAILED',str(e));return None
print('BTC15 JOURNAL METADATA ONLY — READ ONLY')
folders=ls(base)
if folders is None:raise SystemExit(1)
for d in folders:
 if d.get('type')!='directory':continue
 print('\nFOLDER',d.get('name'),'modified',d.get('modifiedAt'))
 children=ls(d['path'])
 if children is None:continue
 for c in children:
  if c.get('name') in ('main.sqlite3','main.sqlite3-wal','main.sqlite3-shm','main.json','main.admin-health.json'):
   print(c['name'],'modified',c.get('modifiedAt'),'bytes',c.get('size'))
print('\nLISTING ONLY. No active checkpoint authenticated; no downloads or writes.')
PY
