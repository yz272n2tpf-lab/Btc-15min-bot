"""Unpack the three fixed offline replay artifacts, never an arbitrary path."""
from pathlib import Path
import sys,zipfile

def hydrate(workspace):
    repo=Path(__file__).resolve().parents[2]
    mapping={'incident/records.jsonl':'recovered-common/incident/records.jsonl',
             'pr36/records.jsonl':'recovered-common/pr36/records.jsonl',
             'pr36/feature_frames.jsonl':'recovered-feature-frames/pr36_frames.jsonl'}
    with zipfile.ZipFile(repo/'audit/existing_evidence_20261011/bounded_replay_inputs.zip')as z:
        assert set(z.namelist())==set(mapping)
        for member,dest in mapping.items():
            p=workspace/dest;p.parent.mkdir(parents=True,exist_ok=True)
            raw=z.read(member)
            if p.exists() and p.read_bytes()!=raw:raise ValueError('Existing artifact conflict: '+str(p))
            p.write_bytes(raw)
    print('Three bounded offline source artifacts ready; no production access.')

if __name__=='__main__':hydrate(Path(sys.argv[1]))
