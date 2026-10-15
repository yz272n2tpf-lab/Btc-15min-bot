"""Offline research acceptance: 10 sequential contract boundaries and durable outbox receipts.

This is a synthetic rollover/recovery check, NOT Kalshi source-clock equivalence.
"""
import sqlite3
import unittest
from .test_v11_outbox_actual_worker_bridge import Tests as BridgeTests
from .btc15_v10_receipt_readback_research import verify_receipt

class TenRolloverAcceptance(BridgeTests):
    def test_ten_consecutive_15m_contract_boundaries(self):
        # Ten successive 900-second boundaries, 11 distinct contracts.
        # No market source or trading-model execution occurs in this test.
        start=1792108800
        contracts=['BTC15-%d'%(start+900*i) for i in range(11)]
        self.insert(contracts[0])
        for contract in contracts[1:]:
            self.insert(contract)
        completed=self.dispatch()
        self.assertEqual(completed,['A']+contracts)
        self.assertEqual(len(self.rows()),12)
        self.assertEqual(len(set(r['contract'] for r in self.rows())),12)
        self.assertEqual([int(x.split('-')[1]) for x in contracts],
                         [start+900*i for i in range(11)])
        for i,contract in enumerate(contracts):
            settlement=dict(final60_side='UP',final60_count=60,final60_complete=True)
            receipt=verify_receipt(self.root/'main.sqlite3',contract,settlement)
            self.assertEqual(receipt['sequence'],i+2)
        self.assertEqual(self.dispatch(),[])
        self.assertEqual(len(self.rows()),12)
    def test_pending_after_ack_interruption_then_restart(self):
        def interrupt(stage,contract):
            if stage=='AFTER_JOURNAL':raise RuntimeError('RESEARCH_INTERRUPTION')
        with self.assertRaises(RuntimeError):self.dispatch(interrupt)
        self.worker.queue.put(None);self.worker.thread.join(timeout=5)
        from btc15_v2_product.journal import RevisionWorker
        from .test_v9_actual_worker_receipts import Processor
        self.worker=RevisionWorker(self.root,'main',Processor())
        self.assertEqual(self.dispatch(),['A'])
        self.assertEqual(self.pending(),[('A',1)])
        self.assertEqual(len(self.rows()),1)

if __name__=='__main__':unittest.main()
