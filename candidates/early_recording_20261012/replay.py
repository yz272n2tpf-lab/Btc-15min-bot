"""Mechanical depth/timing replay. Displayed quantities never establish a fill."""
import base64
import json
from btc15_kalshi_quote_provenance_v1 import Book
from .archive import sha, finite


def quote_chain(records):
    blobs={};received={};books={};states=[];gaps=[]
    for r in records:
        p=r['payload'];kind=r['kind'];session=r['session']
        if kind=='QUOTE_BYTES':
            raw=base64.b64decode(p['raw_base64'],validate=True)
            if sha(raw)!=p['sha256']:raise ValueError('QUOTE_BYTES_HASH')
            blobs[(session,p['sha256'])]=raw
        elif kind=='QUOTE_RECEIVE':
            received[(session,p['epoch'],p['raw_sha256'],p['received_at'])]=p
        elif kind=='QUOTE_ACCEPT':
            key=(session,p['epoch'],p['ticker'])
            try:
                receipt=received[(session,p['epoch'],p['raw_sha256'],p['received_at'])]
                if not finite(p['accepted_at']) or not finite(p['received_at']) or p['accepted_at']<p['received_at']:
                    raise ValueError('RECEIVE_ACCEPT_ORDER')
                event=json.loads(blobs[(session,p['raw_sha256'])])
                book=books.get(key)
                if event.get('type')=='orderbook_snapshot':
                    if book is not None and (event['sid']!=book.sid or event['seq']!=book.seq+1 or event['msg']['market_id']!=book.market_id):
                        gaps.append(dict(reason='SNAPSHOT_SEQUENCE_BREAK',epoch=p['epoch']))
                    book=Book(p['ticker']);books[key]=book
                if book is None:raise ValueError('NO_SNAPSHOT')
                book.apply(event)
                if book.ts_ms is not None and book.ts_ms/1000>p['received_at']:
                    raise ValueError('EXCHANGE_AFTER_RECEIVE')
                yes,no=book.levels['yes'],book.levels['no']
                state=dict(epoch=p['epoch'],ticker=p['ticker'],market_id=book.market_id,
                    sid=book.sid,seq=book.seq,exchange_ts_ms=book.ts_ms,
                    received_at=p['received_at'],accepted_at=p['accepted_at'],
                    raw_sha256=p['raw_sha256'],
                    levels={s:[[str(price),str(q)] for price,q in sorted(book.levels[s].items())] for s in ('yes','no')},
                    price_unit='USD_per_contract',quantity_unit='contracts',fill_evidence=False)
                if yes and no:
                    y,n=max(yes),max(no)
                    state['top']=dict(up_bid=str(y),up_bid_quantity=str(yes[y]),
                        up_ask=str(1-n),up_ask_quantity=str(no[n]),
                        down_bid=str(n),down_bid_quantity=str(no[n]),
                        down_ask=str(1-y),down_ask_quantity=str(yes[y]))
                states.append(state)
            except (ValueError,KeyError,TypeError) as exc:
                books.pop(key,None)
                gaps.append(dict(reason='QUOTE_RECONSTRUCTION_GAP',epoch=p['epoch'],detail=str(exc)))
        elif kind=='EVIDENCE_GAP':
            books.clear();gaps.append(dict(reason='CAPTURE_GAP_INVALIDATES_BOOKS',details=p))
        elif kind=='STREAM_END':
            books={k:v for k,v in books.items() if k[1]!=p['epoch']}
            gaps.append(dict(reason='STREAM_END',details=p))
    return dict(states=states,gaps=gaps,fill_evidence=False)


def proof_receipts(proof, records):
    chain=quote_chain(records)
    w=proof['witness'];states=chain['states']
    matches=[s for s in states if s['epoch']==w['epoch'] and s['ticker']==w['ticker']
             and [s['market_id'],s['sid'],s['seq'],s['exchange_ts_ms']]==
                 [w['market_id'],w['sid'],w['seq'],w['exchange_ts_ms']]
             and s['accepted_at']<=w['consumed_ms']/1000]
    # Identity alone is insufficient: quantities can change without changing seq.
    # Every replayed message must equal an originally received/accepted message.
    blobs={};receipts=set();accepted=[]
    for r in records:
        p=r['payload'];session=r['session']
        if r['kind']=='QUOTE_BYTES':
            raw=base64.b64decode(p['raw_base64'],validate=True)
            if sha(raw)!=p['sha256']:raise ValueError('QUOTE_BYTES_HASH')
            blobs[(session,p['sha256'])]=json.loads(raw)
        elif r['kind']=='QUOTE_RECEIVE':
            receipts.add((session,p['epoch'],p['raw_sha256'],p['received_at']))
        elif r['kind']=='QUOTE_ACCEPT':
            if (session,p['epoch'],p['raw_sha256'],p['received_at']) in receipts and p['epoch']==w['epoch'] and p['ticker']==w['ticker'] and p['received_at']<=p['accepted_at']<=w['consumed_ms']/1000:
                accepted.append((session,blobs.get((session,p['raw_sha256']))))
    complete=any(all((s,e) in accepted for e in proof['value']['events']) for s in {s for s,e in accepted})
    supported=bool(matches) and complete
    return dict(proof_sha256=proof['proof_sha256'],witness=w,
                timing_verified=supported,
                missing=[] if supported else ['NO_EXACT_RECEIVED_ACCEPTED_WITNESS_OR_EVENT_BYTES'],
                fill_evidence=False)
