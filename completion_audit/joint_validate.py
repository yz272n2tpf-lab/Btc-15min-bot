"""Score the locked joint probes once; no search/reselection on validation."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import itertools
import json
from pathlib import Path
from joint_diagnosis import load_rows,main_rows,paths,metric,calls,diagnose,epoch,stats
from joint_v81 import rows as vrows,candidates,run as vdiagnose


def validate(data,market_dir,lock_path,output):
    lock=json.loads(lock_path.read_text());claimed=lock.pop('canonical_sha256')
    if hashlib.sha256(json.dumps(lock,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=claimed:
        raise ValueError('Candidate lock altered')
    for name,sha in lock['input_sha256'].items():
        if hashlib.sha256((lock_path.parent/name).read_bytes()).hexdigest()!=sha:
            raise ValueError('Locked analysis/input changed: '+name)
    start,end=map(epoch,lock['validation_data']);scheduled=int((end-start)/900)
    markets={};missing=[]
    for f in market_dir.glob('*.json'):
        obj=json.loads(f.read_text());m=obj.get('market')
        if m and start<=epoch(m['open_time'])<end:markets[m['ticker']]=m
        elif obj['_read_only_evidence']['status']==404:missing.append(obj['_read_only_evidence']['scheduled_open'])
    rows=main_rows(data/'main.jsonl.gz',start,end);clean=paths(load_rows(data/'inputs.jsonl.gz'))
    vs,reasons,bad=vrows(data/'v81.jsonl.gz',start,end)
    result=dict(phase='internal_development_validation_only',candidate_lock_sha256=claimed,
        validation_data=lock['validation_data'],scheduled=scheduled,official=len(markets),
        missing_official_slots=sorted(missing),rows=len(rows),policies={},joint=[],orders=False,
        original_validation_untouched=True,final_holdout_untouched=True,
        diagnosis=diagnose(rows,markets,scheduled,clean),v81_diagnosis=vdiagnose(vs,markets,scheduled,clean,False))
    callsets={}
    for lane,policies in lock['policies'].items():
        result['policies'][lane]={}
        for name,p in policies.items():
            entries=candidates(vs,p) if lane=='v81' else calls(rows,lane,p)
            result['policies'][lane][name]=metric(entries,markets,scheduled,lane,clean,True)
            callsets[lane,name]=set(r['ticker'] for r in entries)
    for combo in itertools.product(*(list(lock['policies'][l]) for l in ['early','final','scalp'])):
        sets=[callsets[l,n] for l,n in zip(['early','final','scalp'],combo)]
        result['joint'].append(dict(policies=dict(zip(['early','final','scalp'],combo)),
            union_contracts=len(set.union(*sets)),
            unique_contracts={l:len(sets[i]-set.union(*(sets[j] for j in range(3) if j!=i))) for i,l in enumerate(['early','final','scalp'])},
            overlap={a+'+'+b:len(sets[i]&sets[j]) for (i,a),(j,b) in itertools.combinations(enumerate(['early','final','scalp']),2)}))
    result['calibration_anchors']={}
    for anchor in [8,5,2]:
        used={}
        for r in rows:
            if (r['fair'] is not None and r['ticker'] not in used and anchor-.5<=r['receipt_left']<=anchor):used[r['ticker']]=r
        scored=metric(list(used.values()),markets,scheduled,'final',detail=True)
        result['calibration_anchors'][str(anchor)]=scored
    with output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({l:{n:{k:m[k] for k in ['calls','contracts','wins','accuracy','entry','minutes_left','hit10']} for n,m in ps.items()} for l,ps in result['policies'].items()},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--markets',type=Path,required=True)
    p.add_argument('--lock',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();validate(a.data,a.markets,a.lock,a.output)
