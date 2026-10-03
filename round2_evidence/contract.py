"""One producer map and schema. Absent producers remain explicitly unavailable."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
FIELDS=[]
def group(lane,producer,prefix,names,status='PRESENT_IF_EMITTED',needed=None):
    for name in names.split():
        FIELDS.append(dict(field=lane.lower()+'.'+name,lane=lane,producer=producer,
            source_path=prefix+name if prefix is not None else None,
            producer_state=status,required_for=needed or lane,
            missing='UNAVAILABLE; never backfill, infer a witness, or substitute another lane'))

group('SHARED','COMMON_OBSERVER','', 'schema_version record_type run_id observer_epoch sequence_in_process recorded_utc sampling_seconds sources')
group('SHARED','PROTECTED_MAIN','', 'display_build source_timestamp_utc generated_utc contract timer market health parity safety')
group('SHARED','PROTECTED_MAIN','market.','target up_bid up_ask down_bid down_ask brti_ready brti_age_seconds')
group('SHARED','PROTECTED_MAIN','timer.','close_utc close_basis seconds_left')
group('SHARED','PROTECTED_MAIN','health.','brti_fresh source_fresh market_open paired_quotes')
group('SHARED','PROTECTED_MAIN','parity.','timestamp_utc status api_contract')
group('SHARED','COMMON_MAIN_RECEIPT','', 'request_started_utc response_received_utc http_status error_type')
group('SHARED','BRTI_OWNER','', 'owner_state')
group('SHARED','INDEPENDENT_ACQUIRER',None,'original_member_bytes member_sha256 stream_id offset end_offset run_manifest_bytes run_manifest_sha256 collector_commit collector_fingerprints signer_id authenticated_route peer_identity redirect_policy', 'MISSING_LIVE_PRODUCER')
group('SHARED','NATIVE_V2_WITNESSES',None,'source_build run_build native_epoch native_decision_id model_hash policy_hash quote_id book_sequence quote_payload_sha256 quote_source_utc quote_received_utc quote_validated_utc quote_consumed_utc up_bid_size up_ask_size down_bid_size down_ask_size quote_decimal_units brti_witness btc_witness quote_witness native_cutoff_utc native_consumption_completed_utc native_publication_completed_utc official_open_utc official_close_utc official_window_witness official_target_witness', 'MISSING_LIVE_PRODUCER')
group('SHARED','CLOCK_MONITOR',None,'clock_id clock_epoch measurement_id reference_utc valid_from_utc valid_until_utc error_us rate_ppm read_error_us step_status suspension_status restart_status monitor_attestation revocation_state paired_utc_boottime', 'MISSING_LIVE_PRODUCER')
group('SHARED','EXPOSURE_REVALIDATOR',None,'admission_result admission_predicate_intervals consumed_utc current_check_utc exposure_recheck_utc guidance_expiry completed_delivery_witness', 'MISSING_LIVE_PRODUCER')
group('SHARED','POPULATION_CATALOG',None,'eligible_contract_manifest scheduled_contract quiet_contract capture_start capture_end restart_reason gap_reason quote_reconnect authoritative_settlement final60_complete final60_count final60_average final60_side settlement_artifact_ref', 'MISSING_ROUND2_FEED')
group('SHARED','INDEPENDENT_ACQUIRER',None,'capture_run_id producer_instance_id producer_epoch service_id deployment_id git_commit source_module_hashes model_artifact_hash training_dataset_hash training_cutoff_utc policy_constants official_contract_universe_manifest_hash partition_manifest_hash run_started_utc run_stopped_utc capture_start_reason capture_end_reason', 'MISSING_LIVE_RUN_MANIFEST')
group('SHARED','NATIVE_V2_WITNESSES',None,'side_mapping quote_source quote_validation_result quote_status quote_rejection_reason quote_source_contract_ticker target_source_id target_payload_sha256 expected_quote_cadence quote_heartbeat quote_last_good quote_gap_intervals source_sequence_continuity original_quote_decimal_payload model_evaluation_id feature_validity_masks source_ids source_history_cutoff', 'MISSING_LIVE_PRODUCER')
group('SHARED','CLOCK_MONITOR',None,'clock_domain certificate_sha256 clock_basis reference_identity monitor_runtime_epoch offset_bound_evidence rate_bound_evidence read_bound_evidence epoch_continuity_evidence', 'MISSING_LIVE_PRODUCER')
group('SHARED','INDEPENDENT_ACQUIRER',None,'acquisition_manifest reader_authorization endpoint source_service_identity', 'MISSING_LIVE_PRODUCER')
group('SHARED','EXPOSURE_REVALIDATOR',None,'admission_reason duplicate_conflict_replay_rollover_outage', 'MISSING_LIVE_PRODUCER')
group('SHARED','NATIVE_V2_WITNESSES',None,'native_published_utc native_decision_utc quote_consumption_completed_utc brti_consumption_completed_utc btc_consumption_completed_utc', 'MISSING_LIVE_PRODUCER')
group('EARLY','PROTECTED_MAIN','early.','source ready side fair edge ask bid conditions')
group('EARLY','PROTECTED_MAIN','', 'early')
group('EARLY','NATIVE_EARLY_GATE_STREAM',None,'candidate_id candidate_evaluation_id all_gate_results rejection_reasons suppression_reasons probability_threshold price_gate persistence_gate time_gate btc_target_context trajectory_history history_cutoff brti_selected_evidence model_feature_context emitted_tradingview_context emitted_seconds_context emitted_native_range_context', 'MISSING_LIVE_PRODUCER')
group('EARLY','DIRECTIONAL_AUTHORITY_LEDGER',None,'origin_id manager_signal_id original_side signal_timestamp_utc accepted_utc original_ask original_bid protected_snapshot_key protected_content_sha256 origin_record origin_kind protocol_sha256', 'OFFLINE_ONLY_NOT_NATIVE')
group('FINAL','PROTECTED_MAIN','', 'final')
group('EARLY','DIRECTIONAL_AUTHORITY_LEDGER',None,'research_origin_id origin_observation_timestamp origin_available_timestamp original_member_reference signal_runtime_epoch signal_build protected_source_timestamp_utc protected_generated_utc observer_received_utc', 'OFFLINE_ONLY_NOT_NATIVE')
group('FINAL','PROTECTED_MAIN','final.','source ready side confidence conditions recorded_final_call recorded_side recorded_confidence')
group('FINAL','FINAL_LINKED_EVENT_PRODUCER',None,'final_event_id final_publication_id evidence_inputs generated_identity publication_identity immutable_early_origin_id link_basis previous_state current_state saw_strong_final trigger_branch valid_opposing_not_ready qualified_opposing_confirmation', 'MISSING_EXPLICIT_LIVE_LINK')
group('FINAL','INFORMATION_READ_ONLY',None,'five_minute_caution three_minute_guard flip_risk phase_source phase_build phase_generated_utc phase_contract_binding', 'NOT_IN_THIS_COMMON_SOURCE; NO_NEW_GET')
group('FINAL','FINAL_LINKED_EVENT_PRODUCER',None,'record_id sequence status reason guidance event final_confirmation protected_evidence publication_completed_utc', 'MISSING_EXPLICIT_LIVE_LINK')
group('FINAL','INFORMATION_READ_ONLY',None,'published_phase_label phase_publication_utc phase_origin_id flip_risk_definition flip_risk_producer flip_risk_version flip_risk_source_utc flip_risk_publication_utc flip_risk_availability', 'NOT_IN_THIS_COMMON_SOURCE; NO_NEW_GET')
group('SCALP','V81_PUBLICATION','', 'v81_state')
group('SCALP','SERIAL_PUBLICATION','', 'serial_state')
group('SCALP','SCALP_ORIGIN_EVENT_STREAM',None,'signal_id event_id event_sequence origin_hash contract_ticker exchange_market_id side signal_generated_utc signal_published_utc signal_received_utc published_entry_decimal original_market_ask_decimal original_market_bid_decimal original_quote_id first_post_publication_quote_id first_post_receipt_quote_id first_quote_received_utc first_quote_ask_decimal first_quote_bid_decimal entry_admission_result entry_rejection_reason policy_id model_hash feature_snapshot_id feature_payload_sha256 feature_availability_cutoff_utc probability strength seconds_left elapsed_contract_seconds btc30_aligned origin_gate_results', 'MISSING_COMPLETE_LIVE_EVENT_STREAM')
group('SCALP','SCALP_LIFECYCLE_EVENT_STREAM',None,'lifecycle_event_id signal_origin_id prior_state next_state transition_kind trigger_reason trigger_quote_id trigger_evidence_ids evaluated_utc published_utc received_utc current_same_side_bid_decimal gross_unrealized_c_decimal peak_bid_so_far_decimal peak_gain_so_far_c_decimal peak_quote_id armed arm_threshold_c arm_event_id arm_quote_id arm_utc arm_observed_gain_c floor_c trail_c giveback_c target_c stop_c exit_bid_decimal exit_guidance_event_id shadow_exit_id retirement_reason unavailable_reason origin_retained brti_protection_evaluations brti_readiness brti_side brti_agreement brti_witness_ref', 'MISSING_COMPLETE_LIVE_EVENT_STREAM')
group('SCALP','SCALP_SERIAL_OWNER_STREAM',None,'serial_index prior_signal_id prior_origin_side lane_label prior_terminal_event_id prior_terminal_kind prior_terminal_utc elapsed_since_prior_origin_sec elapsed_since_prior_terminal_sec active_origin_ids_at_decision overlap_allowed_by_policy reentry_gate_result suppression_reason source_candidate_id source_candidate_hash never_armed armed_no_exit unqualified_entry', 'MISSING_COMPLETE_LIVE_EVENT_STREAM')

group('SCALP','SCALP_LIFECYCLE_EVENT_STREAM',None,'lifecycle_policy_hash remaining_seconds transition_sequence protection_missing_reason evidence_role user_guidance horizon_end_reason path_completeness', 'MISSING_COMPLETE_LIVE_EVENT_STREAM')

PRODUCERS={
 'COMMON_OBSERVER':dict(component='btc15_common_observer_v1.observe_forever',service='scalp-finalprod-clean-v1',basis='Already-produced original gzip member; no new observation',identity='e98576f23e247349b90717aea3a3ad832d409354 reference; actual run/build must be bound'),
 'COMMON_MAIN_RECEIPT':dict(component='btc15_common_observer_v1.read_source(main)',basis='Collector clocks only, never native receipt'),
 'PROTECTED_MAIN':dict(component='existing dashboard_state.json protected early/final objects',source='sources[service=main].state',basis='Complete parsed response only; startup _two_final_* forbidden',identity='qualified lineage abe212b513827c8cec28a2f64e0161e79296bd82; per-response witness unavailable'),
 'BRTI_OWNER':dict(component='existing sources[service=owner].state',basis='Separate owner observation; cannot repair main cutoff or freshen main evidence'),
 'V81_PUBLICATION':dict(component='existing sources[service=v81].state',basis='Whole original state retained; not a complete per-event lifecycle log'),
 'SERIAL_PUBLICATION':dict(component='existing sources[service=serial].state',basis='Whole original state retained; not equivalent to actual user EXIT'),
 'INDEPENDENT_ACQUIRER':dict(component='b025771 Policy/seal_member contract',basis='API exists; real continuously detached materializer NOT ESTABLISHED'),
 'NATIVE_V2_WITNESSES':dict(component='BTC15_SOURCE_WITNESSES_V2 / BTC15_NATIVE_CONTEXT_V2',basis='Offline contracts only. No producer callback added; missing per-source/decision/publication evidence remains null'),
 'CLOCK_MONITOR':dict(component='trusted per-domain host/NTS clock monitor',basis='Not present. Certificate receiver is not a monitor or an attestation'),
 'EXPOSURE_REVALIDATOR':dict(component='b025771 Admission.view plus future delivery seam',basis='Offline guard exists; genuine delivery seam/witness not established'),
 'POPULATION_CATALOG':dict(component='official Kalshi contract catalog and complete authoritative settlement/closeout stream',basis='Existing metadata/scorer can describe contracts, but no independent complete Round2 catalog/settlement feed is wired'),
 'NATIVE_EARLY_GATE_STREAM':dict(component='native EARLY evaluation at original cutoff',basis='Protected conditions retained when emitted; all rejected/suppressed candidate events and all gate inputs are not emitted as a complete stream'),
 'DIRECTIONAL_AUTHORITY_LEDGER':dict(component='btc15_directional_signal_authority_v1.Authority origins/records',basis='dcc44cc offline candidate only; recorder cannot call authority to manufacture actual BUY origins'),
 'FINAL_LINKED_EVENT_PRODUCER':dict(component='existing authority record with explicit origin and protected identity',basis='Offline origin/event relation can be preserved. No matching live authority stream established'),
 'INFORMATION_READ_ONLY':dict(component='abe212 information output; informational only',basis='Common observer URL set does not include /information. Do not derive phase/risk or add GET'),
 'SCALP_ORIGIN_EVENT_STREAM':dict(component='true-SCALP _maybe_true_scalp_signal; V8.1 owner entry event',basis='Partial native summary/state exists; full immutable published-entry/first-quote provenance stream unavailable'),
 'SCALP_LIFECYCLE_EVENT_STREAM':dict(component='_update_true_scalp_pending / _update_profit_shadow / V8.1 owner transitions',basis='Native shadow exits differ from guidance. No continuous complete event and BRTI evaluation stream established'),
 'SCALP_SERIAL_OWNER_STREAM':dict(component='serial owner and source candidate transitions',basis='Requires actual predecessor/terminal links, suppression and unresolved-origin denominator; not reconstructed from counters')}

CELL={'type':'object','additionalProperties':False,'required':['status','value','producer','source_path','reason'],
 'properties':{'status':{'enum':['OBSERVED','UNAVAILABLE']},'value':{},'producer':{'type':'string'},'source_path':{'type':['string','null']},'reason':{'type':['string','null']}},
 'allOf':[{'if':{'properties':{'status':{'const':'UNAVAILABLE'}}},'then':{'properties':{'value':{'type':'null'},'reason':{'type':'string','minLength':1}}}},
          {'if':{'properties':{'status':{'const':'OBSERVED'}}},'then':{'properties':{'reason':{'type':'null'},'value':{'not':{'type':'null'}}}}}]}
SCHEMA={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:btc15:round2:unified:1','title':'BTC15_ROUND2_EVIDENCE_V1',
 'type':'object','additionalProperties':False,'required':['schema','record_id','mode','guidance','orders_enabled','coverage','source_dispositions','fields'],
 'properties':{'schema':{'const':'BTC15_ROUND2_EVIDENCE_V1'},'record_id':{'type':'string','minLength':1},'mode':{'const':'EVIDENCE_ONLY'},'guidance':{'type':'null'},'orders_enabled':{'const':False},
 'coverage':{'enum':['UNAVAILABLE_INCOMPLETE_PRODUCERS','SOURCE_ERROR_OR_WAIT']},'source_dispositions':{'type':'array'},'fields':{'type':'object','additionalProperties':False,'required':[r['field'] for r in FIELDS],'properties':{r['field']:CELL for r in FIELDS}}}}

from copy import deepcopy
for spec in FIELDS:
    cell=deepcopy(CELL)
    cell['properties']['producer']={'const':spec['producer']}
    cell['properties']['source_path']={'const':spec['source_path']}
    if spec['source_path'] is None:cell['properties']['status']={'const':'UNAVAILABLE'}
    SCHEMA['properties']['fields']['properties'][spec['field']]=cell

def export():
    (ROOT/'schema.json').write_text(json.dumps(SCHEMA,indent=2)+'\n')
    (ROOT/'producer_map.json').write_text(json.dumps(dict(producers=PRODUCERS,fields=FIELDS),indent=2)+'\n')
    import csv
    with (ROOT/'producer_map.csv').open('w',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(FIELDS[0]),lineterminator="\n");w.writeheader();w.writerows(FIELDS)
if __name__=='__main__':export()
