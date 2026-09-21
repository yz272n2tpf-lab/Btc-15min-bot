#!/usr/bin/env python3
"""Independent checks of reported entries against raw quote rows and official results."""
import hashlib,json,math
from pathlib import Path
import pandas as pd
from prepare import ROOT,HERE,CUTOFF,close_time,SOURCES,inventory

def main():
    inventory()  # Verifies bytes against immutable input Git commit.
    calls=pd.read_csv(HERE/'per_call.csv')
    labels=pd.read_csv(HERE/'labels.csv').set_index('contract')
    assert not calls.duplicated(['cohort','policy','contract']).any()
    assert calls.official_side.equals(calls.contract.map(labels.official_side))
    assert calls.ask.between(.0000001,.50).all()
    assert calls.contract.map(close_time).max()<CUTOFF
    sources={n:pd.read_csv(ROOT/n,low_memory=False) for n in [SOURCES[0],SOURCES[2],SOURCES[7]]}
    for r in calls.itertuples():
        row=sources[r.source].iloc[int(r.source_row)-2]
        if r.source==SOURCES[0]:quote=row['yes_ask' if r.side=='UP' else 'no_ask']
        elif r.source==SOURCES[2]:quote=row['up_ask' if r.side=='UP' else 'down_ask']
        else:
            assert row.side==r.side;quote=row.side_ask
        assert abs(quote-r.ask)<1e-12
        assert abs(r.target-r.official_target)<.01
    results=json.loads((HERE/'results.json').read_text())
    metrics=pd.read_csv(HERE/'metrics.csv')
    for r in metrics.itertuples():
        q=calls[(calls.cohort==r.cohort)&(calls.policy==r.name)]
        assert len(q)==r.calls
        assert int((q.side==q.official_side).sum())==r.correct
        assert abs(len(q)/r.denominator-r.coverage)<1e-12
    # Oracle counts rederived directly from the three input quote tables.
    membership=pd.read_csv(HERE/'membership.csv')
    for cohort in results:
        ids=set(membership.loc[membership.cohort==cohort,'contract'])
        for minimum in [2,4]:
            winning=set();affordable=set()
            for name,df in sources.items():
                if (name==SOURCES[0])!=(cohort=='august_replay'):continue
                for row in df.to_dict('records'):
                    t=row.get('ticker',row.get('contract'))
                    if t not in ids:continue
                    remaining=row.get('remaining',row.get('minutes_left',row.get('seconds_left',0)/60))
                    if not minimum<=remaining<=10:continue
                    if name==SOURCES[0]:quotes=[('UP',row['yes_ask']),('DOWN',row['no_ask'])]
                    elif name==SOURCES[2]:quotes=[('UP',row['up_ask']),('DOWN',row['down_ask'])]
                    else:quotes=[(row['side'],row['side_ask'])]
                    for side,ask in quotes:
                        if 0<ask<=.5:
                            affordable.add(t)
                            if side==labels.loc[t,'official_side']:winning.add(t)
            ref=results[cohort]['oracle'][str(minimum)]
            assert len(winning)==ref['winner_affordable_contracts']
            assert len(affordable)==ref['any_affordable_contracts']
            assert min(len(affordable),math.floor(len(winning)/.93))==ref['max_calls_at_93pct_accuracy']
    features=pd.read_csv(HERE/'features.csv.gz',low_memory=False).merge(labels.reset_index(),on='contract',validate='many_to_one')
    missing_target=features.target.isna()
    # Two side rows of one zero-gap August snapshot yield 0/0 when deriving
    # target from gap/percentage. They cannot qualify T1 or A; keep missing.
    assert ((features.loc[~missing_target,'target']-features.loc[~missing_target,'official_target']).abs()<=.01).all()
    assert ((features.loc[missing_target,'cohort']=='august_replay')&(features.loc[missing_target,'gap']==0)).all()
    assert json.loads((HERE/'label_conflicts.json').read_text())==[]
    a=calls[(calls.cohort=='august_replay')&(calls.policy=='family_T1')]
    early=a[a.remaining.between(7,10)]
    assert len(early)==14 and int((early.side==early.official_side).sum())==13
    output={'status':'PASS','per_policy_entry_records_checked':len(calls),'distinct_entry_rows_checked':calls.row_id.nunique(),
       'official_labels':len(labels),'label_conflicts':0,'fixed_target_mismatch_rows':0,
       'zero_gap_rows_with_unrecoverable_derived_target':int(missing_target.sum()),
       'source_bytes_match_pinned_commit':True,'tier1_august_calls':len(a),'tier1_august_correct':int((a.side==a.official_side).sum()),
       'tier1_august_7to10_calls':len(early),'tier1_august_7to10_correct':int((early.side==early.official_side).sum()),
       'oracle_independently_recomputed':True,'no_post_cutoff_contracts':True,
       'signal_only':True,'orders':False,'production_imports':False,'no_service_access_or_mutation':True}
    (HERE/'verification.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))

if __name__=='__main__':main()
