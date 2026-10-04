"""Read-only byte/AST proof, complementing causal runtime differential tests."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BRIDGE_BASE='1d942014af22ab4acb3048a29dbbc831d5ecc924'
BASES={'main':'de4f3e20b8657eb8cfee91bd4e525c103b5bf513','v81':'60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1'}

def tree(source):
    return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}

def inventory(lane='main',root=ROOT):
    base=BASES[lane]
    tracked=subprocess.check_output(['git','ls-tree','-r','--name-only',base],cwd=root,text=True).splitlines()
    changes=[]
    for name in tracked:
        old=subprocess.check_output(['git','show',base+':'+name],cwd=root)
        p=root/name
        if not p.is_file() or p.read_bytes()!=old:changes.append(name)
    assert not changes,changes
    old_bridge=subprocess.check_output(['git','show',BRIDGE_BASE+':ops/btc15_v2_scoring/bridge.py'],cwd=root)
    old,new=tree(old_bridge),tree((root/'ops/btc15_v2_scoring/bridge.py').read_bytes())
    allowed={'production_snapshot','load_snapshot','score','main'}
    modified=sorted(name for name in old if old[name]!=new.get(name))
    assert set(modified)<=allowed,modified
    unchanged=sorted(name for name in old if old[name]==new.get(name))
    assert all(name in unchanged for name in ('lane_contract','event_identity','authoritative','origin_check','scalp_paths','snapshot','load_scorer'))
    scorer='btc15_cohort_evidence_v1.py'
    baseline_scorer=subprocess.check_output(['git','show',BRIDGE_BASE+':'+scorer],cwd=root)
    assert (root/scorer).read_bytes()==baseline_scorer
    result=dict(schema='BTC15_SEMANTIC_INVENTORY_R1',lane=lane,frozen_base=base,
        original_tracked_files=len(tracked),original_tracked_files_changed=changes,
        original_bridge_sha256=hashlib.sha256(old_bridge).hexdigest(),
        established_scorer_sha256=hashlib.sha256(baseline_scorer).hexdigest(),
        strict_bridge_functions_ast_identical=unchanged,bridge_functions_with_additive_changes=modified,
        interpretation='Byte/AST identity plus separate runtime differential tests; no claim that network availability is identical',
        orders=False,signal_only=True)
    path=root/'qualification/v2_product_20261004'/f'{lane}_semantic_inventory.json'
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--lane',choices=list(BASES),default='main')
    inventory(p.parse_args().lane)
