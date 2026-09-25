#!/usr/bin/env python3
"""Focused candidate checks. No network. NO ORDERS."""
import inspect, threading, unittest
from unittest.mock import patch
import btc15_kalshi_quote_provenance_offpath_candidate as q

TICKER='KXBTC15M-26SEP201315-15'; NOW=1790000000500; CLOSE=NOW+500000

def snapshot():
    return dict(type='orderbook_snapshot',sid=2,seq=2,msg=dict(
        market_ticker=TICKER,market_id='uuid-1',
        yes_dollars_fp=[['0.49','20']],no_dollars_fp=[['0.50','25']]))
def delta():
    return dict(type='orderbook_delta',sid=2,seq=3,msg=dict(
        market_ticker=TICKER,market_id='uuid-1',side='yes',
        price_dollars='.49',delta_fp='1',ts_ms=NOW-200))

class Candidate(unittest.TestCase):
    def provider(self):
        p=object.__new__(q.Provider); p.lock=threading.Lock(); p.ticker=TICKER
        p.book=q.Book(TICKER); p.book.apply(snapshot()); p.book.apply(delta())
        p.events=[snapshot(),delta()]; p.epoch='epoch'; p.close_ms=CLOSE
        class Sink:
            def __init__(self): self.items=[]
            def submit(self,w,e): self.items.append((w,tuple(e))); return True
        p.proof_writer=Sink(); return p

    def test_consume_has_no_json_or_disk_calls(self):
        source=inspect.getsource(q.Provider.consume)
        self.assertNotIn('json.dumps',source)
        self.assertNotIn('write_text',source)
        self.assertNotIn('.replace(',source)

    def test_consume_returns_same_quote_and_enqueues_witness(self):
        p=self.provider()
        with patch.object(q.time,'time',return_value=NOW/1000):
            self.assertEqual(p.consume(TICKER,'collector',CLOSE),(.49,.5,.5,.51))
        self.assertEqual(len(p.proof_writer.items),1)
        w,events=p.proof_writer.items[0]
        self.assertEqual(w.identity,['uuid-1',2,3,NOW-200])
        self.assertEqual(w.close_ms,CLOSE); self.assertEqual(len(events),2)

    def test_worker_validator_replays_exact_identity(self):
        p=self.provider()
        proof=dict(source_time='collector',ticker=TICKER,epoch='epoch',
                   consumed_ms=NOW,identity=['uuid-1',2,3,NOW-200],
                   events=[snapshot(),delta()])
        class W:
            source_time='collector';ticker=TICKER;close_ms=CLOSE;consumed_ms=NOW
        self.assertEqual(p._validate_offpath_proof(proof,W),['uuid-1',2,3,NOW-200])

if __name__=='__main__': unittest.main()
