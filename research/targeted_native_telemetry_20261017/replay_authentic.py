"""One sequential existing-reader replay; compare to preserved authentic result."""
import hashlib,json,os,resource,subprocess,sys,time
from pathlib import Path
from ops.live_recording.policy import canonical,file_sha
from ops.live_recording.finish import validate_seals
ROOT=Path(__file__).resolve().parents[2]
source=ROOT.parent/'btc15-authentic-20261017'
out=source/'replay-targeted';run=out/'run';run.mkdir(parents=True,exist_ok=False)
manifest=json.loads((ROOT/'research/authentic_diagnostic_evidence_20261017/recovered.json').read_bytes())
for x in manifest['verified']:
 p=source/'raw'/x['path'];assert p.stat().st_size==x['size'] and file_sha(p)==x['sha256']
seals={r:dict(seal=json.loads((source/'raw'/r/'seal.json').read_bytes()),sha256=file_sha(source/'raw'/r/'seal.json')) for r in ('main','v81','information')}
validate_seals(json.loads((ROOT/'research/native_diagnostic_20261017/campaign.approval-draft.json').read_bytes()),seals)
for p in (source/'replay-f1/run').rglob('*'):
 if p.is_file():
  dst=run/p.relative_to(source/'replay-f1/run');dst.parent.mkdir(exist_ok=True);os.link(p,dst)
start=time.monotonic()
with (out/'stdout.txt').open('wb') as stdout,(out/'stderr.txt').open('wb') as stderr:
 result=subprocess.run([sys.executable,'-B','-m','ops.live_recording.finish','--read-only',str(out),'--profile','early_diagnostic'],cwd=ROOT,stdout=stdout,stderr=stderr,timeout=250)
assert result.returncode==0,(out/'stderr.txt').read_text()
checks={}
for name in ('summary.json','windows.jsonl','issues.jsonl','associations.jsonl','v81_native_original_associations.jsonl'):
 raw=(out/'verification'/name).read_bytes();old=(source/'replay-f1/verification'/name).read_bytes()
 assert raw==old,name
 checks[name]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),byte_identical_to_authentic_baseline=True)
for x in manifest['verified']:assert file_sha(source/'raw'/x['path'])==x['sha256']
receipt=dict(returncode=0,elapsed_seconds=time.monotonic()-start,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
 all_12_original_objects_unchanged=True,ledgers=checks,summary=json.loads((out/'verification/summary.json').read_bytes()))
(ROOT/'research/targeted_native_telemetry_20261017/authentic-replay.json').write_bytes(canonical(receipt));print(json.dumps(receipt,indent=2))
