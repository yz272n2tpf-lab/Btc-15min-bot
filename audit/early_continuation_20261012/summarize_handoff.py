"""Summarize saved outputs only; does not run signals, fit or replay."""
from collections import Counter,defaultdict
from pathlib import Path
import gzip,json,statistics

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
ledger=json.loads(gzip.decompress((OUT/'evaluation/LABEL_LEDGER.json.gz').read_bytes()))
results=json.loads((OUT/'evaluation/RESULTS.json').read_text())
artifact=json.loads((OUT/'evaluation/CONTINUATION_ARTIFACT.json').read_text())
first=[r for r in ledger if r['first_common']]
later=[r for r in ledger if r['period'].startswith('oct')]
bycontract=defaultdict(list)
for r in ledger:bycontract[r['contract']].append(r)
overlap={}
for name,rows in [('all_landmarks',ledger),('all_first_common',first),('diagnostic_first_common',[r for r in later if r['first_common']])]:
    cc=Counter(r['contract'] for r in rows if r['entry'])
    # All entry observation windows are followed to the same contract end for
    # descriptive durations. Pair counts describe dependent windows, not trades.
    overlap[name]=dict(entered_windows=sum(cc.values()),overlapping_window_pairs=sum(n*(n-1)//2 for n in cc.values()),
                      contracts_with_multiple_entered_windows=sum(n>1 for n in cc.values()))
class_counts={}
for period in results['periods']:
    rr=[r for r in ledger if r['period']==period and r['features'] is not None]
    class_counts[period]={side:{str(y):dict(landmarks=sum(r['y']==y and r['side']==side for r in rr),
        contracts=len({r['contract'] for r in rr if r['side']==side and r['y']==y})) for y in (0,1,None)} for side in ('UP','DOWN')}
old=[]
for period in results['periods']:
    old+=json.loads((ROOT/('audit/early_rebuild_20261012/evaluation/'+period+'.json')).read_text())['setups']
byid={r['setup']['id']:r for r in old}
joint=[]
for r in first:
    o=byid[r['setup_id']];h=o.get('hypothetical_after_cost')
    joint.append(dict(contract=r['contract'],side=r['side'],period=r['period'],durable_y=r['y'],durable_status=r['status'],
        managed_status=o['status'],managed_net_cents=h['net_cents'] if h else None))
def econ(rows):
    complete=[r for r in rows if r['managed_net_cents'] is not None]
    return dict(attempts=len(rows),status=dict(Counter(r['managed_status'] for r in rows)),complete=len(complete),
        mean_net_cents=statistics.mean(r['managed_net_cents'] for r in complete) if complete else None,
        positive=sum(r['managed_net_cents']>0 for r in complete))
def contract_bounds(rows):
    cc=defaultdict(list)
    for r in rows:cc[r['contract']].append(r)
    return dict(contracts=len(cc),has_success=sum(any(r['y']==1 for r in v) for v in cc.values()),
        no_success_but_unknown=sum(not any(r['y']==1 for r in v) and any(r['y'] is None for r in v) for v in cc.values()))
supported=[r for r in later if r['score']['probability'] is not None]
output=dict(class_counts=class_counts,overlapping_observation_windows=overlap,
    probability_range=[min(r['score']['probability'] for r in supported),max(r['score']['probability'] for r in supported)],
    diagnostic_supported_outcomes=dict(Counter(str(r['y']) for r in supported)),
    all_first_managed=econ(joint),diagnostic_first_managed=econ([r for r in joint if r['period'].startswith('oct')]),
    durable_success_managed=econ([r for r in joint if r['durable_y']==1]),
    diagnostic_durable_success_managed=econ([r for r in joint if r['period'].startswith('oct') and r['durable_y']==1]),
    all_first_contract_outcomes=contract_bounds(first),diagnostic_first_contract_outcomes=contract_bounds([r for r in later if r['first_common']]),
    calibration_feature_missing_successes=[{k:r[k] for k in ('contract','side','decision_time','feature_error')} for r in ledger if r['period']=='sep28_29_diagnostic' and r['y']==1 and r['features'] is None],
    diagnostic_successes=[{k:r[k] for k in ('contract','side','decision_time','feature_error','first_common')} for r in later if r['y']==1],
    all_first_burst_observed=sum(r['burst_observed'] for r in first),diagnostic_first_burst_observed=sum(r['burst_observed'] for r in later if r['first_common']))
(OUT/'HANDOFF_METRICS.json').write_text(json.dumps(output,indent=2,sort_keys=True)+'\n')
(OUT/'MATCHED_OPPORTUNITY_AND_MANAGEMENT.json').write_text(json.dumps(joint,indent=2,sort_keys=True)+'\n')
print(json.dumps(output,indent=2))
