"""Map exact prior specification terms without inventing a native producer."""
import csv,json,re
from pathlib import Path
from .contract import FIELDS,PRODUCERS
ROOT=Path(__file__).parent
byname={r['field']:r for r in FIELDS}
bytail={}
for r in FIELDS:bytail.setdefault(r['field'].split('.',1)[1],[]).append(r['field'])
alias={
 'capture_run_id':'shared.capture_run_id','original_ask_decimal':'scalp.original_market_ask_decimal','original_bid_decimal':'scalp.original_market_bid_decimal',
 'price_unit':'shared.quote_decimal_units','ask_size':'shared.up_ask_size + shared.down_ask_size','bid_size':'shared.up_bid_size + shared.down_bid_size',
 'decision_id':'shared.native_decision_id','signal_probability':'scalp.probability','signal_strength':'scalp.strength',
 'official_window_witness_id':'shared.official_window_witness','official_target':'shared.target','bid_decimal':'shared.up_bid + shared.down_bid','ask_decimal':'shared.up_ask + shared.down_ask',
 'source_utc':'shared.quote_source_utc','received_utc':'shared.quote_received_utc','consumed_utc':'shared.quote_consumed_utc','validated_utc':'shared.quote_validated_utc',
 'source_payload_sha256':'shared.quote_payload_sha256','source_contract_ticker':'shared.quote_source_contract_ticker','rejection_reason':'shared.quote_rejection_reason',
 'next_offset':'shared.end_offset','run_manifest_original_bytes':'shared.run_manifest_bytes','collector_file_fingerprints':'shared.collector_fingerprints',
 'original_same_side_ask':'early.original_ask','original_same_side_bid':'early.original_bid','origin_observation_timestamp':'early.origin_observation_timestamp',
 'origin_available_timestamp':'early.origin_available_timestamp','authoritative_settlement_artifact_reference':'shared.settlement_artifact_ref',
 'official_open':'shared.official_open_utc','official_close':'shared.official_close_utc','epoch':'shared.clock_epoch',
 'protected_early':'early.early','protected_publication':'shared.sources','protection_origin_link_basis':'final.link_basis',
 'protected_source_timestamp_utc':'early.protected_source_timestamp_utc','protected_generated_utc':'early.protected_generated_utc',
 'publication_completed_utc':'final.publication_completed_utc','protected_content_sha256':'early.protected_content_sha256',
 'BTC15_SOURCE_WITNESSES_V2':'shared.quote_witness + shared.brti_witness + shared.btc_witness',
 'authority':'shared.quote_witness + shared.brti_witness + shared.btc_witness','owner_epoch':'shared.quote_witness + shared.brti_witness + shared.btc_witness',
 'witnessed_utc':'shared.quote_witness + shared.brti_witness + shared.btc_witness','payload_sha256':'shared.quote_witness + shared.brti_witness + shared.btc_witness',
 'contract.ticker':'shared.contract','contract.target':'shared.target','parity.contract':'shared.parity',
 'sources[].service':'shared.sources','sources[].state':'shared.sources','sources[].request_started_utc':'shared.sources','sources[].response_received_utc':'shared.sources','sources[].http_status':'shared.sources','sources[].error_type':'shared.sources',
 'final.probability':'final.confidence'
}
alias.update({'BTC15_DETACHED_COMMON_MEMBER_V1 acquisition manifest': 'shared.acquisition_manifest', 'approved source/service/endpoint identity': 'shared.source_service_identity + shared.endpoint', 'signer identity': 'shared.signer_id', 'run/epoch/sequence/member binding': 'shared.acquisition_manifest', 'independent reader authorization': 'shared.reader_authorization', 'actual peer/redirect policy evidence': 'shared.peer_identity + shared.redirect_policy', 'trusted monitor attestation and revocation state': 'shared.monitor_attestation + shared.revocation_state', 'admission decision/reasons': 'shared.admission_result + shared.admission_reason', 'predicate interval results': 'shared.admission_predicate_intervals', 'availability check time': 'shared.current_check_utc', 'display exposure recheck time': 'shared.exposure_recheck_utc', 'guidance expiry': 'shared.guidance_expiry', 'delivery completion witness if available': 'shared.completed_delivery_witness', 'duplicate/conflict/replay/rollover/outage records': 'shared.duplicate_conflict_replay_rollover_outage', 'actual published phase label': 'final.published_phase_label', 'phase producer/version': 'final.phase_source + final.phase_build', 'phase source/publication clocks': 'final.phase_generated_utc + final.phase_publication_utc', 'phase immutable origin/contract binding': 'final.phase_origin_id + final.phase_contract_binding', 'flip_risk value and definition': 'final.flip_risk + final.flip_risk_definition', 'flip_risk producer/version': 'final.flip_risk_producer + final.flip_risk_version', 'flip_risk source/publication clocks and availability': 'final.flip_risk_source_utc + final.flip_risk_publication_utc + final.flip_risk_availability', 'decision_utc': 'shared.native_decision_utc', 'consumption_completed_utc.quote': 'shared.quote_consumption_completed_utc', 'consumption_completed_utc.brti': 'shared.brti_consumption_completed_utc', 'consumption_completed_utc.btc': 'shared.btc_consumption_completed_utc', 'completed_publication_utc': 'shared.native_publication_completed_utc', 'original observer observed_utc': 'shared.recorded_utc', 'native shared decision identity': 'shared.native_decision_id', 'native/capture/model/build identity': 'shared.run_build + shared.model_hash + shared.capture_run_id', 'official window witnesses': 'shared.official_window_witness', 'explicit FINAL-to-origin evidence mapping': 'final.immutable_early_origin_id + final.link_basis'})
static={'lane=SCALP':'lane identity declaration only','mode=SIGNAL_ONLY':'mode declaration only','orders_enabled=false':'orders-disabled declaration only','lane':'SCALP declaration; not an observed signal'}
rows=[]
def add(source,section,term,lane,missing_producer):
    mapped=alias.get(term)
    # A current publication is never a substitute for an earlier immutable record.
    if source=='FINAL_CAPTURE_SPEC' and section=='immutable_accepted_origin_if_one_exists':mapped='early.origin_record'
    if source=='FINAL_CAPTURE_SPEC' and section=='research_origin':
        mapped={'research_origin_id':'early.research_origin_id','origin_kind':'early.origin_kind','protocol_sha256':'early.protocol_sha256','contract':'early.origin_record','side':'early.original_side','origin_observation_timestamp':'early.origin_observation_timestamp','origin_available_timestamp':'early.origin_available_timestamp','original_same_side_ask':'early.original_ask','original_same_side_bid':'early.original_bid','original_member_reference':'early.original_member_reference','protected_snapshot_key':'early.protected_snapshot_key','protected_content_sha256':'early.protected_content_sha256'}[term]
    if source=='FINAL_CAPTURE_SPEC' and section=='linked_guidance':
        mapped='final.'+term if 'final.'+term in byname else 'final.protected_evidence'
    if source=='FINAL_CAPTURE_SPEC' and section=='owner_witnesses':mapped='shared.quote_witness + shared.brti_witness + shared.btc_witness'
    if source=='FINAL_CAPTURE_SPEC' and section=='native_context' and term=='published_utc':mapped='shared.native_published_utc'
    if source=='SCALP_CAPTURE_SPEC' and section.startswith('4.') and term in ('event_sequence','received_utc','published_utc'):
        mapped={'event_sequence':'scalp.transition_sequence','received_utc':'scalp.received_utc','published_utc':'scalp.published_utc'}[term]
    if source=='SCALP_CAPTURE_SPEC' and section.startswith('2.') and term=='quote_id':mapped='scalp.original_quote_id'
    if term in static:
        rows.append(dict(source=source,section=section,requirement=term,lane=lane,mapped_fields='protocol/manifest',producer='DECLARED_CAPTURE_POLICY',status='STATIC_REQUIREMENT',reason=static[term]));return
    if mapped is None:
        candidates=[]
        if term in byname:candidates=[term]
        elif lane.lower()+'.'+term in byname:candidates=[lane.lower()+'.'+term]
        elif 'shared.'+term in byname:candidates=['shared.'+term]
        elif term in bytail:candidates=bytail[term]
        else:
            # Actual raw source paths, or a preserved whole object, are exact locators.
            candidates=[r['field'] for r in FIELDS if r['producer']=='PROTECTED_MAIN' and r['source_path']==term]
        if len(candidates)==1:mapped=candidates[0]
    fields=mapped.split(' + ') if mapped else []
    exact=fields and all(x in byname for x in fields)
    present=exact and all(byname[x]['source_path'] is not None for x in fields)
    if exact:
        producers=' + '.join(sorted({byname[x]['producer'] for x in fields}));status='PARSED_FIELD_IF_EMITTED' if present else 'UNAVAILABLE_REQUIRED_PRODUCER'
        reason='Preserve original value; parsed observation is not live admission' if present else 'Required live producer/witness/link is not established'
    else:
        producers=missing_producer;status='UNAVAILABLE_REQUIREMENT';reason='Exact requirement remains explicitly unimplemented; no reconstruction or fabricated producer'
    rows.append(dict(source=source,section=section,requirement=term,lane=lane,mapped_fields=mapped or '',producer=producers,status=status,reason=reason))
text=(ROOT/'references/scalp_requirements.md').read_text();section=''
prods={'1':'INDEPENDENT_ACQUIRER','2':'SCALP_ORIGIN_EVENT_STREAM','3':'NATIVE_V2_WITNESSES','4':'SCALP_LIFECYCLE_EVENT_STREAM','5':'SCALP_SERIAL_OWNER_STREAM','6':'CLOCK_MONITOR','7':'POPULATION_CATALOG'}
for line in text.splitlines():
    if line.startswith('## '):section=line[3:]
    for term in re.findall(r'`([^`]+)`',line):add('SCALP_CAPTURE_SPEC',section,term,'SCALP',prods.get(section[:1],'SCALP_ORIGIN_EVENT_STREAM'))
spec=json.loads((ROOT/'references/final_requirements.json').read_text())
for area in ['minimum_historical_analysis','live_admission_and_linked_management','full_v2_only_if_claimed']:
    for group in spec[area]:
        for term in group.get('fields',group.get('fields_each',[])):
            add('FINAL_CAPTURE_SPEC',group['group'],term,'FINAL','FINAL_LINKED_EVENT_PRODUCER' if 'origin' in group['group'] or 'guidance' in group['group'] else 'NATIVE_V2_WITNESSES')
for r in FIELDS:
    if r['lane']=='EARLY':add('EARLY_ROUND2_REQUIREMENTS','protected state / candidate gates / research origins',r['field'],'EARLY',r['producer'])
(ROOT/'requirements_crosswalk.json').write_text(json.dumps(rows,indent=2)+'\n')
with (ROOT/'requirements_crosswalk.csv').open('w',newline='') as h:
    w=csv.DictWriter(h,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
print(json.dumps({'requirements':len(rows),'explicitly_unmapped_unavailable':sum(r['status']=='UNAVAILABLE_REQUIREMENT' for r in rows)}))
