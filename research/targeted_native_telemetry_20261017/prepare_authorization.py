"""Materialize reviewable config/actions only; executes no Railway/SSH calls."""
import json
from pathlib import Path
from ops.live_recording.policy import canonical,sha
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
BUILDS={'main':'8847c61b0a98c436618d7aef8b07a1626bc00e13','v81':'510da93a925a66f2040cc10dd08c2532caccece2'}
RUN='CORRECTED_DIAG_20261017_8847c61b_510da93a'
b=Path('/tmp/btc15-targeted-native-stable-20261017');packages=json.loads((b/'PACKAGES.json').read_bytes())
old=json.loads((ROOT/'research/native_diagnostic_20261017/campaign.approval-draft.json').read_bytes());c=json.loads(canonical(old))
c['run_id']=RUN;c['root']='/data/btc15_recordings/'+RUN
for role,r in c['roles'].items():
 lane='main' if role=='information' else role;r['build']=BUILDS[lane];r['manifest_sha256']=packages['packages'][lane]['manifest_sha256']
(HERE/'campaign.approval-draft.json').write_bytes(canonical(c));config_sha=sha(canonical(c))
a=json.loads((ROOT/'research/native_diagnostic_authorization_20261017/SELECTIVE_ACTIONS.json').read_bytes())
for action in a['activation']:
 lane=action['role'];args=action['arguments'];text=json.dumps(args)
 text=text.replace(old['run_id'],RUN).replace(sha(canonical(old)),config_sha)
 text=text.replace(old['roles'][lane]['build'],BUILDS[lane]).replace(old['roles'][lane]['manifest_sha256'],c['roles'][lane]['manifest_sha256'])
 text=text.replace('research/native-diagnostic-'+lane+'-20261017','research/corrected-native-'+lane+'-20261017')
 action['arguments']=json.loads(text)
a.pop('source_patch_sha256');a['action_list_sha256']={name:sha(canonical(a[name])) for name in ('activation','rollback')}
a['run_id']=RUN;a['configuration_sha256']=config_sha;a['authorized']=False;a['executed']=False
(HERE/'SELECTIVE_ACTIONS.json').write_text(json.dumps(a,indent=2)+'\n')
plan=json.loads((ROOT/'research/native_operational_20261017/NATIVE_READ_PLAN.json').read_bytes())
for lane in ('main','v81'):
 plan[lane]['identity']['RAILWAY_DEPLOYMENT_ID']=packages['packages'][lane]['deployment']
 packages['packages'][lane].update(candidate_commit=BUILDS[lane],candidate_branch='research/corrected-native-'+lane+'-20261017')
packages['packages']['information']['candidate_commit']=BUILDS['main']
(HERE/'NATIVE_READ_PLAN.json').write_bytes(canonical(plan));(HERE/'PACKAGES.json').write_text(json.dumps(packages,indent=2)+'\n')
# Reuse the completed provisioning implementation. Only exact identities and
# artifact paths change; a required explicit switch prevents accidental use.
original=(ROOT/'research/native_diagnostic_execution_20261017/prepare_once.py').read_text()
original=original.replace(sha(canonical(old)),config_sha).replace(old['run_id'],RUN)
original=original.replace("assert os.environ.get('RAILWAY_GIT_COMMIT_SHA')=='950e4b5e401d501bb26b5a66473e06500e8c08ac','RESEARCH_SOURCE'", "assert os.environ.get('RAILWAY_GIT_COMMIT_SHA')==os.environ.get('BTC15_APPROVED_RESEARCH_SHA') and len(os.environ.get('BTC15_APPROVED_RESEARCH_SHA',''))==40,'RESEARCH_SOURCE'")
original=original.replace('research/native_diagnostic_20261017/campaign.approval-draft.json','research/targeted_native_telemetry_20261017/campaign.approval-draft.json').replace('research/native_operational_20261017/NATIVE_READ_PLAN.json','research/targeted_native_telemetry_20261017/NATIVE_READ_PLAN.json')
assert original.endswith('run()\n')
original=original[:-6]+"if __name__=='__main__':\n    assert sys.argv[1:]==['--separately-authorized-once'],'SEPARATE_AUTHORIZATION_REQUIRED'\n    run()\n"
(HERE/'provision_once.py').write_text(original)
print(json.dumps(dict(run_id=RUN,config_sha256=config_sha,packages={k:{f:v.get(f) for f in ('candidate_commit','sha256','bytes','manifest_sha256','install_sha256')} for k,v in packages['packages'].items()}),indent=2))
