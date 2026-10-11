"""Post-replay descriptions only; never feeds candidate rules or calibration."""
from collections import Counter
from pathlib import Path
import gzip, hashlib, json
from .engine import Rules, features, screen
from .study import load_data, write_json


def run():
    out=Path('audit/early_condition_20261011');result={}
    for name,inputs in [('acceptance','acceptance'),('diagnostic_opened_holdout','diagnostic'),('development','development'),('calibration','calibration')]:
        data=load_data(out/(inputs+'_inputs.json.gz'));evaluation=json.loads((out/(name+'_evaluation.json')).read_text())
        details=[]
        for e in evaluation['episodes']:
            o=e['origin'];s=e['scenario']
            if s:
                seq=data[o['contract']];r=next(x for x in seq if x['time']==s['entry_at'])
                x=features([z for z in seq if z['time']<=r['time']],r,o['side'],Rules())
                failures=screen(r,x,o['side'],Rules())
                details.append(dict(origin_id=o['id'],entry_recheck_failures=failures,
                    still_structurally_qualified=not failures,net=s['net'],complete=s['complete_path']))
        result[name]=dict(delayed_entry_rechecks=details,passed_complete=sum(not r['entry_recheck_failures']and r['complete']for r in details),
            note='Post-analysis sensitivity only. Primary scenarios execute at first observed ASK after delay regardless of later requalification; no actual fill. No rules altered.')
    write_json(out/'execution_recheck_diagnostic.json',result)
    print(json.dumps({k:{a:b for a,b in v.items()if a!='delayed_entry_rechecks'}for k,v in result.items()},indent=2))


if __name__=='__main__':run()
