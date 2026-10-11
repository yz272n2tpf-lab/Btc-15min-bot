"""Final acceptance orchestration. Does not fit or change any rule/profile."""
from collections import Counter
from pathlib import Path
import argparse, hashlib, json
from .study import common, cohort, load_data, save_data, replay, stats, score_episode, write_json
from candidates.three_ladder_20261011.profile_study import ts, evaluate


def run(root, raw, diagnostic):
    out=root/'audit/early_condition_20261011'
    frozen=json.loads((out/'PRE_ACCEPTANCE_FREEZE.json').read_text())
    for p,h in frozen['files'].items():
        if hashlib.sha256((root/p).read_bytes()).hexdigest()!=h:raise RuntimeError('FROZEN_FILE_CHANGED: '+p)
    profile=json.loads((out/'profile_DISABLED.json').read_text())
    prior=json.loads((root/'audit/three_ladder_readiness_20261011/research_profile_DISABLED.json').read_text())
    data,quality=common(raw,ts('2026-10-06T00:00:00Z'),ts('2026-10-06T06:00:00Z'))
    diag,dq=common(diagnostic,ts('2026-10-04T00:00:00Z'),ts('2026-10-04T04:00:00Z'))
    used=set(prior['development_contracts']+prior['calibration_contracts'])|set(diag)
    assert not used.intersection(data)
    datahash=save_data(out/'acceptance_inputs.json.gz',data)
    diaghash=save_data(out/'diagnostic_inputs.json.gz',diag)
    results={}
    for name,frames in [('acceptance',data),('diagnostic_opened_holdout',diag),('development',load_data(out/'development_inputs.json.gz')),('calibration',load_data(out/'calibration_inputs.json.gz'))]:
        proposal=replay(frames,proposal=True)
        admitted=replay(frames,profile=profile)
        summary=stats(proposal)
        summary['input_contracts']=len(frames);summary['input_observations']=sum(map(len,frames.values()))
        # Evaluate sensitivity on the SAME fixed episodes/condition triggers.
        sensitivity={}
        for delay in (5,10,20):
            scored=[score_episode(e,frames[e['origin']['contract']],delay)for e in proposal['episodes']]
            sensitivity[str(delay)]=stats(dict(proposal,episodes=scored))
        complete=[e for e in proposal['episodes']if e['scenario']and not e['censor']]
        admitted_ids={e['origin']['id']for e in admitted['episodes']}
        comparison=dict(admitted=stats(admitted),missed_positive_structural_proposals=[e['origin']['id']for e in complete if e['scenario']['net']>0 and e['origin']['id']not in admitted_ids],
            rejected_negative_or_zero_structural_proposals=sum(e['scenario']['net']<=0 and e['origin']['id']not in admitted_ids for e in complete),
            scope='This is the predeclared structural-proposal universe, NOT every possible profitable market path.',
            historical_baseline_first_ready=proposal['baseline_first_ready'],
            baseline_limitation='Observed historical readiness only; no original full native baseline lifecycle or fill record is reconstructed.')
        # Premature exit diagnostic: first available quote 30s after actual exit,
        # never search future maxima. A later better quote does not prove rules
        # should have held; this is descriptive only.
        post_exit=[]
        for e in proposal['episodes']:
            if not e['exit']or not e['scenario']:continue
            sequence=frames[e['origin']['contract']]
            later=next((r for r in sequence if r['time']>=e['exit']['time']+30),None)
            if later and later['time']<=e['exit']['time']+40 and later['healthy']:
                held=e['origin']['side'].lower();b=later[held+'_bid'];post_exit.append(dict(origin_id=e['origin']['id'],at=later['time'],bid=b,
                    higher_than_exit_quote=b>e['exit']['bid'],net_after_same_signal_ask=b-e['origin']['ask']-.04-max(later[held+'_ask']-b,.02)))
        baseline_forecast=evaluate(prior,frames)
        result=dict(summary=summary,comparison=comparison,sensitivity=sensitivity,post_exit_30s_diagnostic=post_exit,
            frozen_horizon_baseline=baseline_forecast,**proposal)
        write_json(out/(name+'_evaluation.json'),result)
        results[name]=dict(summary=summary,comparison=comparison,sensitivity={k:{v:d[v]for v in ('complete_scored','positive_net','negative_or_zero_net','mean_net_cents')}for k,d in sensitivity.items()},
            observed_later_higher_bids=sum(d['higher_than_exit_quote']for d in post_exit),post_exit_diagnostic_n=len(post_exit))
    manifest=dict(acceptance_raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),acceptance_projection_sha256=datahash,
        diagnostic_projection_sha256=diaghash,contracts=sorted(data),overlap_with_prior_used_contracts=[],normalization_quality=quality,diagnostic_quality=dq,
        native_full_chronology=False,fee_execution_scenario_only=True)
    write_json(out/'acceptance_manifest.json',manifest);write_json(out/'EVALUATION_SUMMARY.json',results)
    print(json.dumps({k:v['summary']for k,v in results.items()},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--raw',type=Path,required=True);p.add_argument('--diagnostic',type=Path,required=True);a=p.parse_args();run(a.root,a.raw,a.diagnostic)
