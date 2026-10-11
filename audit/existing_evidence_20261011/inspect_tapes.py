"""Summarize archived JSONL and recover original state observations, read-only."""
import gzip,json,hashlib
from collections import Counter
from pathlib import Path

def run(workspace):
    out=workspace/'repo/audit/existing_evidence_20261011';catalog=json.loads((out/'corpus_inventory.json').read_text())
    summaries=[];states={};events=[]
    for item in catalog['files']:
        name=item['name'];sha=item['sha256']
        if not(name.endswith(('.jsonl','.jsonl.gz')) or ('common' in name and name.endswith('.gz'))):continue
        if any(x in name.lower() for x in ['synthetic','generated/','features_no_outcomes','monitor','clock_']):continue
        p=workspace/'evidence-corpus'/sha
        if not p.exists():continue
        opener=gzip.open if name.endswith('.gz') else open
        n=bad=0;types=Counter();tickers=set();times=[];state_n=0;first=None;stream_error=None
        with opener(p,'rt',encoding='utf8') as f:
            while True:
                try:line=f.readline()
                except (EOFError,OSError,UnicodeError) as exc:
                    stream_error=str(exc);break
                if not line:break
                n+=1
                try:r=json.loads(line)
                except Exception:bad+=1;continue
                if first is None:first=r
                e=r.get('event',r);b=e.get('body',e);s=b.get('state')
                typ=e.get('kind',r.get('record_type','ROW'));types[str(typ)]+=1
                if not isinstance(s,dict):
                    if isinstance(r.get('state'),dict):s=r['state']
                    elif isinstance(r.get('main'),dict):s=r['main']
                candidates=[]
                if isinstance(s,dict):candidates.append((s,r.get('service'),r.get('response_received_utc') or r.get('end_epoch') or b.get('opportunity_generated_utc')))
                if isinstance(b.get('emission'),dict) and isinstance(b['emission'].get('state'),dict):
                    candidates.append((b['emission']['state'],'v81',None))
                for source in r.get('sources',[]):
                    if isinstance(source,dict) and isinstance(source.get('state'),dict):
                        candidates.append((source['state'],source.get('service'),source.get('response_received_utc')))
                for s,service,receipt in candidates:
                    if not s.get('contract'):continue
                    t=s.get('source_timestamp_utc') or s.get('generated_utc')
                    state_n+=1;tickers.add(s['contract'])
                    if t:times.append(t)
                    # Original raw bodies stay in the hashed source archive. Chart
                    # arrays are not decision inputs and need not be duplicated.
                    s={k:v for k,v in s.items() if k!='chart'}
                    key=hashlib.sha256(json.dumps(s,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                    v=states.setdefault(key,{'state':s,'source_shas':[],'recorded_at':receipt,'kind':typ,'producer':e.get('identity'),'service':service})
                    if sha not in v['source_shas']:v['source_shas'].append(sha)
                if not candidates:
                    t=r.get('timestamp_utc') or r.get('observed_utc') or r.get('ts')
                    if isinstance(t,str):times.append(t)
                    contract=r.get('contract') or r.get('ticker')
                    if isinstance(contract,str):tickers.add(contract)
        summaries.append({'sha256':sha,'name':name,'rows':n,'malformed':bad,'stream_error':stream_error,'kinds':dict(types),'contracts':len(tickers),'contract_ids':sorted(tickers),'time_range':[min(times),max(times)] if times else None,'state_rows':state_n,'example_keys':list(first or {})})
    (out/'tape_inventory.json').write_text(json.dumps(summaries,indent=2))
    # Persist only MAIN projections for policy analysis. Full SCALP records remain
    # in original sources and in the tape accounting above.
    with (workspace/'recovered_main_states.jsonl').open('w') as f:
        for key,v in states.items():
            if isinstance(v['state'].get('final'),dict):
                f.write(json.dumps(dict(state_hash=key,**v),separators=(',',':'))+'\n')
    print(json.dumps({'tapes':len(summaries),'rows':sum(x['rows'] for x in summaries),'unique_states':len(states)}))
if __name__=='__main__':
    import sys
    run(Path(sys.argv[1]))
