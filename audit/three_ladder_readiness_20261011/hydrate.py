"""Materialize only bounded included replay inputs in an isolated workspace.

Run the parent audit's hydrator first for the original four-contract inputs.
Never overwrite a conflicting existing file, never open a production path.
"""
from pathlib import Path
import hashlib,json,sys,zipfile

def main(workspace):
    workspace=Path(workspace).resolve();audit=workspace/'repo/audit/three_ladder_readiness_20261011'
    destination=workspace/'readiness-evidence'
    if workspace==Path('/') or workspace.is_relative_to('/data'):raise ValueError('Isolated workspace required')
    source=json.loads((audit/'input_projection_manifest.json').read_text())
    expected={r['name']+'/records.jsonl':r['projection_sha256'] for r in source}
    expected.update({'features-'+str(r['offset'])+'.jsonl':r['sha256'] for r in json.loads((audit/'feature-ranges.json').read_text())})
    with zipfile.ZipFile(audit/'bounded_candidate_inputs.zip') as z:
        if set(z.namelist())!=set(expected):raise ValueError('Unexpected archive membership')
        for name,h in expected.items():
            raw=z.read(name)
            if hashlib.sha256(raw).hexdigest()!=h:raise ValueError('Input hash mismatch')
            p=destination/name
            if p.exists() and p.read_bytes()!=raw:raise ValueError('Existing input differs; use a fresh workspace')
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    print('Verified bounded replay inputs:',len(expected))

if __name__=='__main__':main(sys.argv[1])
