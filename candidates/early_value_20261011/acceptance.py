"""Score frozen policies; never fit using acceptance or opened diagnostic paths."""
from pathlib import Path
import argparse,hashlib,json,shutil
from candidates.early_condition_20261011.study import common,save_data,load_data,write_json
from candidates.three_ladder_20261011.profile_study import ts
from .study import ROOT,OUT,PRIOR,compare_period,replay,summarize


def run(raw):
    freeze=json.loads((OUT/'PRE_ACCEPTANCE_FREEZE.json').read_text())
    for rel,expected in (freeze['files']|freeze['retained_inputs']).items():
        assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==expected,rel
    data,quality=common(raw,ts(freeze['acceptance'][0]),ts(freeze['acceptance'][1]))
    known=set()
    for name in ('development','calibration','diagnostic','acceptance'):
        known.update(load_data(PRIOR/(name+'_inputs.json.gz')))
    assert not known.intersection(data),'Previously opened acceptance contracts'
    reserved=json.loads((OUT/'reservation_overlap.json').read_text())['reserved_expected_contracts']
    assert set(data)<=set(reserved),'Unreserved contract'
    projection=save_data(OUT/'acceptance_inputs.json.gz',data)
    profile=json.loads((OUT/'profile_DISABLED.json').read_text())
    summaries={};sensitivities={}
    for name,cohort in [('acceptance_oct7',data),('opened_oct4',load_data(PRIOR/'diagnostic_inputs.json.gz')),
                       ('opened_oct6',load_data(PRIOR/'acceptance_inputs.json.gz'))]:
        summaries[name],_=compare_period(name,cohort,profile)
        sensitivities[name]={}
        for delay in (5,10,20):
            result=replay(cohort,'unified_value',delay=delay)
            sensitivities[name][str(delay)]=summarize(result,cohort)
    write_json(OUT/'acceptance_comparison.json',summaries)
    write_json(OUT/'delay_sensitivity.json',sensitivities)
    write_json(OUT/'acceptance_manifest.json',dict(reserved_window=freeze['acceptance'],contracts=sorted(data),
        contract_count=len(data),observations=sum(map(len,data.values())),quality=quality,
        raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),projection_sha256=projection,
        prior_contract_overlap=[],native_receipt_depth_available=False,confirmed_fills=0,
        frozen_files_verified=True,signal_only=True,orders=False))
    shutil.copy2(raw.parent/'recovery.json',OUT/'acceptance_recovery.json')
    print(json.dumps({n:{p:{k:v[k] for k in ('proposals','delayed_valid','complete','positive','mean_net_cents','entry_ask_cents')} for p,v in d.items()} for n,d in summaries.items()},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);a=p.parse_args();run(a.raw)
