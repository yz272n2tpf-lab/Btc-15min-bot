"""Bounded evidence diagnostics; no fitting, future-best-price or rule changes."""
from collections import Counter,defaultdict
from pathlib import Path
import hashlib,json,subprocess
from candidates.early_condition_20261011.engine import Rules as PriorRules,features as prior_features,screen as prior_screen
from candidates.early_condition_20261011.study import load_data,write_json
from .study import OUT,PRIOR,ROOT


def review():
    evidence={}
    for name in ('development','calibration'):
        data=load_data(PRIOR/(name+'_inputs.json.gz'));universe=defaultdict(set);gates=Counter();examples=[]
        for c,rows in data.items():
            for i,r in enumerate(rows):
                ask=r[r['side'].lower()+'_ask']
                if not r['healthy'] or r['left']<=190:continue
                if ask<=.55:universe['any_cheap_healthy'].add(c)
                if ask<=.55 and r['p']>=.75:
                    universe['cheap_confident'].add(c)
                    x=prior_features(rows[:i+1],r,r['side'],PriorRules())
                    failures=prior_screen(r,x,r['side'],PriorRules())
                    gates.update(failures)
                    examples.append(dict(contract=c,time=r['time'],ask=ask,p=r['p'],left=r['left'],prior_rejections=failures))
        new=json.loads((OUT/(name+'_unified_value.json')).read_text())
        old=json.loads((OUT/(name+'_condition_v1.json')).read_text())
        comparisons=[]
        for e in new['episodes']:
            o=e['origin'];prior=next((p['origin'] for p in old['episodes'] if p['origin']['contract']==o['contract']),None)
            comparisons.append(dict(contract=o['contract'],value_ask=o['ask'],value_time=o['time'],
                prior_ask=prior['ask'] if prior else None,prior_time=prior['time'] if prior else None,
                delay_revalidation=e['delayed_revalidation'],
                canceled_quote_scenario=e['scenario_without_revalidation'] if not e['delayed_revalidation']['valid'] else None))
        evidence[name]=dict(independent_candidate_contract_counts={k:len(v) for k,v in universe.items()},
            cheap_confident_observations=len(examples),old_gate_rejections_on_those_observations=dict(gates),
            qualified_value_examples=comparisons,cheap_confident_inputs=examples)
    write_json(OUT/'selection_diagnosis.json',evidence)
    # Byte-level preservation across every previously tracked file, stronger
    # than rerunning unrelated component tests. New paths alone are allowed.
    changed=subprocess.check_output(['git','diff','2f00d06ad6dd707934844d0c438c7fd39de8e70e','--name-status']).decode().splitlines()
    bad=[line for line in changed if not line.startswith('A\t') or not line.split('\t')[-1].startswith(('candidates/early_value_20261011/','audit/early_value_20261011/'))]
    assert not bad,bad
    from btc15_v2_product.release import verify_files
    manifest=verify_files('main')
    write_json(OUT/'protection_checks.json',dict(base='2f00d06ad6dd707934844d0c438c7fd39de8e70e',
        modified_preexisting_files=[],main_release_files=len(manifest['files_sha256']),
        protected_main_files=len(manifest['lane_protected_files']['main']),
        main_release_manifest_sha256=hashlib.sha256((ROOT/'BTC15_V2_PRODUCT_RELEASE_R1.json').read_bytes()).hexdigest(),
        independent_scalp_revision='6e04aced0f718b29f8ed805abcc0f76b01ed5096',
        final_gates='Unchanged $75/$50,90% and supporting qualification',
        dashboard_order='Unchanged FINAL -> EARLY -> SCALP -> chart',
        baseline_early_unchanged=True,production_mutations=0,signal_only=True,orders=False))
    print(json.dumps({k:{x:v[x] for x in ('independent_candidate_contract_counts','cheap_confident_observations','old_gate_rejections_on_those_observations')} for k,v in evidence.items()},indent=2))


if __name__=='__main__':review()
