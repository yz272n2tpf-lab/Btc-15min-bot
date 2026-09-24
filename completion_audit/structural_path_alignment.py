"""Compare existing native V8.1 book paths with the independent clean tape.

No replay regeneration: both immutable input files are read in memory. Same-feed
bid marks improve label alignment but do not establish fills or independence.
"""
from collections import defaultdict,Counter
import argparse
import hashlib
import json
from pathlib import Path
from structural_batch import DATA,ROOT,verify_inputs,markets,scalp_fit,scalp_calls,score_entries
from joint_diagnosis import load_rows,paths,epoch
from joint_v81 import rows as vrows


def native_paths(records):
    tape=defaultdict(list);seen=set();excluded=Counter()
    for r in records:
        d=r['state'];p=d.get('input_provenance') or {};q=p.get('quote') or {};b=p.get('brti') or {};t=r['receipt_epoch']
        try:
            good=(p['schema']=='V81_TIMESTAMPED_INPUTS_V1' and p['orders'] is False and p['signal_only'] is True
                and p['ticker']==d['contract']==q['ticker'] and p['open_ts']<=t<p['close_ts']
                and p['close_ts']-p['open_ts']==900 and q['transport']=='timestamped_contiguous_ws'
                and 0<=t-q['source_ts_ms']/1000<=6 and 0<=t-b['source_ts_ms']/1000<=5
                and b['status']=='PRIMARY_OK' and b['clean_for_qualification'] is True
                and 0<=t-epoch(d['generated_utc'])<=3.5 and 0<=t-epoch(p['btc_source_utc'])<=10)
        except (KeyError,TypeError,ValueError):good=False
        if not good:excluded['source_or_publication']+=1;continue
        key=(p['ticker'],q['validated_at_ms'])
        if key in seen:continue
        seen.add(key)
        tape[p['ticker']].append(dict(t=t,target=p['target'],**{k:q[k] for k in ('up_bid','up_ask','down_bid','down_ask')}))
    return tape,dict(excluded)


def run(output):
    verify_inputs();native,bad=native_paths(load_rows(DATA/'v81.jsonl.gz'));independent=paths(load_rows(DATA/'inputs.jsonl.gz'))
    result=dict(orders=False,signal_only=True,same_feed_marks_are_not_fills=True,
        purpose='Test label alignment as the next bottleneck after architecture candidates failed',
        no_new_threshold_search=True,native_rejections=bad,source_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    model=None
    for part,start,end,n in [('tuning','2026-09-24T00:15Z','2026-09-24T06:45Z',26),('validation','2026-09-24T07:00Z','2026-09-24T12:15Z',21)]:
        truth=markets(part);vr,_,_=vrows(DATA/'v81.jsonl.gz',epoch(start),epoch(end))
        if part=='tuning':model=scalp_fit(vr,native);result['native_model']=model
        model_entries=scalp_calls(vr,model)
        existing=json.loads((ROOT/'STRUCTURAL_LEAD_LAG_STRICT_20260924.json').read_text())[part]['policies']
        # Entries already frozen by the earlier fixed policy; paths cannot select entry times.
        policies={name:m['entries'] for name,m in existing.items()}
        policies['native_first_passage_head']=model_entries
        result[part]={name:dict(native=score_entries(entries,truth,n,'v81',native),
                               independent=score_entries(entries,truth,n,'v81',independent)) for name,entries in policies.items()}
    with output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(native_model=model,parts={p:{k:{source:dict(calls=m['calls'],contracts=m['contracts'],
        first_passage=m['first_passage']) for source,m in sources.items()} for k,sources in result[p].items()} for p in ('tuning','validation')}),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
