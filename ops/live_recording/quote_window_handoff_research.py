"""Research-only bounded quote-state handoff for the EXISTING native reader.

Consumes already hash-validated original recorder envelopes from
ops.recording_workflow.evidence.streaming_window_inventory. Uses the SAME
btc15_kalshi_quote_provenance_v1.Book parser used by CampaignVerifier.
No new quote provider, live feed, market polling, strategy, order or freshness
threshold. Produces auditable state hashes, never a trade/qualification result.

One original QUOTE_BYTES may be referenced by QUOTE_RECEIVE and QUOTE_ACCEPT.
A bounded LRU holds original wire bytes; an exact receive identity holds the
unaccepted event. On cache overflow, unresolved receipt, or sequence violation
this fails closed, rather than reconstructing missing observations.
"""
import base64
from collections import Counter, OrderedDict
from decimal import Decimal
import json

from btc15_kalshi_quote_provenance_v1 import Book
from ops.live_recording.policy import canonical,sha

MiB=1024**2


class QuoteWindowHandoff:
    def __init__(self, *, max_books=16, max_raw_bytes=16*MiB,
                 max_pending=4096, max_requests=512):
        if not 1<=max_books<=64 or not 1*MiB<=max_raw_bytes<=64*MiB:
            raise ValueError('QUOTE_HANDOFF_BOOK_OR_RAW_BUDGET')
        if not 1<=max_pending<=16384 or not 1<=max_requests<=4096:
            raise ValueError('QUOTE_HANDOFF_PENDING_BUDGET')
        self.max_books=max_books
        self.max_raw_bytes=max_raw_bytes
        self.max_pending=max_pending
        self.max_requests=max_requests
        self.books={}
        self.receives={}
        self.requests={}
        self.raws=OrderedDict()
        self.raw_size=0
        self.counts=Counter()
        self.quarantined=False
        self.gap_count=0
        self.max_books_used=0
        self.max_pending_used=0
        self.max_raw_used=0
        self.checkpoints=0
        self.proven_valid_prefix=0
        self.streams_open_at_end=0
        self.last_record_sha256=None

    def _raw(self,digest):
        if digest not in self.raws:
            raise ValueError('QUOTE_HANDOFF_ORIGINAL_RAW_MISSING')
        blob=self.raws[digest]
        self.raws.move_to_end(digest)
        return blob

    def _save_raw(self,digest,blob):
        if not isinstance(blob,bytes) or sha(blob)!=digest:
            raise ValueError('QUOTE_HANDOFF_RAW_SHA')
        if len(blob)>self.max_raw_bytes:
            raise ValueError('QUOTE_HANDOFF_SINGLE_RAW_OVER_CAP')
        if digest in self.raws:
            if self.raws[digest]!=blob:
                raise ValueError('QUOTE_HANDOFF_RAW_COLLISION')
            self.raws.move_to_end(digest)
            return
        while self.raws and self.raw_size+len(blob)>self.max_raw_bytes:
            _,previous=self.raws.popitem(last=False)
            self.raw_size-=len(previous)
        self.raws[digest]=blob
        self.raw_size+=len(blob)
        self.max_raw_used=max(self.max_raw_used,self.raw_size)

    @staticmethod
    def _state(book):
        # Exchange state exactly as parsed by the original Book class.
        # This is an audit checkpoint, not a synthesized quote publication.
        value=dict(ticker=book.ticker,market_id=book.market_id,
                   sid=book.sid,seq=book.seq,ts_ms=book.ts_ms,
                   valid=book.valid,last=book.last,
                   levels={side:[[str(price),str(quantity)] for price,quantity in
                                 sorted(book.levels[side].items())]
                           for side in ('yes','no')})
        return value

    def accept(self, role, record):
        if role not in ('source','information'):
            raise ValueError('QUOTE_HANDOFF_ROLE')
        kind=record['kind']
        source_session=record['session']
        self.last_record_sha256=record['sha256']
        if kind=='EVIDENCE_GAP':
            self.gap_count+=1
            self.quarantined=True
            self.counts['evidence_gap_envelopes']+=1
        if self.quarantined:
            if kind.startswith('QUOTE_'):
                self.counts['unreplayable_quote_envelopes_after_gap']+=1
            return

        value=record['payload']
        if kind=='QUOTE_BYTES':
            try:
                raw=base64.b64decode(value['raw_base64'],validate=True)
                digest=value['sha256']
            except (KeyError,ValueError) as e:
                raise ValueError('QUOTE_HANDOFF_ORIGINAL_RAW_INVALID') from e
            self._save_raw(digest,raw)
            self.counts['original_raw_envelopes']+=1
            return
        if kind=='STREAM_START':
            epoch=value['epoch'];ticker=value['ticker']
            if not isinstance(epoch,str) or not epoch or not isinstance(ticker,str) or not ticker:
                raise ValueError('QUOTE_HANDOFF_STREAM_IDENTITY')
            key=(source_session,epoch,ticker)
            if key in self.books or len(self.books)>=self.max_books:
                raise ValueError('QUOTE_HANDOFF_DUPLICATE_OR_TOO_MANY_STREAMS')
            self.books[key]=Book(ticker)
            self.max_books_used=max(self.max_books_used,len(self.books))
            self.counts['stream_starts']+=1
            return
        if kind=='STREAM_END':
            key=(source_session,value['epoch'],value['ticker'])
            if key not in self.books:
                raise ValueError('QUOTE_HANDOFF_END_WITHOUT_START')
            self.books.pop(key)
            for k in list(self.receives):
                if k[:3]==key:
                    self.receives.pop(k)
                    self.counts['unaccepted_at_stream_end']+=1
            self.counts['stream_ends']+=1
            return
        if kind=='QUOTE_REQUEST':
            wire=self._raw(value['raw_sha256'])
            request=json.loads(wire)
            if not isinstance(request,dict) or 'id' not in request:
                raise ValueError('QUOTE_HANDOFF_REQUEST_SCHEMA')
            if request.get('cmd')=='update_subscription':
                key=(source_session,value.get('epoch'),request['id'])
                if key in self.requests or len(self.requests)>=self.max_requests:
                    raise ValueError('QUOTE_HANDOFF_REQUEST_LIMIT')
                self.requests[key]=dict(request=request,sent_at=value['sent_at'])
            self.counts['quote_requests']+=1
            return
        if kind=='QUOTE_RECEIVE':
            # Receipt identity in the original verifier must be EXACT.
            ticker=value['ticker'];epoch=value['epoch']
            stream_key=(source_session,epoch,ticker)
            if stream_key not in self.books:
                raise ValueError('QUOTE_HANDOFF_RECEIVE_OUTSIDE_STREAM')
            wire=self._raw(value['raw_sha256'])
            event=json.loads(wire)
            if not isinstance(event,dict):
                raise ValueError('QUOTE_HANDOFF_RECEIVE_EVENT_SCHEMA')
            key=(*stream_key,value['raw_sha256'],value['received_at'])
            if key in self.receives or len(self.receives)>=self.max_pending:
                raise ValueError('QUOTE_HANDOFF_RECEIVE_DUPLICATE_OR_LIMIT')
            self.receives[key]=event
            self.max_pending_used=max(self.max_pending_used,len(self.receives))
            self.counts['quote_receives']+=1
            return
        if kind=='QUOTE_ACCEPT':
            stream_key=(source_session,value['epoch'],value['ticker'])
            book=self.books.get(stream_key)
            if book is None:
                raise ValueError('QUOTE_HANDOFF_ACCEPT_OUTSIDE_STREAM')
            key=(*stream_key,value['raw_sha256'],value['received_at'])
            if key not in self.receives:
                raise ValueError('QUOTE_HANDOFF_ACCEPT_WITHOUT_EXACT_RECEIPT')
            if not value['received_at']<=value['accepted_at']:
                raise ValueError('QUOTE_HANDOFF_RECEIPT_AFTER_ACCEPTANCE')
            event=self.receives.pop(key)
            previous=book
            kind=event.get('type')
            rebasing=kind=='orderbook_snapshot' and previous.seq is not None
            if rebasing or kind=='ok':
                request=self.requests.get((source_session,value['epoch'],event.get('id')))
                if request is None:
                    raise ValueError('QUOTE_HANDOFF_REBASE_OR_ACK_REQUEST_MISSING')
                cmd=request['request']
                params=cmd.get('params') or {}
                if (cmd.get('cmd')!='update_subscription' or
                        params.get('action')!='get_snapshot' or
                        params.get('market_tickers')!=[value['ticker']] or
                        request['sent_at']>value['received_at']):
                    raise ValueError('QUOTE_HANDOFF_REQUEST_PROVENANCE')
                if rebasing:
                    if (event.get('sid')!=previous.sid or
                            event.get('seq')!=previous.seq+1 or
                            event.get('msg',{}).get('market_id')!=previous.market_id or
                            params.get('sid')!=previous.sid):
                        raise ValueError('QUOTE_HANDOFF_REBASE_SEQUENCE')
                    book=Book(value['ticker'])
                    self.books[stream_key]=book
                    self.counts['verified_rebases']+=1
                if kind=='ok' and 'sid' not in event and 'seq' not in event:
                    self.counts['unsequenced_protocol_acknowledgments']+=1
                    return
            try:
                book.apply(event)
            except Exception as exc:
                raise ValueError('QUOTE_HANDOFF_CONTIGUOUS_BOOK_REPLAY') from exc
            self.counts['quote_accepts']+=1
            if kind=='orderbook_delta':
                self.counts['verified_deltas']+=1
            elif kind=='orderbook_snapshot':
                self.counts['verified_snapshots']+=1
            self.proven_valid_prefix+=1

    def checkpoint(self, role, session, last_record_sequence):
        # Do not serialize the entire quote/raw byte stream. The original
        # worker continues holding bounded state in memory across windows.
        # Checkpoint hashes describe *actual* live replay state. The worker
        # cannot resume from this hash alone following a crash.
        states=[]
        for (s,epoch,ticker),book in sorted(self.books.items()):
            if s!=session:continue
            state=self._state(book)
            states.append(dict(epoch=epoch,ticker=ticker,
                               market_id=book.market_id,sid=book.sid,seq=book.seq,
                               exchange_ts_ms=book.ts_ms,
                               book_state_sha256=sha(canonical(state))))
        self.checkpoints+=1
        payload=dict(schema='BTC15_QUOTE_WINDOW_HANDOFF_AUDIT_V1',
                     role=role,session=session,last_original_sequence=last_record_sequence,
                     open_books=states,queued_exact_receives=sum(k[0]==session for k in self.receives),
                     carried_raw_lru_bytes=self.raw_size,
                     original_quote_receives=self.counts['quote_receives'],
                     original_quote_accepts=self.counts['quote_accepts'],
                     contiguous_book_events=self.proven_valid_prefix,
                     original_capture_gaps=self.gap_count,
                     quarantined_on_gap=self.quarantined,
                     checkpoint_is_recoverable=False,
                     association_qualified=False,
                     native_early_qualified=False)
        payload['audit_sha256']=sha(canonical(payload))
        return payload

    def finish(self):
        self.streams_open_at_end=len(self.books)
        return dict(schema='BTC15_QUOTE_HANDOFF_STAGE2_RESEARCH_V1',
                    original_message_counts=dict(self.counts),
                    original_evidence_gap_envelopes=self.gap_count,
                    contiguous_book_events_before_first_gap=self.proven_valid_prefix,
                    max_open_books=self.max_books_used,
                    max_exact_unaccepted_receives=self.max_pending_used,
                    max_original_raw_cache_bytes=self.max_raw_used,
                    audit_checkpoints=self.checkpoints,
                    open_streams_at_recording_stop=self.streams_open_at_end,
                    quarantined_on_evidence_loss=self.quarantined,
                    original_quote_state_replay='INCOMPLETE_GAP' if self.quarantined else 'BOUNDED_REPLAY_COMPLETE_FOR_AVAILABLE_INPUT',
                    whole_campaign_qualified=False,
                    native_early_qualified=False,
                    quote_state_restart_checkpoint_verified=False,
                    production_changed=False,orders=False)
