"""Local-only exact-source installation/rollback. Never calls Railway or git push."""
import argparse,json,shutil
from pathlib import Path
from .policy import BASES,MANIFESTS,file_sha,canonical,need,safe_path,atomic

def inventory(root):return {str(p.relative_to(root)):file_sha(p) for p in root.rglob('*') if p.is_file()}
def local(p):
 p=safe_path(p);need(not p.is_relative_to('/data') and not p.is_relative_to('/app'),'LOCAL_INSTALL_ONLY');return p
def prepare(source,target,candidate,lane,source_hashes,old_allowlist):
 source,target,candidate=local(source),local(target),local(candidate)
 need(not target.exists(),'NEW_ISOLATED_TARGET_REQUIRED')
 need(inventory(source)==source_hashes,'EXACT_ORIGINAL_SOURCE_TREE')
 need(file_sha(source/'BTC15_V2_PRODUCT_RELEASE_R1.json')==MANIFESTS[lane],'ORIGINAL_MANIFEST_HASH')
 original=json.loads((source/'BTC15_V2_PRODUCT_RELEASE_R1.json').read_bytes())
 for name,h in original['files_sha256'].items():need(file_sha(source/name)==h,'ORIGINAL_RELEASE_SOURCE:'+name)
 for name,h in original['lane_protected_files'][lane].items():need(file_sha(source/name)==h,'ORIGINAL_PROTECTED:'+name)
 shutil.copytree(source,target)
 names={x['path'] for x in old_allowlist['files']}
 names.update(str(p.relative_to(candidate)) for p in (candidate/'ops/live_recording').glob('*.py'))
 # reader extensions are already in the old allowlist; tests and research are never deployed.
 names={n for n in names if not Path(n).name.startswith('test_')}
 for name in sorted(names):
  dst=target/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(candidate/name,dst)
 patches={
 'btc15_v2_native.py':("    native_main()","    from ops.live_recording.bootstrap import start\n    start('main')\n    native_main()"),
 'btc15_v2_launch.py':("        return v81_main(ROOT)","        from ops.live_recording.bootstrap import start\n        start('v81')\n        return v81_main(ROOT)"),
 'btc15_v2_product/worker.py':("    service.main()","    from ops.live_recording.bootstrap import start\n    start('information')\n    service.main()")}
 for name,(before,after) in patches.items():
  p=target/name;t=p.read_text();need(t.count(before)==1,'EXACT_ENTRY_SEAM:'+name);p.write_text(t.replace(before,after));names.add(name)
 shutil.copyfile(source/'BTC15_V2_PRODUCT_RELEASE_R1.json',target/'BTC15_RECORDER_ORIGINAL_RELEASE.json');names.add('BTC15_RECORDER_ORIGINAL_RELEASE.json')
 candidate_manifest=json.loads(canonical(original))
 for name in sorted(names):candidate_manifest['files_sha256'][name]=file_sha(target/name)
 candidate_manifest['recorder']=dict(default_off=True,base_release=BASES[lane],original_manifest_sha256=MANIFESTS[lane],signal_only=True,orders=False)
 atomic(target/'BTC15_V2_PRODUCT_RELEASE_R1.json',candidate_manifest);names.add('BTC15_V2_PRODUCT_RELEASE_R1.json')
 # Independently reject every frozen/protected-byte change before returning an installable tree.
 freeze=json.loads((source/'BTC15_LADDER_COMPLETION_FREEZE_20261003.json').read_bytes())
 for name,h in {**freeze['files_sha256' if lane=='main' else 'v81_files_sha256'],**original['lane_protected_files'][lane]}.items():need(file_sha(target/name)==h,'FROZEN_OVERLAY_COLLISION:'+name)
 receipt=dict(schema='BTC15_RECORDER_INSTALL_V1',lane=lane,base_release=BASES[lane],original_files=source_hashes,candidate_files={n:file_sha(target/n) for n in sorted(names)},added=sorted(names-set(source_hashes)),default_off=True,production_executed=False)
 atomic(target/'BTC15_RECORDER_INSTALL.json',receipt)
 return receipt
def rollback(target,source):
 target,source=local(target),local(source);r=json.loads((target/'BTC15_RECORDER_INSTALL.json').read_bytes())
 need(inventory(source)==r['original_files'],'ROLLBACK_ORIGINAL_DRIFT')
 for n,h in r['candidate_files'].items():need(file_sha(target/n)==h,'ROLLBACK_REFUSE_CANDIDATE_DRIFT:'+n)
 expected=dict(r['original_files'],**r['candidate_files']);actual=inventory(target);actual.pop('BTC15_RECORDER_INSTALL.json')
 need(actual==expected,'ROLLBACK_REFUSE_OTHER_CHANGES')
 for n in r['candidate_files']:
  if n in r['original_files']:shutil.copyfile(source/n,target/n)
  else:(target/n).unlink()
 (target/'BTC15_RECORDER_INSTALL.json').unlink()
 need(inventory(target)==r['original_files'],'ROLLBACK_HASH_MISMATCH')
 return dict(restored_files=len(r['original_files']),exact=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('operation',choices=['prepare','rollback']);p.add_argument('--source',required=True);p.add_argument('--target',required=True);p.add_argument('--candidate');p.add_argument('--lane',choices=['main','v81']);p.add_argument('--source-hashes');p.add_argument('--old-allowlist');a=p.parse_args()
 r=rollback(a.target,a.source) if a.operation=='rollback' else prepare(a.source,a.target,a.candidate,a.lane,json.loads(Path(a.source_hashes).read_bytes()),json.loads(Path(a.old_allowlist).read_bytes()))
 print(json.dumps(r,sort_keys=True))
if __name__=='__main__':main()
