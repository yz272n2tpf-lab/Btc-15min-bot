#!/usr/bin/env python3
"""Timing/adversarial qualification for off-path quote capture. NO ORDERS."""
import tempfile, threading, time, unittest
from pathlib import Path
from unittest.mock import patch
import btc15_kalshi_quote_provenance_offpath_candidate as q

T='KXBTC15M-26SEP201315-15'; NOW=1790000000500; CLOSE=NOW+500000

def snapshot():
    return dict(type='orderbook_snapshot',sid=2,seq=2,msg=dict(market_ticker=T,market_id='m',
        yes_dollars_fp=[['.49','20']],no_dollars_fp=[['.50','20']]))
def delta(seq=3,ts=NOW-200,pad=0):
    d=dict(type='orderbook_delta',sid=2,seq=seq,msg=dict(market_ticker=T,market_id='m',
        side='yes',price_dollars='.49',delta_fp='1',ts_ms=ts))
    if pad:d['msg']['fixture_padding']='x'*pad
    return d

class Sink:
    def __init__(self,accept=True):self.accept=accept;self.items=[]
    def submit(self,w,e):self.items.append((w,tuple(e)));return self.accept

def provider(events=None):
    p=object.__new__(q.Provider);p.lock=threading.Lock();p.ticker=T;p.close_ms=CLOSE
    p.book=q.Book(T);p.book.apply(snapshot());p.book.apply(delta())
    p.events=events if events is not None else [snapshot(),delta()]
    p.epoch='epoch';p.proof_writer=Sink();return p

class Timing(unittest.TestCase):
    def test_large_proof_not_serialized_before_return(self):
        # Approximate the previously problematic megabyte-scale retained proof.
        events=[snapshot(),delta()]
        for i in range(4,804):
            events.append(delta(seq=i,ts=NOW-200+i-3,pad=1600))
        p=provider(events)
        import json
        with patch.object(q.time,'time',return_value=NOW/1000), patch.object(q.json,'dumps',side_effect=AssertionError('native serialization')):
            start=time.perf_counter_ns();out=p.consume(T,'collector',CLOSE);elapsed=time.perf_counter_ns()-start
        self.assertEqual(out,(.49,.5,.5,.51));self.assertEqual(len(p.proof_writer.items),1)
        # Not a production latency SLA: catches accidental reintroduction of MB serialization.
        self.assertLess(elapsed,5_000_000)

    def test_queue_rejection_does_not_change_quote(self):
        p=provider();p.proof_writer=Sink(False)
        with patch.object(q.time,'time',return_value=NOW/1000):
            self.assertEqual(p.consume(T,'collector',CLOSE),(.49,.5,.5,.51))

    def test_mutated_event_reference_fails_worker_replay(self):
        p=provider();events=[snapshot(),delta()]
        proof=dict(source_time='collector',ticker=T,epoch='epoch',consumed_ms=NOW,
                   identity=['m',2,3,NOW-200],events=events)
        events[-1]['seq']=99
        class W:source_time='collector';ticker=T;close_ms=CLOSE;consumed_ms=NOW
        with self.assertRaises(ValueError):p._validate_offpath_proof(proof,W)

    def test_rollover_still_clears_before_use(self):
        p=provider()
        self.assertIsNone(p.consume('NEXT','collector',CLOSE+900000));self.assertIsNone(p.book)

if __name__=='__main__':unittest.main()
