"""Execute exact candidate functions on recovered inputs, with explicit scope.

Full native EARLY replay, bounded-clock FINAL predicate replay, and conditional
SCALP management replay are separate. Never manufacture native frame identity,
forecast/profile evidence, a BUY, a fill, or continuous quotes across an outage.
"""
from copy import deepcopy
from datetime import datetime
import hashlib,json,subprocess
from collections import Counter
from pathlib import Path
from candidates.early_opportunity_20261011.lifecycle import Candidate
from candidates.early_opportunity_20261011.qualification import EvidenceRegistry
from btc15_v2_product.directional import protected_frame,qualify
from btc15_v2_product.early_entry import ARTIFACT,WEIGHTS
from btc15_v2_product.scalp import POLICY
from btc15_v2_product.scalp_policy import Lifecycle
from btc15_v2_product.scalp_economics import entry_assessment
from btc15_v81_qualified_inputs_v1 import require_qualified
from audit.existing_evidence_20261011.evaluate import epoch,VARIANTS,distance,stats

BASE='702a8906a5fce0b18d0ff0efd8a5fcfed772b757'
SCALP_LIVE='6e04aced0f718b29f8ed805abcc0f76b01ed5096'

def final_predicates_from_recorded_inputs(state,frame,received):
    """Actual candidate predicates at both ends of the unknown capture interval.

    Not qualify(): original MAIN quote/BRTI/native receipts are not fabricated.
    Equal endpoint gates establish only the predicate decision on these inputs.
    """
    m=state['market'];g=state['final'];cut=epoch(frame['decision_utc'])
    closed=cut+frame['features']['remaining']*60
    # A source frame's own elapsed+remaining encodes the recorded contract window.
    f=dict(contract=frame['ticker'],official_close=closed,captured_ts=cut,
        btc_price=frame['btc_price'],target=frame['target'],brti={'value':m['brti_value']},
        fair=dict(side=g['side'],ask=m[g['side'].lower()+'_ask'],fair=g['confidence'],
            edge=g['confidence']-m[g['side'].lower()+'_ask'],dist_over_range5=frame['features']['dist_over_range5']),
        **{k:m[k]for k in ['up_bid','up_ask','down_bid','down_ask']})
    first=protected_frame(f,cut)[0]['final']['conditions']
    f['captured_ts']=received;last=protected_frame(f,received)[0]['final']['conditions']
    return first if first==last else None,closed-cut

def main(w):
    root=w/'repo';out=root/'audit/existing_evidence_20261011';result={}
    files=['candidates/early_opportunity_20261011/qualification.py','candidates/early_opportunity_20261011/lifecycle.py',
        'btc15_v2_product/directional.py','btc15_v2_product/early_entry.py','btc15_v2_product/early_management.py',
        'btc15_v2_product/scalp.py','btc15_v2_product/scalp_policy.py','btc15_v2_product/scalp_economics.py',
        'btc15_v81_qualified_inputs_v1.py','audit/opportunity_integrity_20261011/final_distance_study.py']
    identities=[]
    for p in files:
        body=(root/p).read_bytes();base=subprocess.check_output(['git','show',BASE+':'+p],cwd=root)
        assert body==base
        row=dict(file=p,base_commit=BASE,sha256=hashlib.sha256(body).hexdigest())
        if '/scalp' in p:
            other=subprocess.check_output(['git','show',SCALP_LIVE+':'+p],cwd=root)
            row.update(independent_deployed_commit=SCALP_LIVE,independent_sha256=hashlib.sha256(other).hexdigest(),identical=other==body)
        identities.append(row)
    result['identities']=dict(files=identities,early_policy='OFFLINE_EARLY_OPPORTUNITY_INTEGRITY_V1',reviewed_profiles=len(EvidenceRegistry().profiles),
        scalp_branch_entry='SCALP_NET_EVIDENCE_V1',scalp_independent_entry='SCALP_MOMENTUM_COST_ROOM_V3',
        scalp_management=dict(policy=POLICY.name if hasattr(POLICY,'name')else str(POLICY),arm=POLICY.arm,giveback=POLICY.giveback,horizon=POLICY.horizon),
        final=dict(confidence=.90,distance_6_to8_minutes=75,distance_last6_minutes=50,distance_over_range5=1,brti_side_gap_exclusive=11),
        signal_only=True,orders=False,warning='702 is an EARLY candidate branch, not a synchronized MAIN/independent-SCALP deployment bundle. Its SCALP entry implementation differs from live 6e04aced.')

    # One authentic preserved October11 native origin frame. Selected-origin
    # evidence is not an all-decisions sample and cannot estimate missed entries.
    original_capture=w/'evidence/main_ladders.json'
    if original_capture.exists():
        capture=json.loads(original_capture.read_text());o=capture['origin']
    else:
        o=json.loads((out/'early_native_replay_frame.json').read_text())['recorded_origin']
    f=o['entry_provenance']
    at=epoch(o['signal_timestamp_utc']);expiry=qualify(f,at)
    candidate=Candidate();decision=candidate.process(deepcopy(f),at)
    assert decision['opportunity']['reasons']==['VALIDATED_OPPORTUNITY_EVIDENCE_REQUIRED']
    result['early_native_replay']=dict(records=1,contracts=1,source='preserved Phase B main_ladders.json origin.entry_provenance',
        contract=o['contract'],original_origin_id=o['origin_id'],original_ask=o['original_ask'],decision_at=at,source_expiry=expiry,
        new_buys=int(decision['event']=='BUY'),recorded_baseline_buy=True,result=decision,
        role='SELECTED_ORIGIN_SINGLE_FULL_NATIVE_REPLAY_NOT_FULL_COHORT',
        cannot_validate=['candidate profit quality','candidate multi-minute positive opportunities','candidate warning/EXIT timing','candidate independent re-entry frequency','missed attractive entries'])
    (out/'early_native_replay_frame.json').write_text(json.dumps(dict(frame=f,decision_ts=at,origin_id=o['origin_id'],recorded_origin=o),indent=2))

    # Actual current FINAL predicate code, not a hand-reimplemented baseline.
    frames=[json.loads(l)for l in(w/'recovered-feature-frames/pr36_frames.jsonl').open()]
    assert all(r['artifact_sha256']==ARTIFACT and r['weights_sha256']==WEIGHTS for r in frames)
    index={(r['ticker'],epoch(r['decision_utc'])):r for r in frames};seen={};ambiguous=0;conflicted=set()
    for line in(w/'recovered-common/pr36/records.jsonl').open():
        event=json.loads(line)
        for source in event.get('sources',[]):
            if source['service']!='main' or 'state'not in source:continue
            s=source['state'];key=(s.get('contract'),epoch(s['source_timestamp_utc']));frame=index.get(key)
            if frame is None:continue
            if not all(s['health'].get(k)is True for k in ['source_fresh','brti_fresh','paired_quotes','market_open']):continue
            assert frame['target']==s['market']['target'] and frame['btc_price']==s['market']['btc_price']
            received=epoch(source['response_received_utc'])
            gates,left=final_predicates_from_recorded_inputs(s,frame,received)
            if gates is None:ambiguous+=1;continue
            row=dict(contract=key[0],time=key[1],left=left,side=s['final']['side'],p=s['final']['confidence'],
                gap=frame['btc_price']-frame['target'],gates=gates)
            if key in seen and seen[key]!=row:conflicted.add(key)
            seen.setdefault(key,row)
    labels={r['contract']:r['official_side']for r in json.loads((out/'final_forward_state.json').read_text())['live']['settled_records']}
    chosen={v:{}for v in VARIANTS}
    for key,row in sorted(seen.items(),key=lambda kv:kv[1]['time']):
        if key in conflicted:continue
        for variant in VARIANTS:
            gates=dict(row['gates'],gap_ok=abs(row['gap'])>=distance(variant,row['left']))
            if all(gates.values()):chosen[variant].setdefault(row['contract'],dict(row,correct=row['side']==labels[row['contract']]if row['contract']in labels else None))
    result['final_candidate_predicate_replay']=dict(feature_bound_records=len(seen)-len(conflicted),contracts=len({r['contract']for k,r in seen.items()if k not in conflicted}),
        capture_interval_ambiguous_publications=ambiguous,conflicting_feature_keys=len(conflicted),
        table={v:dict(**stats(list(rs.values())),records=list(rs.values()))for v,rs in chosen.items()},
        role='ACTUAL_CANDIDATE_PREDICATE_REPLAY_WITH_CAPTURE_TIME_BRACKET_NOT_FULL_NATIVE_AUTHORITY_REPLAY',
        full_native_qualification=False,settlement_aware_scored=False,
        missing=['original MAIN quote consumption receipt/sequence','full native BRTI receipt binding','independently reviewed settlement-path model'],
        current_model_hashes_bound=True,no_model_refit=True)

    # Run 702's exact SCALP admission economics on sufficient recorded entry
    # inputs. This does not need an invented current BTC price or BTC30 history.
    selected=json.loads((out/'incident_selected_publications.json').read_text());origin=selected['entry']['state']['origin'];p=origin['entry_provenance'];q=p['quote']
    row=dict(q,ticker=p['ticker'],target=p['target'],brti=p['brti']['value'],input_provenance=p,ts=origin['decision_ts'])
    require_qualified(row,origin['decision_ts'])
    assessment=entry_assessment(row,origin['side'],origin['fee_schedule'])
    assert not assessment['ready']
    result['scalp_candidate_entry_replay']=dict(records=1,contracts=1,role='ACTUAL_702_ENTRY_ASSESSMENT_COMPONENT_REPLAY',
        result=assessment,independent_live_baseline_issued=True,full_processor_replay=False,
        reason='Original current BTC value/full decision row absent; no price is manufactured from later MAIN observations. Bundled 702 entry policy rejects even this recorded 60c case.')

    # Conditional new lifecycle replay: seed the authentic historical BUY;
    # expressly NOT a BUY generated by 702, whose admission rejected it above.
    engine=Lifecycle(POLICY,origin['contract'],origin['side'],origin['original_ask'],origin['signal_ts'],origin['signal_ts'],origin['close_ts'])
    path=[];used=set();outages=0;first_protect=None;first_exit=None
    for line in(w/'recovered-common/incident/records.jsonl').open():
        event=json.loads(line)
        for source in event['sources']:
            if source['service']!='v81':continue
            s=source.get('state',{});o=s.get('origin')or{}
            if o.get('origin_id')!=origin['origin_id']or s.get('published_ts',0)<=origin['signal_ts']:continue
            at=s['published_ts']
            if at in used:continue
            used.add(at)
            if s.get('status')=='UNAVAILABLE':
                outages+=1;answer=engine.update(dict(observed_ts=at,ticker=origin['contract'],quote_validated_at_observation=False))
            else:
                p=s['input_provenance'];q=p['quote'];row=dict(q,ticker=p['ticker'],target=p['target'],brti=p['brti']['value'],input_provenance=p)
                require_qualified(row,at)
                answer=engine.update(dict(observed_ts=at,ticker=p['ticker'],brti_source_ts=p['brti']['source_ts_ms']/1000,
                    quote_validated_at_observation=True,up_bid=q['up_bid']))
            path.append(dict(at=at,result=answer,status_recorded=s.get('guidance'),bid=s.get('executable_current_bid')))
            if answer['status']=='PROTECT'and first_protect is None:first_protect=at
            if answer['status']=='EXIT'and first_exit is None:first_exit=at
    result['scalp_conditional_management_replay']=dict(observations=len(path),outages=outages,first_protect=first_protect,first_exit=first_exit,
        matches_recorded_protect=first_protect==selected['first_protect']['state']['published_ts'],
        matches_recorded_exit=first_exit==selected['exit79']['state']['published_ts'],
        full_path=False,new_candidate_buy=False,role='ACTUAL_CANDIDATE_LIFECYCLE_CONDITIONAL_ON_RECORDED_BASELINE_ORIGIN',path=path)
    (out/'candidate_replay_results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:{a:b for a,b in v.items()if a not in ['result','table','files','path']}for k,v in result.items()},indent=2))

if __name__=='__main__':
    import sys
    main(Path(sys.argv[1]))
