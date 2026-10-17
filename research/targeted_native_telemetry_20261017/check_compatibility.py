"""Existing static package/seam check, using preserved native dependency metadata."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from research.native_diagnostic_authorization_20261017.check_static_compatibility import CHILD
from ops.live_recording.install import inventory
from ops.live_recording.policy import canonical,sha,file_sha
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
b=Path('/tmp/btc15-targeted-native-stable-20261017');p=json.loads((HERE/'PACKAGES.json').read_bytes())['packages']
c=json.loads((HERE/'campaign.approval-draft.json').read_bytes());probe=json.loads((ROOT/'research/native_diagnostic_authorization_20261017/PROBE_RECEIPT.json').read_bytes());checks={}
for role in ('main','v81','information'):
 lane='main' if role=='information' else role;root=b/(lane+'-installed');item=p[lane]
 assert sha(canonical(inventory(root)))==item['inventory_sha256'];assert file_sha(b/item['archive'])==item['sha256']
 payload=dict(role=role,config=c,versions=probe['producer_reads'][lane]['dependencies'])
 run=subprocess.run([sys.executable,'-B','-c',CHILD],input=json.dumps(payload),cwd=root,text=True,capture_output=True,timeout=20,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',BTC15_RECORDING_ENABLED='0'))
 assert run.returncode==0,run.stderr
 rows=[json.loads(x.split(' ',1)[1]) for x in run.stdout.splitlines() if x.startswith('BTC15_STATIC_COMPATIBILITY ')];assert len(rows)==1
 checks[role]=rows[0]
# Compute the entire installed Git tree without fetching absent commit objects.
# These tree identities are the successful GitHub create_commit receipts.
def git_object(kind,data):
 return hashlib.sha1(kind+b' '+str(len(data)).encode()+b'\0'+data).digest()
def directory_tree(root):
 rows=[]
 for path in root.iterdir():
  assert not path.is_symlink()
  if path.is_dir():mode=b'40000';oid=directory_tree(path);key=path.name.encode()+b'/'
  else:mode=b'100755' if path.stat().st_mode&0o111 else b'100644';oid=git_object(b'blob',path.read_bytes());key=path.name.encode()
  rows.append((key,mode+b' '+path.name.encode()+b'\0'+oid))
 return git_object(b'tree',b''.join(row for _,row in sorted(rows)))
expected=dict(main='b45595431124c4f8697aa60c2eb8da01534576fc',v81='4cacd21533abcf3e0d56f3ca51b08f9b962d2e8e')
for lane in ('main','v81'):
 actual=directory_tree(b/(lane+'-installed')).hex()
 assert actual==expected[lane],(lane,actual,expected[lane])
 checks[lane]['published_git_tree_exact']=True
 checks[lane]['tree_sha']=actual
 checks[lane]['commit_sha']=p[lane]['candidate_commit']
out=dict(status='PASS',checks=checks,scope='OFFLINE STATIC INSTALL; PRESERVED NATIVE DEPENDENCY METADATA; NOT NATIVE PERFORMANCE')
(HERE/'compatibility.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS: all three roles, exact candidate Git trees, no threads/network/capture')
