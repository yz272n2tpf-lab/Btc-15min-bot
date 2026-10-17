"""Build with the existing installer, pinned source exports and rollback checks."""
import argparse,json
from pathlib import Path
from research.native_diagnostic_20261017 import packages
from ops.live_recording.policy import canonical

def build(out):
 packages.BASELINE='be1c02a1e0a320b668c9b7aa394aae6fe1f88269'
 # Last preserved successful rollback deployments; recheck live identity only
 # at the separately authorized activation boundary, never deploy here.
 packages.DEPLOYMENTS.update(main='3d4b26ce-d11c-4b3c-ac8c-1ed5a403f3c9',v81='c04d806f-d279-4a0b-8b3b-5f6316c985a6')
 result=packages.build(out);root=Path(out)
 for lane in ('main','v81'):
  p=result['packages'][lane];old=root/p['archive'];p['archive']='btc15-corrected-native-'+lane+'-20261017.tar.gz';old.rename(root/p['archive'])
  p['package_id']='BTC15_TARGETED_NATIVE_'+lane.upper()+'_20261017'
 info=result['packages']['information'];info['package_id']='BTC15_TARGETED_NATIVE_INFORMATION_20261017';info['archive']=result['packages']['main']['archive']
 result['scope']='RECORDER_ONLY_PUBLICATION_OUTCOME_AND_QUOTE_OVERRUN; PRIOR_F1_FIXES_RETAINED'
 (root/'PACKAGES.json').write_bytes(canonical(result));return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);args=p.parse_args()
 r=build(args.out);print(json.dumps({k:{f:v[f] for f in ('package_id','sha256','bytes')} for k,v in r['packages'].items()},indent=2))
