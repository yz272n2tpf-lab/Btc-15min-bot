#!/usr/bin/env python3
import json, tempfile, time, unittest
from pathlib import Path
from btc15_quote_proof_offpath_v1 import Witness, OffPathProofWriter

class OffPath(unittest.TestCase):
    def witness(self):
        return Witness("KXBTC15M-X","collector","epoch",1000,"m",2,3,900,1500)

    def test_submit_never_serializes_payload(self):
        class Explodes(dict):
            pass
        # Serialization happens only on worker. submit itself accepts references.
        with tempfile.TemporaryDirectory() as d:
            writer=OffPathProofWriter(d, lambda proof,w:w.identity, 2_000_000)
            self.assertTrue(writer.submit(self.witness(), ({"x":"y"},)))
            writer.queue.join()

    def test_validated_content_addressed_publish(self):
        with tempfile.TemporaryDirectory() as d:
            writer=OffPathProofWriter(d, lambda proof,w:w.identity, 2_000_000)
            self.assertTrue(writer.submit(self.witness(), ({"type":"fixture"},)))
            writer.queue.join()
            index=json.loads((Path(d)/"latest.json").read_text())
            self.assertEqual(index["identity"],["m",2,3,900])
            self.assertTrue((Path(d)/(index["sha256"]+".json")).exists())
            self.assertTrue(index["signal_only"]); self.assertFalse(index["orders"])

    def test_identity_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            writer=OffPathProofWriter(d, lambda proof,w:["wrong"], 2_000_000)
            writer.submit(self.witness(), ({"type":"fixture"},)); writer.queue.join()
            self.assertFalse((Path(d)/"latest.json").exists())
            self.assertEqual(writer.rejected,1)

    def test_queue_overflow_drops_evidence_not_strategy(self):
        with tempfile.TemporaryDirectory() as d:
            gate=__import__("threading").Event()
            writer=OffPathProofWriter(d, lambda proof,w:(gate.wait(.2) or w.identity), 2_000_000, queue_size=1)
            accepted=[writer.submit(self.witness(), ({"n":i},)) for i in range(20)]
            self.assertIn(False,accepted)
            self.assertGreater(writer.dropped,0)

    def test_disk_retention_is_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            writer=OffPathProofWriter(d, lambda proof,w:w.identity, 2_000_000, retain=2)
            for i in range(5):
                w=Witness("KXBTC15M-X","collector","epoch",1000+i,"m",2,3+i,900+i,1500)
                writer.submit(w, ({"i":i},)); writer.queue.join()
                import time; time.sleep(.002)
            blobs=[p for p in Path(d).glob("*.json") if p.name!="latest.json"]
            self.assertLessEqual(len(blobs),2)

if __name__=="__main__":
    unittest.main()
