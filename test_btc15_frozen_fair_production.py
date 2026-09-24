import ast
import hashlib
from pathlib import Path
import unittest

from completion_audit.frozen_model_artifact import load_verified


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "bot_two_output_build_v4_13_profit_protection_shadow.py"
ARTIFACT = ROOT / "completion_audit/model_artifact/frozen_fair_candidate.joblib"
ARTIFACT_SHA = "1bf10e755fc81584bab3c3682b16103353f84582c27bb003664de883e7e7c816"
WEIGHTS_SHA = "95fc4e893c9032f29b9732d03c4a2e0cd62755ba93b36106a1d0c8c094520ba6"


class FrozenFairProductionTests(unittest.TestCase):
    def test_artifact_has_registered_byte_and_weight_identity(self):
        self.assertEqual(hashlib.sha256(ARTIFACT.read_bytes()).hexdigest(), ARTIFACT_SHA)
        model = load_verified(
            ARTIFACT,
            expected_artifact_sha256=ARTIFACT_SHA,
            expected_weights_sha256=WEIGHTS_SHA,
        )
        self.assertEqual(model["weights_sha256"], WEIGHTS_SHA)
        self.assertEqual(model["forest"].n_jobs, 1)

    def test_production_source_parses_and_never_refits_fair_model(self):
        text = SOURCE.read_text()
        ast.parse(text)
        fair = text.split("# === RESTORED TARGET-AWARE FAIR-VALUE ENTRY ENGINE START ===", 1)[1]
        fair = fair.split("# === RESTORED TARGET-AWARE FAIR-VALUE ENTRY ENGINE END ===", 1)[0]
        self.assertNotIn("_fair_rf.fit(", fair)
        self.assertNotIn("_fair_sigmoid.fit(", fair)
        self.assertIn("_fair_load_verified(", fair)
        self.assertIn("_fair_completed_candles(_fair_raw_btc)", fair)
        self.assertIn("FAIR MODEL FEATURE IDENTITY MISMATCH", fair)

    def test_live_partial_ticks_keep_source_and_receipt_clocks(self):
        text = SOURCE.read_text()
        self.assertIn('data.get("time")', text)
        self.assertIn('"source_utc": source', text)
        self.assertIn('"observed_utc": observed', text)
        self.assertIn("_fair_frame_at_cut(_fair_btc, _ec_live_ticks(), _cut)", text)
        self.assertIn("BTC tick source timestamp unqualified", text)

    def test_signal_only_identity_is_logged(self):
        text = SOURCE.read_text()
        self.assertIn("fair_model_weights_sha256", text)
        self.assertIn("fair_model_artifact_sha256", text)
        self.assertIn("NO STARTUP FIT", text)


if __name__ == "__main__":
    unittest.main()
