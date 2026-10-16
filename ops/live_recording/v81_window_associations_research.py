"""Stage 5 research: join the EXISTING reader's original V81 quote, input and scalp facts.

This optional bounded consumer sees only original, per-envelope-hash-verified
archive records. It reuses the production QualifiedInputs.require_qualified and
the original native CampaignVerifier.scalp causal predicates. It does NOT run
the trading model or treat prices as fills. Authentic BUY/EXIT and profitability
remain unauthorized until all source roles and settlement links qualify.

All three original independent proofs are necessary for an actionable V81
observation: Kalshi timestamped depth, exact BTC response receipt, and exact
BRTI consumer receipt. No interpolation, replacement, resampling or tolerance.
"""
import base64
from collections import Counter,OrderedDict
from datetime import datetime,timezone
import json
import math
import os
from pathlib import Path

from btc15_v81_qualified_inputs_v1 import require_qualified,epoch
from ops.live_recording.policy import canonical,sha


def number(v):return type(v) in (int,float) and math.isfinite(v)


class V81WindowAssociations:
    def __init__(self, quote_handoff, source_handoff,
                 *, max_inputs=8192,max_brti_reads=8192,max_original_http_receipts=8192):
        if any(type(z) is not int or z<1 or z>65536 for z in
               (max_inputs,max_brti_reads,max_original_http_receipts)):
            raise ValueError('V81_LINKS_RESOURCE_BUDGET')
        self.quote=quote_handoff
        self.source=source_handoff
        self.max_inputs=max_inputs
        self.max_brti_reads=max_brti_reads
        self.max_original_http_receipts=max_original_http_receipts
        self.inputs=OrderedDict()
        self.brti=OrderedDict()
        self.http=OrderedDict()
        self.counts=Counter()
        self.verified=[]
        self.total_original_native_matches=0
        self.audit_file=None
        self.audit_path=None
        self.audit_bytes=0
        self.audit_max_bytes=64*1024**2
        self.audit_sha256=None
        self.max_retained_inputs=0
        self.max_retained_brti=0
        self.max_retained_http=0
        self.evicted_inputs=0
        self.evicted_brti=0
        self.evicted_http=0
        self.quarantined=False
        self.gaps=0
        self.checkpoints=0

    def attach_audit(self,path,*,max_bytes=64*1024**2):
        """Append-only bounded exact-match ledger in the isolated reader output.

        A partial ledger left by a failed read is NOT a campaign verdict. The
        inventory's final manifest is still mandatory to claim even a complete
        source scan; producer SEALED and full CampaignVerifier remain separate.
        """
        if self.audit_file is not None:
            raise ValueError('V81_LINKS_AUDIT_ALREADY_OPEN')
        if type(max_bytes) is not int or not 1024<=max_bytes<=256*1024**2:
            raise ValueError('V81_LINKS_AUDIT_BUDGET')
        target=Path(path)
        if target.is_symlink() or not target.parent.is_dir():
            raise ValueError('V81_LINKS_AUDIT_INVALID_DESTINATION')
        self.audit_max_bytes=max_bytes
        self.audit_path=target
        self.audit_file=target.open('xb')

    def _audit_native_receipt(self,receipt):
        line=canonical(receipt)+b'\n'
        if self.audit_bytes+len(line)>self.audit_max_bytes:
            raise ValueError('V81_LINKS_AUDIT_OUTPUT_BUDGET')
        if self.audit_file is None:
            raise ValueError('V81_LINKS_DURABLE_AUDIT_REQUIRED')
        self.audit_file.write(line)
        self.audit_bytes+=len(line)
        self.total_original_native_matches+=1
        if len(self.verified)<1024:
            self.verified.append(receipt)

    @staticmethod
    def _body(v):
        raw=v.get('raw')
        if not isinstance(raw,str) or sha(raw.encode())!=v.get('sha256'):
            raise ValueError('V81_LINKS_ORIGINAL_RECORD_RAW_SHA')
        try:obj=json.loads(raw)
        except (TypeError,ValueError) as exc:
            raise ValueError('V81_LINKS_INVALID_ORIGINAL_JSON') from exc
        if not isinstance(obj,dict):
            raise ValueError('V81_LINKS_JSON_NOT_OBJECT')
        return obj

    def _bound(self,cache,key,entry,capacity,counter):
        if key in cache:
            if cache[key]!=entry:
                raise ValueError('V81_LINKS_CONFLICTING_EXACT_RECEIPT')
            return
        cache[key]=entry
        if len(cache)>capacity:
            cache.popitem(last=False)
            setattr(self,counter,getattr(self,counter)+1)

    def _brti(self,session,v,seq):
        observed=self._body(v)
        at=v.get('received_at')
        if not number(at):
            raise ValueError('V81_LINKS_BRTI_RECEIPT_CLOCK')
        # The adapter's original brti() preserves canonical original owner
        # bytes and original application receipt, not a reconstructed poll.
        key=(session,v['sha256'],at)
        item=dict(point=observed,sequence=seq,received_at=at)
        self._bound(self.brti,key,item,self.max_brti_reads,'evicted_brti')
        self.max_retained_brti=max(self.max_retained_brti,len(self.brti))
        self.counts['ORIGINAL_BRTI_READS']+=1

    def _http(self,session,v,seq):
        received=v.get('received_at')
        endpoint=v.get('endpoint')
        if not number(received) or not isinstance(endpoint,str):
            raise ValueError('V81_LINKS_HTTP_CLOCK_OR_ORIGIN')
        if not endpoint.endswith('/products/BTC-USD/ticker'):
            return
        raw=base64.b64decode(v.get('raw_base64',''),validate=True)
        if sha(raw)!=v.get('sha256'):
            raise ValueError('V81_LINKS_ORIGINAL_BTC_RAW_HASH')
        try:parsed=json.loads(raw)
        except (ValueError,UnicodeError) as e:raise ValueError('V81_LINKS_BTC_JSON') from e
        if not isinstance(parsed,dict) or not isinstance(parsed.get('time'),str):
            raise ValueError('V81_LINKS_BTC_SOURCE_SCHEMA')
        if not isinstance(parsed.get('price'),(str,int,float)) or not math.isfinite(float(parsed['price'])):
            raise ValueError('V81_LINKS_BTC_PRICE_SCHEMA')
        key=(session,v['sha256'],received)
        item=dict(time=parsed['time'],price=float(parsed['price']),
                  sequence=seq,received_at=received)
        self._bound(self.http,key,item,self.max_original_http_receipts,'evicted_http')
        self.max_retained_http=max(self.max_retained_http,len(self.http))
        self.counts['ORIGINAL_COINBASE_TICKER_RECEIPTS']+=1

    def _input(self,session,v,seq):
        row=self._body(v)
        at=v.get('accepted_at')
        p=row.get('input_provenance')
        if not isinstance(p,dict) or p.get('schema')!='V81_TIMESTAMPED_INPUTS_V1':
            raise ValueError('V81_LINKS_ORIGINAL_INPUT_PROVENANCE')
        if not number(at) or not number(row.get('ts')) or row['ts']>at:
            raise ValueError('V81_LINKS_INPUT_OWNER_ACCEPTANCE_CLOCK')
        for field in ('btc_response_sha256','btc_received_at',
                      'brti_observation_sha256','brti_received_at'):
            if field not in v:raise ValueError('V81_LINKS_INPUT_RECEIPT:'+field)
        if not all(number(v[f]) and v[f]<=row['ts']
                   for f in ('btc_received_at','brti_received_at')):
            raise ValueError('V81_LINKS_ORIGINAL_SOURCE_RECEIPT_CUTOFF')
        # Identical production source qualification already enforces the
        # 5s BRTI, 6s Kalshi and 10s BTC source-age limits. Never loosen.
        try:require_qualified(row,row['ts'])
        except Exception as exc:
            raise ValueError('V81_LINKS_ORIGINAL_INPUT_NOT_QUALIFIED:'+str(exc)) from exc
        source_key=(session,v['btc_response_sha256'],v['btc_received_at'])
        btc=self.http.get(source_key)
        if btc is None:
            raise ValueError('V81_LINKS_EXACT_BTC_RESPONSE_MISSING')
        if btc['time']!=p['btc_source_utc'] or btc['price']!=row.get('btc'):
            raise ValueError('V81_LINKS_EXACT_BTC_PRICE_OR_TIME')
        if epoch(btc['time'])>v['btc_received_at']:
            raise ValueError('V81_LINKS_BTC_RECEIVED_BEFORE_SOURCE')
        brti=self.brti.get((session,v['brti_observation_sha256'],v['brti_received_at']))
        if brti is None:raise ValueError('V81_LINKS_EXACT_BRTI_READ_MISSING')
        b=brti['point']
        want={k:b.get(k) for k in ('value','source_ts_ms','owner_epoch',
                                  'sequence','status','clean_for_qualification')}
        if want!=p['brti'] or row.get('brti')!=b.get('value'):
            raise ValueError('V81_LINKS_EXACT_ORIGINAL_BRTI_FIELDS')
        if b['source_ts_ms']/1000>v['brti_received_at']:
            raise ValueError('V81_LINKS_BRTI_RECEIVED_BEFORE_SOURCE')
        # A ticker and strike cannot be inferred from response history:
        # the original official metadata must already be available.
        official=self.source._match_market('source',session,p['ticker'],
                 p['open_ts'],p['close_ts'],p['target'],row['ts'])
        # Previous exact accepted book state exists, from the same original
        # session and timestamped, contiguous Kalshi websocket, not REST.
        quoted=self.quote.match_native_v81_quote(session,p['quote'],row['ts'],
                                                  p['open_ts'],p['close_ts'])
        ident=sha(canonical(p))
        attempt=v.get('attempt_id')
        key=(session,ident,attempt)
        element=dict(original_sequence=seq,original_envelope_sha256=v['sha256'],
                     accepted_at=at,row=row,official_receipts=len(official),
                     quote_receipt=quoted,
                     btc_response_sha256=v['btc_response_sha256'],
                     brti_observation_sha256=v['brti_observation_sha256'])
        if key in self.inputs and self.inputs[key]!=element:
            raise ValueError('V81_LINKS_AMBIGUOUS_ATTEMPT_OR_PROVENANCE')
        self._bound(self.inputs,key,element,self.max_inputs,'evicted_inputs')
        self.max_retained_inputs=max(self.max_retained_inputs,len(self.inputs))
        self.counts['ORIGINAL_INPUT_ACCEPTED_FULLY_CAUSAL']+=1

    def _scalp(self,session,v,seq):
        n=self._body(v)
        if n.get('kind')!='SCALP_OBSERVATION':return
        if n.get('unavailable_reason'):
            self.counts['ORIGINAL_SCALP_UNAVAILABLE']+=1
            return
        p=n.get('provenance')
        if not isinstance(p,dict):
            raise ValueError('V81_LINKS_SCALP_PROVENANCE_MISSING')
        product=n.get('product')
        if not isinstance(product,dict):
            raise ValueError('V81_LINKS_ORIGINAL_PRODUCT_IDENTITY_MISSING')
        attempt=product.get('attempt_id')
        raw_input=self.inputs.get((session,sha(canonical(p)),attempt))
        if raw_input is None:
            raise ValueError('V81_LINKS_EXACT_V81_INPUT_OR_ATTEMPT_MISSING')
        at=n.get('published_ts');committed=v.get('committed_at')
        if not number(at) or not number(committed) or not (
            raw_input['row']['ts']<=raw_input['accepted_at']<=at<=committed):
            raise ValueError('V81_LINKS_NATIVE_PUBLICATION_OR_INPUT_CUTOFF')
        row=raw_input['row']
        if (n.get('contract')!=p.get('ticker') or
            row.get('ticker')!=p.get('ticker') or
            p.get('quote')!=row['input_provenance'].get('quote') or
            row.get('target')!=p.get('target') or
            row.get('brti')!=p['brti'].get('value') or
            any(row.get(k)!=p['quote'].get(k) for k in
                ('up_bid','up_ask','down_bid','down_ask'))):
            raise ValueError('V81_LINKS_NATIVE_CROSS_SOURCE_OR_PRICE_DRIFT')
        try:require_qualified(row,at)
        except Exception as exc:
            raise ValueError('V81_LINKS_NATIVE_PUBLICATION_STALE:'+str(exc)) from exc
        # Re-verify exact original accepted depth at native cut; accepting
        # a second later/rebased book with the same approximate price is forbidden.
        quote=self.quote.match_native_v81_quote(session,p['quote'],row['ts'],
                        p['open_ts'],p['close_ts'])
        receipt=dict(ticker=n['contract'],published_ts=at,
                     original_sequence=seq,
                     original_input_sequence=raw_input['original_sequence'],
                     quote_identity_sha256=quote['identity_sha256'],
                     original_quote_count=quote['original_accept_count'],
                     original_input_sha256=raw_input['original_envelope_sha256'],
                     original_native_sha256=v['sha256'],
                     literal_event=n.get('event'),
                     literal_guidance=n.get('guidance'))
        # Durable append is required before crediting a successful native
        # association; the original native entry and quote are never omitted.
        self._audit_native_receipt(receipt)
        self.counts['ORIGINAL_SCALP_FULL_CAUSAL_INPUT_AND_QUOTE']+=1
        # The original strategy proposal, entry/exit conditions, fee applicability,
        # native BUY origin and actual final settlement still require full verifier.
        self.counts['STRATEGY_OR_SETTLEMENT_NOT_YET_VALIDATED']+=1

    def accept(self,role,record):
        if role!='source':return
        k=record['kind']
        if k=='EVIDENCE_GAP' or k=='INFORMATION_FAILURE' or (
            k=='SOURCE_GAP' and record['payload'].get('reason')!='SOURCE_START_OR_EPOCH_CHANGE'):
            self.quarantined=True
            self.gaps+=1
        if self.quarantined:
            if k in ('V81_INPUT','NATIVE_RECORD'):
                self.counts['NATIVE_OR_INPUT_DISQUALIFIED_AFTER_GAP']+=1
            return
        p=record['payload']
        session=record['session']
        if k=='BRTI_READ':self._brti(session,p,record['sequence'])
        elif k=='ORIGINAL_RESPONSE':self._http(session,p,record['sequence'])
        elif k=='V81_INPUT':self._input(session,p,record['sequence'])
        elif k=='NATIVE_RECORD':self._scalp(session,p,record['sequence'])

    def checkpoint(self,role,session,original_sequence):
        if self.audit_file is not None:
            self.audit_file.flush()
            os.fsync(self.audit_file.fileno())
        self.checkpoints+=1
        result=dict(schema='BTC15_V81_CAUSAL_WINDOW_AUDIT_STAGE5_V1',
                    role=role,session=session,
                    last_original_sequence=original_sequence,
                    accepted_inputs=self.counts['ORIGINAL_INPUT_ACCEPTED_FULLY_CAUSAL'],
                    proven_native_scalp_inputs=self.counts['ORIGINAL_SCALP_FULL_CAUSAL_INPUT_AND_QUOTE'],
                    exact_btc_http_receipts=self.counts['ORIGINAL_COINBASE_TICKER_RECEIPTS'],
                    exact_brti_owner_reads=self.counts['ORIGINAL_BRTI_READS'],
                    carried_inputs=len(self.inputs),
                    carried_brti=len(self.brti),carried_http=len(self.http),
                    source_or_evidence_gaps=self.gaps,quarantined=self.quarantined,
                    complete_native_buy_exit_settlement_proven=False,
                    full_early_campaign_verified=False,
                    restart_resume_checkpoint_verified=False)
        result['audit_sha256']=sha(canonical(result))
        return result

    def finish(self):
        if self.audit_file is not None:
            self.audit_file.flush();os.fsync(self.audit_file.fileno())
            self.audit_file.close();self.audit_file=None
        if self.audit_path is not None:
            from ops.recording_workflow.evidence import file_sha
            self.audit_sha256=file_sha(self.audit_path)
        return dict(schema='BTC15_EXISTING_READER_V81_CAUSAL_STAGE5_V1',
                    original_evidence_counts=dict(self.counts),
                    original_source_or_capture_gaps=self.gaps,
                    quarantined_on_original_loss=self.quarantined,
                    max_retained_accepted_inputs=self.max_retained_inputs,
                    max_retained_original_brti=self.max_retained_brti,
                    max_retained_original_http=self.max_retained_http,
                    evicted_input_rows=self.evicted_inputs,
                    evicted_brti_read_rows=self.evicted_brti,
                    evicted_http_response_rows=self.evicted_http,
                    verified_native_receipts=self.verified,
                    verified_native_receipts_are_examples=True,
                    complete_native_association_count=self.total_original_native_matches,
                    durable_audit_file_bytes=self.audit_bytes,
                    durable_audit_file_sha256=self.audit_sha256,
                    durable_audit_complete_only_with_reader_manifest=True,
                    decision_inputs_qualified_but_strategy_not_independently_recomputed=
                        self.counts['ORIGINAL_SCALP_FULL_CAUSAL_INPUT_AND_QUOTE'],
                    original_lifecycle_and_settlement_verified=False,
                    full_campaign_verified=False,
                    signal_only=True,orders=False)