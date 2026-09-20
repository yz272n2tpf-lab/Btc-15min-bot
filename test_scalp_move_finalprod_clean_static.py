#!/usr/bin/env python3
"""Static qualification for clean final-production ladder collector. NO ORDERS."""
import ast, base64, gzip, hashlib
from pathlib import Path
import unittest

V1="3fdb2ef60f184e1ce2cef306c1db2a9de03b3e7b1a27c32b6bfffabb2cf60c48"
V2="52b79e239c0be2b5ece93e3387063185ce51be8a01413f6b76bc5939924fb3ad"

class CleanCollector(unittest.TestCase):
    def test_frozen_v1_and_v2_fingerprints(self):
        src=Path("scalp_move_shadow_v1.py").read_text()
        tree=ast.parse(src)
        payload=next(ast.literal_eval(n.value) for n in tree.body
                     if isinstance(n,ast.Assign)
                     and any(isinstance(t,ast.Name) and t.id=="PAYLOAD" for t in n.targets))
        raw=gzip.decompress(base64.b64decode(payload)).decode()
        self.assertEqual(hashlib.sha256(raw.encode()).hexdigest(),V1)
        reps=(
          ("PRICE-AGNOSTIC BTC15 SCALP MOVE SHADOW V1","PRICE-AGNOSTIC BTC15 SCALP MOVE SHADOW V2 FULL-TIME"),
          ("MIN_LEFT = 120.0","MIN_LEFT = 0.0"),
          ("MOVE_BASED_PRICE_AGNOSTIC|SIGNAL_ONLY|NO_ORDERS","MOVE_BASED_PRICE_AGNOSTIC|FULL_TIME_V2|SIGNAL_ONLY|NO_ORDERS"),
          ("PATH_TELEMETRY|PRICE_AGNOSTIC|NO_ORDERS","PATH_TELEMETRY|PRICE_AGNOSTIC|FULL_TIME_V2|NO_ORDERS"),
          ("SHADOW_RESULT|PRICE_BUCKET_TELEMETRY_ONLY|NO_ORDERS","SHADOW_RESULT|PRICE_BUCKET_TELEMETRY_ONLY|FULL_TIME_V2|NO_ORDERS"),
          ("SCALP MOVE SHADOW V1 START | PRICE-AGNOSTIC | EXECUTABLE ASK->BID | ","SCALP MOVE SHADOW V2 START | PRICE-AGNOSTIC | FULL-TIME 15:00->0:00 | EXECUTABLE ASK->BID | "),
        )
        for a,b in reps:
            self.assertEqual(raw.count(a),1); raw=raw.replace(a,b)
        self.assertEqual(hashlib.sha256(raw.encode()).hexdigest(),V2)

    def test_wrapper_changes_source_not_detector_thresholds(self):
        s=Path("scalp_move_shadow_v2_finalprod_clean.py").read_text()
        self.assertIn("read_shared_brti",s)
        self.assertIn("consume_ws_quotes",s)
        self.assertIn('p.get("status") == "PASS"',s)
        self.assertIn('"quote_match", "brti_match"',s)
        self.assertIn("V2_SHA256",s)
        self.assertNotIn("requests.post",s)
        self.assertNotIn("/portfolio/orders",s)

    def test_signal_only_export_bridge(self):
        s=Path("scalp_path_export_bridge_v1.py").read_text()
        self.assertIn("GET only",s)
        self.assertNotIn("do_POST",s)
        self.assertIn("orders",s)

if __name__=="__main__":
    unittest.main(verbosity=2)
