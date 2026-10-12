"""Recording quality only. No prediction, fitting, trade scoring or fee inference."""
from pathlib import Path
import json
from .evidence import file_sha
from candidates.early_recording_20261012.archive import canonical
REQUIREMENTS=[
 ('continuous_BTC','SOURCE','BTC source owner','source_ts,receipt_ts,available_at,feed,epoch,publication_id,observation_id','whole-run original source identity/chronology/window checks','recording'),
 ('continuous_BRTI','SOURCE','Delivery.accept/fail/remember','original_receipt_ts,basis,accepted_by_owner','whole-run original source identity/chronology/window checks','recording'),
 ('book_depth','QUOTE_ACCEPT','same Provider.session and Book decoder','raw_sha256,ticker,epoch,received_at,accepted_at; raw sid/seq/levels','quote_chain','recording'),
 ('quote_message_bytes','QUOTE_BYTES','same ws.recv return','exact original bytes; kernel clock unknown','sha256','recording'),
 ('decision_inputs','INFORMATION_INPUT','existing DurablePublisher','input_sha256,frame_id,published,decision_cutoff,capture_cutoff','reconstruct','recording'),
 ('proof_witness','QUOTE_PROOF','existing proof worker after cache','proof_sha256,native witness,exact event vector','proof_receipts','recording'),
 ('official_metadata','HTTP_RESPONSE','existing whitelisted kalshi_get','endpoint,raw_sha256,received_at,ticker,open,close,floor_strike','raw original body and exact contract','recording'),
 ('source_failures','SOURCE_GAP','existing owner failures','reason,asset,feed,epoch,observed_at','gap ledger; zero events may be valid','recording'),
 ('native_lifecycle','NATIVE_RECORD','existing journal after commit','original_journal,sequence,raw,sha256,committed_at; original origin/FINAL','exact native original associations','recording'),
 ('fee_applicability','HTTP_RESPONSE','official evidence required','formula,rounding,effective period,scope,authority','missing blocks cost verdict','economic'),
 ('research_protocol',None,'separate offline ledger','size,reaction assumptions,setup/confirmation/ticket/cancellation/expiry','explicit identities; no invented entries','economic'),
 ('diagnostics',None,'bounded optional counters','queue,losses,worker failure,health','memory and stderr','optional')]

def generate(root,index,output,*,health=None,max_range_bytes=32*1024**2,verification_limits=None):
    root=Path(root);index=Path(index);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    idx=json.loads((index/'index_manifest.json').read_bytes())
    from .whole_run import verify_run
    whole=verify_run(root,index,output/'whole-run',budget=verification_limits)
    metrics=whole['metrics']
    mechanics=dict(inputs_reconstructed=metrics.get('INFORMATION_INPUT',0),
        proofs_reconstructed=metrics.get('QUOTE_PROOF',0),proof_receipts_supported=metrics.get('proof_receipts_verified',0),
        book_states=metrics.get('book_states',0),native_associations=metrics.get('native_associations',0),
        information_associations=metrics.get('information_associations',0),whole_run=whole)
    errors=[dict(reason=k,count=v) for k,v in whole['issue_counts'].items()]
    matrix=[]
    for key,kind,source,fields,check,critical in REQUIREMENTS:
        count=idx['counts'].get(kind,0) if kind else 0
        status='VERIFIED' if count else 'BLOCKED'
        if key=='continuous_BTC' or key=='continuous_BRTI':
            asset=key.split('_')[1];count=idx['coverage'].get(asset,{}).get('count',0)
            status='VERIFIED' if count and whole['fixture_complete'] else 'BLOCKED'
        if key=='book_depth':status='VERIFIED' if mechanics.get('book_states') and not errors else 'FAILED'
        if key=='decision_inputs':status='VERIFIED' if mechanics.get('inputs_reconstructed') else 'BLOCKED'
        if key=='proof_witness':status='VERIFIED' if mechanics.get('proofs_reconstructed',0)>0 and mechanics['proofs_reconstructed']==mechanics['proof_receipts_supported'] else 'BLOCKED'
        if key in ('fee_applicability','research_protocol'):status='BLOCKED'
        if key=='native_lifecycle':status='VERIFIED' if whole['fixture_complete'] and metrics.get('native_associations') else 'BLOCKED'
        if key=='diagnostics' and health is not None:status='VERIFIED'
        if critical=='recording' and idx['gaps']:status='FAILED'
        if critical=='recording' and errors:status='FAILED'
        matrix.append(dict(requirement=key,source=source,persisted_fields=fields,record_kind=kind,
            reconstruction=check,records=count,status=status,evidence='FIXTURE_ONLY' if whole['evidence_classes']==['FIXTURE'] else 'UNVERIFIED_ACTUAL_OR_UNKNOWN',critical_for=critical,
            limitation='Exact fixture links only; no actual-production completeness claim' if key=='native_lifecycle' else None))
    matrix.append(dict(requirement='exact_decision_source_metadata_join',status='VERIFIED' if whole['fixture_complete'] else 'BLOCKED',evidence='FIXTURE_ONLY' if whole['evidence_classes']==['FIXTURE'] else 'UNVERIFIED_ACTUAL_OR_UNKNOWN',critical_for='recording',records=metrics.get('native_associations',0),source='native original decision witnesses',persisted_fields='journal identity + native key + original source tuples + quote witness + exact official identity',reconstruction='Whole-run exact joins; native information-consumption hash and consumed-HTTP-response hash are not stored and not claimed'))
    gaps=idx['gaps']+errors
    if health and health.get('status')=='INCOMPLETE':gaps.append(dict(reason='RECORDER_HEALTH_INCOMPLETE',details=health))
    report=dict(schema='BTC15_RECORDING_QUALITY_V1',fixture_only=whole['evidence_classes']==['FIXTURE'],counts=idx['counts'],coverage=idx['coverage'],
        matrix=matrix,gaps=gaps,mechanics=mechanics,health=health,
        complete_evidence=False,fixture_complete=whole['fixture_complete'] and not gaps,cost_verified=False,recording_readiness='OFFLINE_MECHANICS_ONLY',
        economic_evidence_readiness='BLOCKED',model_readiness='BLOCKED_INCOMPATIBLE_ARTIFACT',
        production_approval='NOT_AUTHORIZED',long_test='NO_GO',predictive_performance_evaluated=False,
        real_export_retrieval='BLOCKED_NO_SUPPORTED_REMOTE_SNAPSHOT_ACTION',
        index_sha256=idx['index_sha256'])
    (output/'quality.json').write_bytes(canonical(report))
    (output/'requirements_matrix.json').write_bytes(canonical(matrix))
    (output/'gaps.json').write_bytes(canonical(gaps))
    text=['BTC15 AUTOMATIC RECORDING REPORT','Fixture-only rehearsal. Long test: NO-GO.',
          'Recording mechanics do not establish economics, a compatible model or production approval.',
          'Original timestamps are application clocks; displayed depth is not a fill.','',
          'Records: '+json.dumps(idx['counts'],sort_keys=True),
          'Coverage: '+json.dumps(idx['coverage'],sort_keys=True),
          'Gaps/errors: '+str(len(gaps)), 'Whole-run partitions: '+str(whole['partitions']), 'Derived fixture completeness: '+str(whole['fixture_complete'] and not gaps), 'Actual production completeness: UNVERIFIED','']
    text += [r['requirement']+': '+r['status']+' ('+str(r['records'])+' records)' for r in matrix]
    (output/'REPORT.txt').write_text('\n'.join(text)+'\n')
    return report
