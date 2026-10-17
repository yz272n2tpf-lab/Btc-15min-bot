"""Forensic accounting/trace of already sealed bytes; NOT a qualification reader.

Uses the existing record verifier and vector codec. Never changes quarantine,
fills missing health observations, runs an evaluator, or claims native execution.
"""
import base64
from collections import Counter,defaultdict
import json
from pathlib import Path
import sys

from ops.recording_workflow.evidence import lines,file_sha
from ops.recording_workflow.whole_run import Verifier,LIMITS
from ops.live_recording.policy import canonical,sha
from ops.live_recording.burst_journal_research import observation_charge
from btc15_information_v1 import source_key,progress,check_anchor,Unavailable,iso
from btc15_kalshi_quote_provenance_v1 import replay,MAX_AGE

QUOTE_DERIVED={'raw_sha256','price_unit','quantity_unit','displayed_depth_only','fill_evidence'}
HTTP_DERIVED={'raw_sha256','effective_from','effective_to','fee_rounding','fee_formula',
             'applicable_scope','missing','official_fields','target_binding','observed_series_fields'}

def records(root,role):
    seal=json.loads((root/role/'seal.json').read_bytes());previous=None;seq=0
    for item in seal['files']:
        p=root/role/item['path'];assert p.stat().st_size==item['size'] and file_sha(p)==item['sha256']
        if not item['path'].endswith('.gz'):continue
        for _,r,raw in lines(p):
            assert r['session']==seal['session'] and r['sequence']==seq+1 and r['previous_sha256']==previous
            seq=r['sequence'];previous=r['sha256'];yield r,raw
    assert seq==seal['last_sequence'] and previous==seal['last_sha256']

def decode_information(root,output):
    # Only reuse the existing immutable vector/input codec. This forensic SQL
    # output has no qualification status and is separate from campaign replay.
    v=Verifier(root,root,output/'codec',dict(LIMITS));decoded={};failures=[]
    try:
        for r,_ in records(root,'information'):
            if r['kind'] in ('VECTOR','INFORMATION_INPUT'):
                v.record(dict(r,_part=0))
                if r['kind']=='INFORMATION_INPUT':
                    z=json.loads(v.db.execute('SELECT v FROM facts WHERE t="INFORMATION_INPUT" AND q=?',(r['sequence'],)).fetchone()[0])
                    raw=canonical(z['value']);assert sha(raw)==r['payload']['input_sha256']
                    decoded[r['sequence']]=dict(record=r,value=z['value'],raw=raw)
            elif r['kind']=='INFORMATION_FAILURE':failures.append(r)
        v.db.commit()
    finally:
        v.db.close()
        for f in (v.fgap,v.fpart,v.fassoc):f.close()
    return decoded,failures

def account(root,role,inputs):
    wire={};http={};by=defaultdict(Counter);decoded_bytes=0;envelopes=Counter();health=[]
    for r,line in records(root,role):
        decoded_bytes+=len(line);k=r['kind'];p=r['payload'];envelopes[k]+=1
        if k in ('QUOTE_BYTES','HTTP_BYTES'):
            raw=base64.b64decode(p['raw_base64'],validate=True);assert sha(raw)==p['sha256']
            (wire if k=='QUOTE_BYTES' else http)[p['sha256']]=raw;continue
        if k in ('START','STOP','VECTOR','SOURCE_GAP'):continue
        if k in ('QUOTE_ACCEPT','QUOTE_RECEIVE','QUOTE_REQUEST'):
            raw=wire[p['raw_sha256']];f={x:y for x,y in p.items() if x not in QUOTE_DERIVED}
            # Both bounds are retained. Equality with the recorded upper bound
            # proves all nonempty messages in this kind were admitted as text.
            before_bytes=observation_charge(dict(f,raw=raw));f['raw']=raw.decode()
            before=observation_charge(f);after=observation_charge(p)
        elif k=='HTTP_RESPONSE':
            f={x:y for x,y in p.items() if x not in HTTP_DERIVED};f['raw']=http[p['raw_sha256']]
            before=before_bytes=observation_charge(f);after=observation_charge(p)
        else:
            if k=='ORIGINAL_RESPONSE':
                f={x:y for x,y in p.items() if x not in ('raw_base64','sha256')};f['raw']=base64.b64decode(p['raw_base64'],validate=True)
                assert sha(f['raw'])==p['sha256']
            elif k in ('CANDLE_ACCEPTANCE','V81_INPUT','BRTI_READ','NATIVE_RECORD'):
                f={x:y for x,y in p.items() if x!='sha256'};f['raw']=p['raw'].encode();assert sha(f['raw'])==p['sha256']
            elif k=='SOURCE':f={x:y for x,y in p.items() if x not in ('publication_id','observation_id')}
            elif k=='RECORDING_HEALTH':f=dict(raw=canonical(p));health.append(dict(sequence=r['sequence'],value=p))
            elif k=='INFORMATION_INPUT':f=dict(raw=inputs[r['sequence']]['raw'],published=p['published'],frame_id=p['frame_id'])
            else:
                assert k in ('INFORMATION_FAILURE','STREAM_START','STREAM_END','RECORDING_BOUNDARY'),k
                f=dict(p)
            before=before_bytes=after=observation_charge(f)
        b=by[k];b['observations']+=1
        b['admission_total']+=before;b['bytes_type_lower_bound']+=before_bytes
        b['old_processed_total']+=after;b['charge_difference']+=before-after
    terminal=json.loads((root/role/'terminal-status.json').read_bytes());w=terminal['writer']
    assert set(by)==set(w['admission_by_kind']),(role,set(by)^set(w['admission_by_kind']))
    for k,b in by.items():
        assert b['observations']==w['admission_by_kind'][k]['admitted'],(role,k,'count')
        assert b['admission_total']==w['admission_by_kind'][k]['admitted_charge_bytes'],(role,k,'charge',b,w['admission_by_kind'][k])
    admitted=sum(b['admission_total'] for b in by.values());old=sum(b['old_processed_total'] for b in by.values())
    assert admitted==w['admitted_charge_bytes'] and old==w['durable_batch']['processed_charge_bytes']==w['durable_batch']['durable_charge_bytes'],(role,admitted,old,w)
    assert decoded_bytes==terminal['raw_bytes'] and sum(envelopes.values())==terminal['records']
    return dict(by_kind=dict(by),admitted_charge=admitted,old_processed_charge=old,
        exact_charge_difference=admitted-old,observations=sum(b['observations'] for b in by.values()),
        envelopes=dict(envelopes),decoded_bytes=decoded_bytes,original_terminal_status=terminal['status'],
        original_stop_reason=terminal['reason'],queue=w['queue_items'],unfinished=w['unfinished_observations'],
        reported_losses=w['losses'],hooks=terminal['hooks'],health=health,
        accounting_reconciled=True,recovered_evidence=False)

def candle_trace(root,inputs):
    main=[r for r,_ in records(root,'main')];target=next(r for r in main if r['sequence']==308)
    p=target['payload'];rows=json.loads(p['raw']);future=[(i,x) for i,x in enumerate(rows) if x[0]>p['accepted_at']]
    assert len(future)==1;i,row=future[0];native=[row[0],row[1],*row[3:]];upstream=[row[2],*row[3:]];matches=[]
    for r in main:
        v=r['payload']
        if r['kind']=='ORIGINAL_RESPONSE' and v['endpoint'].endswith('/candles'):
            raw=base64.b64decode(v['raw_base64']);assert sha(raw)==v['sha256']
            for n,x in enumerate(json.loads(raw)):
                st,lo,hi,op,cl,vol=map(float,x)
                if [st,op,hi,lo,cl,vol]==upstream:
                    matches.append(dict(record_sequence=r['sequence'],record_sha256=r['sha256'],response_sha256=v['sha256'],row_index=n,received_at=v['received_at'],wire_row=x))
    native_records=[dict(sequence=r['sequence'],payload=json.loads(r['payload']['raw'])) for r in main if r['kind']=='NATIVE_RECORD']
    use=[dict(input_sequence=q,decision=z['value']['anchor']['decision'],included=native in z['value']['anchor']['completed']) for q,z in inputs.items()]
    assert all(not x['included'] or x['decision']>=row[0] for x in use)
    return dict(record_sequence=308,record_sha256=target['sha256'],row_index=i,native_schema_row=row,
        bucket_start=row[2],bucket_end=row[0],cache_accepted_at=p['accepted_at'],
        bucket_end_minus_cache_acceptance=row[0]-p['accepted_at'],http_matches=matches,
        native_records=native_records,information_anchor_uses=use,
        conclusion='AUTHENTIC_CURRENT_BUCKET_IN_CACHE; NOT_COMPLETED_AT_CACHE_ACCEPTANCE')

def information_trace(root,inputs,failures):
    traces=[];last_published=None
    for q,z in inputs.items():
        f=z['value'];p=z['record']['payload'];a=f['anchor'];b=f['brti'];proof=f['proof'];cut=f['cut']
        check_anchor(a)
        quotes,_=replay(proof,iso(cut),a['ticker'],int(a['closed']*1000),int(cut*1000))
        key=source_key(f,quotes);change=None
        try:change=progress(last_published['key'] if last_published else None,key)
        except Unavailable as e:change=str(e)
        if not p['published']:
            failure=next(r for r in failures if r['sequence']==q+1)
            traces.append(dict(failure_sequence=failure['sequence'],failure_record_sha256=failure['sha256'],input_sequence=q,input_record_sha256=z['record']['sha256'],input_sha256=p['input_sha256'],frame_id=p['frame_id'],published=False,
                cut=cut,anchor_decision=a['decision'],anchor_id=f['anchor_id'],btc=a['btc'],brti=b,
                quote_identity=proof['identity'],quote_consumed_ms=proof['consumed_ms'],quote_received=f['quote_received'],quotes=quotes,
                source_progress=change,prior_published=({k:v for k,v in last_published.items() if k!='key'} if last_published else None),
                freshness_slack_at_capture=min(b['source']+5,a['btc']['source']+10,proof['identity'][3]/1000+MAX_AGE,proof['consumed_ms']/1000+MAX_AGE,a['closed'])-cut,
                native_health_and_publish_clock_recorded=False,
                classification='PUBLISHER_REJECTION_WITH_UNRECORDED_REASON' if change is True else 'UNRESOLVED'))
        if p['published']:last_published=dict(key=key,input_sequence=q,input_sha256=p['input_sha256'],frame_id=p['frame_id'],cut=cut)
    assert [t['failure_sequence'] for t in traces]==[141,158,185,189,209,215,227]
    sources=[dict(sequence=r['sequence'],kind=r['kind'],payload=r['payload']) for r,_ in records(root,'main') if r['kind'] in ('SOURCE','BRTI_READ')]
    return dict(input_count=len(inputs),published_count=sum(z['record']['payload']['published'] for z in inputs.values()),failures=traces,
        first_input=dict(sequence=next(iter(inputs)),value=next(iter(inputs.values()))['value']),main_sources=sources)

def scope_trace(root,inputs):
    roles={}
    for role in ('main','v81','information'):
        terminal=json.loads((root/role/'terminal-status.json').read_bytes())
        identity=json.loads((root/role/'identity.json').read_bytes())
        tail=[r for r,_ in records(root,role) if r['kind'] in ('RECORDING_BOUNDARY','STOP')]
        roles[role]=dict(started=identity['started'],stopped_at=terminal['stopped_at'],elapsed=terminal['elapsed'],tail=tail)
    q,z=next(iter(inputs.items()));brti=z['value']['brti']
    boundary=roles['main']['tail'][0]['payload']['observed_at']
    matches=[r['sequence'] for r,_ in records(root,'main') if r['kind']=='SOURCE' and
             r['payload'].get('asset')=='BRTI' and r['payload'].get('basis')=='ORIGINAL' and
             r['payload'].get('epoch')==brti['epoch'] and r['payload'].get('value')==brti['value'] and
             r['payload'].get('source_ts')==brti['source'] and
             r['payload'].get('original_receipt_ts')==brti['received']]
    return dict(roles=roles,first_information_input=q,first_information_brti=brti,
                main_boundary=boundary,brti_receipt_after_main_boundary=brti['received']-boundary,
                exact_brti_source_matches=matches)

def main():
    root=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(exist_ok=False)
    inputs,failures=decode_information(root,out)
    result=dict(schema='BTC15_AUTHENTIC_FORENSIC_TRACE_V1',qualification=False,
                accounting={r:account(root,r,inputs) for r in ('main','v81','information')},
                candle=candle_trace(root,inputs),information=information_trace(root,inputs,failures),
                scope=scope_trace(root,inputs))
    (out/'findings.json').write_bytes(canonical(result))
    print(json.dumps(dict(accounting={r:{k:x[k] for k in ('admitted_charge','old_processed_charge','exact_charge_difference','observations','accounting_reconciled')} for r,x in result['accounting'].items()},
                         candle={k:v for k,v in result['candle'].items() if k not in ('native_records','information_anchor_uses')},
                         information=result['information']['failures']),indent=2))

if __name__=='__main__':main()
