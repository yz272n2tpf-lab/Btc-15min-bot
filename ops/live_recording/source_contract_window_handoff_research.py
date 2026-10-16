"""Research-only causal source, contract and original outcome handoff.

This is a bounded, optional original-envelope consumer in the EXISTING
ops.recording_workflow.evidence streaming reader. All join semantics come
from ops.recording_workflow.lifecycle and ops.live_recording.reader.

A successful local match is NOT whole-campaign qualification: original
book proof, V81 input and independent information have their own additional
mandatory checks in CampaignVerifier. Missing records hard fail and never
become prices, receipt times or strategy calls.
"""
import base64
from collections import Counter,OrderedDict
from datetime import datetime
import json
import math

from btc15_ladder_settlement_v2 import receipt as existing_settlement_receipt
from ops.live_recording.policy import canonical,sha


def _number(v):
    return type(v) in (int,float) and math.isfinite(v)


def _timestamp(v):
    # Same explicit official time parse as the original independent reader.
    return datetime.fromisoformat(v.replace('Z','+00:00')).timestamp()


class SourceContractWindowHandoff:
    def __init__(self, *, max_sources=65536, max_metadata=4096,
                 max_http_raw_bytes=32*1024**2,max_http_items=2048,
                 max_acceptances=4096):
        if not 1<=max_sources<=262144 or not 1<=max_metadata<=16384:
            raise ValueError('SOURCE_HANDOFF_SOURCE_BUDGET')
        if not 1024<=max_http_raw_bytes<=128*1024**2 or not 1<=max_http_items<=8192:
            raise ValueError('SOURCE_HANDOFF_HTTP_BUDGET')
        if not 1<=max_acceptances<=16384:
            raise ValueError('SOURCE_HANDOFF_ACCEPTANCE_BUDGET')
        self.max_sources=max_sources
        self.max_metadata=max_metadata
        self.max_http_raw_bytes=max_http_raw_bytes
        self.max_http_items=max_http_items
        self.max_acceptances=max_acceptances
        self.sources={}
        self.original_observations={}
        self.official={}
        self.http_bytes=OrderedDict()
        self.http_raw_bytes=0
        self.original_responses=OrderedDict()
        self.original_response_bytes=0
        self.acceptances={}
        self.closeout_acceptances={}
        self.counts=Counter()
        self.gaps=0
        self.quarantined=False
        self.checkpoints=0
        self.max_source_entries=0
        self.max_official_entries=0
        self.max_response_bytes_used=0
        self.max_http_bytes_used=0

    def _save_wire(self, cache, digest, raw, attr):
        if not isinstance(raw,bytes) or sha(raw)!=digest:
            raise ValueError('SOURCE_HANDOFF_ORIGINAL_RAW_HASH')
        if digest in cache:
            # Original bytes may repeat but conflicting digest is fatal.
            if cache[digest][0]!=raw:
                raise ValueError('SOURCE_HANDOFF_RAW_DIGEST_COLLISION')
            return
        current=getattr(self,attr)
        if len(cache)>=self.max_http_items or current+len(raw)>self.max_http_raw_bytes:
            raise ValueError('SOURCE_HANDOFF_BOUNDED_RAW_CACHE')
        cache[digest]=(raw,None)
        setattr(self,attr,current+len(raw))
        if attr=='http_raw_bytes':
            self.max_http_bytes_used=max(self.max_http_bytes_used,current+len(raw))
        else:
            self.max_response_bytes_used=max(self.max_response_bytes_used,current+len(raw))

    def _original_source(self,role,session,v,sequence):
        for key in ('asset','feed','epoch','basis','source_ts',
                    'receipt_ts','available_at','value','original_receipt_ts',
                    'observation_id','publication_id','accepted_by_owner'):
            if key not in v:raise ValueError('SOURCE_HANDOFF_FIELD:'+key)
        digest=v['observation_id']
        x=dict(v);x.pop('observation_id')
        if sha(canonical(x))!=digest:
            raise ValueError('SOURCE_HANDOFF_ORIGINAL_OBSERVATION_SHA')
        if v['publication_id']!=sha(canonical([v['feed'],v['epoch'],v['source_ts']])):
            raise ValueError('SOURCE_HANDOFF_ORIGINAL_PUBLICATION_SHA')
        self._add_original_source(role,session,v,sequence)
        key=(role,session,digest)
        if key in self.original_observations:
            raise ValueError('SOURCE_HANDOFF_DUPLICATE_ORIGINAL_OBSERVATION')
        if len(self.original_observations)>=self.max_sources:
            raise ValueError('SOURCE_HANDOFF_ORIGINAL_OBSERVATIONS_CAP')
        self.original_observations[key]=dict(v)
        self.counts['SOURCE']+=1

    def _add_original_source(self,role,session,v,sequence):
        if v['asset'] not in ('BTC','BRTI') or not all(
            isinstance(v[k],str) and v[k] for k in ('feed','epoch')
        ):
            raise ValueError('SOURCE_HANDOFF_ASSET_OR_FEED')
        if (v['basis'] not in ('ORIGINAL','RECOVERED') or
            type(v['accepted_by_owner']) is not bool or
            not all(_number(v[k]) for k in (
                'source_ts','receipt_ts','available_at','value')) or
            not v['source_ts']<=v['receipt_ts']<=v['available_at']):
            raise ValueError('SOURCE_HANDOFF_RECEIPT_CHRONOLOGY')
        if v['basis']=='ORIGINAL':
            if not _number(v.get('original_receipt_ts')) or v['original_receipt_ts']>v['receipt_ts']:
                raise ValueError('SOURCE_HANDOFF_ORIGINAL_RECEIPT_FIELD')
        elif v.get('original_receipt_ts') is not None:
            raise ValueError('SOURCE_HANDOFF_RECOVERED_NOT_ORIGINAL')
        if v['basis']!='ORIGINAL' or not v['accepted_by_owner']:
            self.counts['NONORIGINAL_OR_UNACCEPTED_SOURCE']+=1
            return
        key=(role,session,v['asset'],v['source_ts'],v['receipt_ts'],v['value'],v['epoch'])
        if key in self.sources:
            # The existing full reader rejects an ambiguous exact source match.
            raise ValueError('SOURCE_HANDOFF_AMBIGUOUS_ORIGINAL_SOURCE_TUPLE')
        if len(self.sources)>=self.max_sources:
            raise ValueError('SOURCE_HANDOFF_VERIFIED_SOURCE_CAP')
        self.sources[key]=dict(available_at=v['available_at'],sequence=sequence,
                                publication_id=v['publication_id'])
        self.max_source_entries=max(self.max_source_entries,len(self.sources))

    def _source_repeat(self,role,session,v,sequence):
        first=self.original_observations.get((role,session,v.get('original_observation_id')))
        if first is None:
            raise ValueError('SOURCE_HANDOFF_SOURCE_REPEAT_FIRST_MISSING')
        expanded=dict(first,**v,original_receipt_ts=first['original_receipt_ts'])
        body={k:value for k,value in expanded.items() if k not in (
            'observation_id','original_observation_id','first_receipt_ts')}
        body['original_receipt_ts']=(
            expanded['receipt_ts'] if expanded['basis']=='ORIGINAL' else None)
        if sha(canonical(body))!=v['observation_id']:
            raise ValueError('SOURCE_HANDOFF_SOURCE_REPEAT_SHA')
        if (v.get('first_receipt_ts')!=first['receipt_ts'] or
             v.get('publication_id')!=first['publication_id']):
            raise ValueError('SOURCE_HANDOFF_SOURCE_REPEAT_FIRST_RECEIPT')
        expanded.update(observation_id=v['observation_id'])
        self._add_original_source(role,session,expanded,sequence)
        self.counts['SOURCE_REPEAT']+=1

    def _metadata(self,role,session,v,sequence):
        try:
            digest=v['raw_sha256'];raw=self.http_bytes[digest][0]
        except KeyError as e:
            raise ValueError('SOURCE_HANDOFF_HTTP_WITHOUT_ORIGINAL_BYTES') from e
        payload=json.loads(raw)
        fields=v.get('official_fields')
        market=payload.get('market') if isinstance(payload,dict) else None
        if not isinstance(market,dict) or not fields:
            self.counts['HTTP_OTHER']+=1
            return
        if not all(fields.get(k)==market.get(k) for k in fields):
            raise ValueError('SOURCE_HANDOFF_OFFICIAL_PROJECTION_MISMATCH')
        if not isinstance(v.get('endpoint'),str) or not v['endpoint'].startswith('/trade-api/v2/markets'):
            raise ValueError('SOURCE_HANDOFF_UNTRUSTED_METADATA_ENDPOINT')
        ticker=market.get('ticker');target=market.get('floor_strike')
        if not isinstance(ticker,str) or not ticker or not _number(target):
            self.counts['MARKET_WITHOUT_NUMERIC_TARGET']+=1
            return
        if not _number(v.get('received_at')):
            raise ValueError('SOURCE_HANDOFF_MARKET_RECEIPT')
        try:
            opened=_timestamp(market['open_time'])
            closed=_timestamp(market['close_time'])
        except (KeyError,ValueError,TypeError) as e:
            raise ValueError('SOURCE_HANDOFF_MARKET_CLOCK') from e
        if not _number(opened) or not _number(closed) or closed<=opened:
            raise ValueError('SOURCE_HANDOFF_MARKET_INTERVAL')
        key=(role,session,ticker,opened,closed,target)
        existing=self.official.setdefault(key,[])
        if sum(len(x) for x in self.official.values())>=self.max_metadata:
            raise ValueError('SOURCE_HANDOFF_OFFICIAL_COUNT_LIMIT')
        existing.append(dict(received_at=v['received_at'],sequence=sequence,
                             original_http_sha256=digest))
        self.max_official_entries=max(self.max_official_entries,
                                      sum(len(x) for x in self.official.values()))
        self.counts['OFFICIAL_MARKET_IDENTITY']+=1

    def _match_source(self,role,session,asset,source,received,value,epoch,cut):
        if not all(_number(x) for x in (source,received,value,cut)) or not source<=received<=cut:
            raise ValueError('SOURCE_HANDOFF_DECISION_SOURCE_CUTOFF')
        matching=[]
        for key,detail in self.sources.items():
            r,s,a,ts,rt,val,ep=key
            if ((r,s,a,ts,rt,val)==(role,session,asset,source,received,value)
                and (epoch is None or ep==epoch)
                and detail['available_at']<=cut):
                matching.append(detail)
                if len(matching)>1:break
        if len(matching)!=1:
            raise ValueError('SOURCE_HANDOFF_MISSING_OR_AMBIGUOUS_SOURCE:'+asset)
        return matching[0]

    def _match_market(self,role,session,ticker,opened,closed,target,cut):
        if not all(_number(x) for x in (opened,closed,target,cut)) or closed-opened!=900:
            raise ValueError('SOURCE_HANDOFF_15M_OFFICIAL_CLOCK')
        key=(role,session,ticker,opened,closed,target)
        matches=[x for x in self.official.get(key,[]) if x['received_at']<=cut]
        if not matches:
            raise ValueError('SOURCE_HANDOFF_EXACT_OFFICIAL_MARKET_MISSING')
        return matches

    def _native_main(self,role,session,record,v,n):
        if n.get('unavailable_reason'):
            self.counts['MAIN_LEGITIMATE_UNAVAILABLE']+=1
            return
        frame=n['evidence'];brti=frame['brti']
        cut=frame['feature_cutoff'];captured=frame['captured_ts']
        published=n['published_ts'];committed=v['committed_at']
        if (n['contract']!=frame['contract'] or
            not all(_number(x) for x in (cut,captured,published,committed)) or
            not frame['official_open']<=cut<=captured<frame['official_close'] or
            not captured<=published<=committed):
            raise ValueError('SOURCE_HANDOFF_NATIVE_CONTRACT_OR_PUBLICATION_CLOCK')
        btc=self._match_source(role,session,'BTC',frame['btc_source'],
                               frame['btc_received'],frame['btc_price'],None,cut)
        b=self._match_source(role,session,'BRTI',brti['cf_ts'],
                             brti['delivery']['observed_ts'],brti['value'],
                             brti['delivery']['owner_epoch'],cut)
        m=self._match_market(role,session,frame['contract'],
                             frame['official_open'],frame['official_close'],
                             frame['target'],cut)
        self.counts['MAIN_EXACT_BTC_BRTI_OFFICIAL_CUTOFF']+=1
        self.counts['MAIN_MARKET_EQUIVALENCE_RECEIPTS']+=len(m)
        # A source/local identity pass is not original quote proof, nor
        # complete BUY/EXIT or independently authoritative settlement.
        return dict(btc=btc,brti=b,official=m)

    def _original_response(self,role,session,v):
        raw=base64.b64decode(v['raw_base64'],validate=True)
        digest=v['sha256']
        if sha(raw)!=digest or not _number(v.get('received_at')):
            raise ValueError('SOURCE_HANDOFF_ORIGINAL_HTTP_RECEIPT')
        endpoint=v.get('endpoint','')
        if not isinstance(endpoint,str) or not (
            endpoint.startswith('https://external-api.kalshi.com/')
            or endpoint.startswith('https://api.elections.kalshi.com/')
            or endpoint.startswith('https://api.exchange.coinbase.com/')):
            raise ValueError('SOURCE_HANDOFF_UNTRUSTED_HTTP_ORIGIN')
        self._save_wire(self.original_responses,digest,raw,'original_response_bytes')
        first,observed=self.original_responses[digest]
        times=list(observed or ())
        if len(times)>=64:raise ValueError('SOURCE_HANDOFF_DUPLICATE_HTTP_RECEIPT_CAP')
        times.append(v['received_at'])
        self.original_responses[digest]=(first,times)
        self.counts['ORIGINAL_RESPONSE']+=1

    def _outcome_accept(self,role,session,record,v):
        raw=v['raw'].encode()
        if sha(raw)!=v['sha256'] or not _number(v['accepted_at']):
            raise ValueError('SOURCE_HANDOFF_OUTCOME_ACCEPTANCE_SHA_OR_CLOCK')
        value=json.loads(raw)
        if not isinstance(value,dict) or not isinstance(value.get('ticker'),str):
            raise ValueError('SOURCE_HANDOFF_OUTCOME_ACCEPTANCE_SCHEMA')
        key=(role,session,value['ticker'])
        if len(self.acceptances)>=self.max_acceptances:
            raise ValueError('SOURCE_HANDOFF_OUTCOME_ACCEPTANCE_CAP')
        self.acceptances.setdefault(key,[]).append(dict(
            value=value,at=v['accepted_at'],response_sha256=v['response_sha256'],
            sequence=record['sequence']))
        self.counts['ORIGINAL_OUTCOME_ACCEPTANCE']+=1

    def _closeout_accept(self,role,session,record,v):
        raw=v['raw'].encode()
        if sha(raw)!=v['sha256'] or not _number(v['accepted_at']):
            raise ValueError('SOURCE_HANDOFF_CLOSEOUT_ACCEPTANCE_SHA_OR_CLOCK')
        val=json.loads(raw)
        if not isinstance(val,dict) or not isinstance(val.get('cohort'),dict):
            raise ValueError('SOURCE_HANDOFF_CLOSEOUT_ACCEPTANCE_SCHEMA')
        if len(self.closeout_acceptances)>=self.max_acceptances:
            raise ValueError('SOURCE_HANDOFF_CLOSEOUT_CAP')
        key=(role,session,sha(canonical(val['cohort'].get('brti'))))
        self.closeout_acceptances.setdefault(key,[]).append(dict(value=val,at=v['accepted_at']))
        self.counts['ORIGINAL_CLOSEOUT_ACCEPTANCE']+=1

    def _native_outcome(self,role,session,v,n):
        kind=n.get('kind')
        published=n.get('published_ts')
        if not _number(published) or not _number(v['committed_at']) or published>v['committed_at']:
            raise ValueError('SOURCE_HANDOFF_SETTLEMENT_PUBLICATION_CLOCK')
        contract=n.get('contract')
        if not isinstance(contract,str) or not contract:
            raise ValueError('SOURCE_HANDOFF_SETTLEMENT_CONTRACT')
        if kind=='SETTLEMENT':
            out=n['settlement']
            if out.get('status')=='UNAVAILABLE':
                self.counts['SETTLEMENT_UNAVAILABLE_NOT_AUTHORITATIVE']+=1
                return
            candidates=[e for e in self.acceptances.get((role,session,contract),[])
                        if e['value']==out and e['at']<=published]
            if not candidates:raise ValueError('SOURCE_HANDOFF_OUTCOME_ACCEPTANCE_MISSING')
            values=[]
            for e in candidates:
                response=self.original_responses.get(e['response_sha256'])
                if response is None:
                    raise ValueError('SOURCE_HANDOFF_ORIGINAL_OUTCOME_RESPONSE_MISSING')
                raw,times=response
                if not any(at<=out['received_ts'] for at in times):
                    raise ValueError('SOURCE_HANDOFF_OUTCOME_RESPONSE_FROM_FUTURE')
                if not out['received_ts']<=e['at']<=published:
                    raise ValueError('SOURCE_HANDOFF_OUTCOME_RECEIPT_ACCEPT_PUBLICATION')
                if sha(raw)!=e['response_sha256']:
                    raise ValueError('SOURCE_HANDOFF_OUTCOME_RESPONSE_SHA_DRIFT')
                payload=json.loads(raw)
                expected=existing_settlement_receipt(contract,out['open_ts'],
                                                       payload,out['received_ts'])
                if expected!=out:
                    raise ValueError('SOURCE_HANDOFF_OFFICIAL_SETTLEMENT_RECOMPUTE')
                values.append(sha(canonical(out)))
            self.counts['EXACT_ORIGINAL_SETTLEMENT_ASSOCIATIONS']+=1
            if out.get('status')=='AUTHORITATIVE':
                self.counts['AUTHORITATIVE_ORIGINAL_SETTLEMENT_ASSOCIATIONS']+=1
            else:
                self.counts['NONAUTHORITATIVE_SETTLEMENT_ASSOCIATIONS']+=1
        elif kind=='BRTI_CLOSEOUT':
            out=n['brti_closeout']
            key=(role,session,sha(canonical(out)))
            values=[a for a in self.closeout_acceptances.get(key,[])
                    if a['value'].get('cohort',{}).get('brti')==out and a['at']<=published]
            if not values:raise ValueError('SOURCE_HANDOFF_CLOSEOUT_ACCEPTANCE_MISSING')
            if out.get('final60_count')!=60 or out.get('final60_complete') is not True:
                raise ValueError('SOURCE_HANDOFF_BRTI_CLOSEOUT_60S_MISSING')
            self.counts['EXACT_ORIGINAL_BRTI_CLOSEOUT_ASSOCIATIONS']+=1

    def accept(self,role,record):
        if role not in ('source','information'):
            raise ValueError('SOURCE_HANDOFF_ROLE')
        kind=record['kind']
        if kind=='EVIDENCE_GAP':
            self.gaps+=1
            self.quarantined=True
            self.counts['EVIDENCE_GAP']+=1
        elif kind=='INFORMATION_FAILURE' or (kind=='SOURCE_GAP' and
                record['payload'].get('reason')!='SOURCE_START_OR_EPOCH_CHANGE'):
            self.gaps+=1
            self.quarantined=True
            self.counts['ORIGINAL_SOURCE_OR_INFORMATION_GAP']+=1
        if self.quarantined:
            if kind in ('SOURCE','SOURCE_REPEAT','HTTP_RESPONSE',
                        'NATIVE_RECORD','OUTCOME_ACCEPTANCE','CLOSEOUT_ACCEPTANCE'):
                self.counts['DISQUALIFIED_AFTER_CAPTURE_LOSS']+=1
            return
        v=record['payload'];session=record['session'];seq=record['sequence']
        if kind=='SOURCE':
            self._original_source(role,session,v,seq)
        elif kind=='SOURCE_REPEAT':
            self._source_repeat(role,session,v,seq)
        elif kind=='HTTP_BYTES':
            raw=base64.b64decode(v['raw_base64'],validate=True)
            self._save_wire(self.http_bytes,v['sha256'],raw,'http_raw_bytes')
            self.counts['HTTP_BYTES']+=1
        elif kind=='HTTP_RESPONSE':
            self._metadata(role,session,v,seq)
            self.counts['HTTP_RESPONSE']+=1
        elif kind=='ORIGINAL_RESPONSE':
            self._original_response(role,session,v)
        elif kind=='OUTCOME_ACCEPTANCE':
            self._outcome_accept(role,session,record,v)
        elif kind=='CLOSEOUT_ACCEPTANCE':
            self._closeout_accept(role,session,record,v)
        elif kind=='NATIVE_RECORD':
            raw=v.get('raw')
            if not isinstance(raw,str) or sha(raw.encode())!=v.get('sha256'):
                raise ValueError('SOURCE_HANDOFF_NATIVE_RAW_SHA')
            n=json.loads(raw)
            if not isinstance(n,dict):raise ValueError('SOURCE_HANDOFF_NATIVE_SCHEMA')
            k=n.get('kind')
            if k=='NATIVE_DECISION':
                self._native_main(role,session,record,v,n)
            elif k in ('SETTLEMENT','BRTI_CLOSEOUT'):
                self._native_outcome(role,session,v,n)
            self.counts['NATIVE_RECORDS_SCANNED']+=1

    def checkpoint(self,role,session,last_sequence):
        self.checkpoints+=1
        state=dict(schema='BTC15_SOURCE_CONTRACT_WINDOW_HANDOFF_AUDIT_V1',
                   role=role,session=session,last_original_sequence=last_sequence,
                   verified_original_sources=self.counts['SOURCE']+self.counts['SOURCE_REPEAT'],
                   stored_original_source_tuples=len(self.sources),
                   original_official_market_identity_receipts=self.counts['OFFICIAL_MARKET_IDENTITY'],
                   main_exact_original_source_metadata_decisions=self.counts['MAIN_EXACT_BTC_BRTI_OFFICIAL_CUTOFF'],
                   original_authoritative_settlement_links=self.counts['AUTHORITATIVE_ORIGINAL_SETTLEMENT_ASSOCIATIONS'],
                   original_brti_closeout_links=self.counts['EXACT_ORIGINAL_BRTI_CLOSEOUT_ASSOCIATIONS'],
                   original_evidence_gaps=self.gaps,
                   quarantined_on_loss=self.quarantined,
                   source_quote_and_full_lifecycle_associations='NOT_QUALIFIED',
                   native_early_qualified=False,
                   checkpoint_can_restart_reader=False)
        state['audit_sha256']=sha(canonical(state))
        return state

    def finish(self):
        return dict(schema='BTC15_SOURCE_CONTRACT_HANDOFF_STAGE4_RESEARCH_V1',
                    record_kinds=dict(self.counts),
                    original_source_tuples=len(self.sources),
                    original_official_market_identities=len(self.official),
                    max_original_source_tuples=self.max_source_entries,
                    max_official_receipts=self.max_official_entries,
                    max_original_http_cache_bytes=self.max_response_bytes_used,
                    max_http_response_cache_bytes=self.max_http_bytes_used,
                    bounded_checkpoints=self.checkpoints,
                    original_evidence_gap_envelopes=self.gaps,
                    quarantined_on_loss=self.quarantined,
                    source_quote_and_native_decision_fully_associated=False,
                    exact_settlement_status_not_proof_of_complete_campaign=True,
                    original_early_qualified=False,
                    full_campaign_qualified=False,
                    producer_changed=False,orders=False)