import unittest
from datetime import datetime, timedelta, timezone

import scalp_opportunity_quality_frontier_v1 as q


def ts(base, sec):
    return (base + timedelta(seconds=sec)).isoformat()


def candidate(base, cid="c1", contract="K1", ask="0.20", left="600", btc30="20"):
    return {
        "timestamp_utc": ts(base, 0), "record_type": "CANDIDATE", "candidate_id": cid,
        "contract": contract, "side": "UP", "entry_ask": ask, "entry_bid": "0.19",
        "spread": "0.01", "seconds_left": left, "btc30": btc30,
        "btc_move5_side": "8", "btc_move15_side": "14", "btc_move30_side": btc30,
        "brti_move5_side": "7", "brti_move15_side": "12", "ask_move5": "0.01",
        "ask_move15": "0.02", "acceleration": "2", "confirm_count": "2",
        "recent_range60": "50", "btc_move5_norm": "0.16", "btc_move15_norm": "0.28",
        "brti_latency_sec": "0.2", "brti_attempts": "1", "structure_ok": "True",
        "btc_against_side": "False", "brti_against_side": "False",
        "dual_reversal_evidence": "False", "brti_status": "PRIMARY_OK",
        "max_possible_upside": str(1 - float(ask)),
    }


def path(base, cid, sec, gain, ask="0.40", bid=None, contract="K1"):
    if bid is None:
        bid = float(ask) + gain
    return {
        "timestamp_utc": ts(base, sec), "record_type": "PATH", "candidate_id": cid,
        "contract": contract, "elapsed_sec": str(sec), "exec_gain": str(gain),
        "current_ask": str(ask), "current_bid": str(bid),
    }


def result(base, cid, sec=180, contract="K1"):
    return {"timestamp_utc": ts(base, sec), "record_type": "RESULT", "candidate_id": cid, "contract": contract}


class TestScalpQualityFrontier(unittest.TestCase):
    def test_feature_list_is_causal(self):
        q.assert_integrity()
        joined = " ".join(q.FEATURES).lower()
        for token in q.FORBIDDEN:
            self.assertNotIn(token, joined)

    def test_entry_price_does_not_control_baseline_qualification(self):
        base = datetime(2026, 9, 15, tzinfo=timezone.utc)
        cheap = candidate(base, ask="0.01")
        rich = candidate(base, ask="0.99")
        self.assertTrue(q.baseline_qualified(cheap))
        self.assertTrue(q.baseline_qualified(rich))

    def test_verify_uses_then_current_ask_not_original_ask(self):
        base = datetime(2026, 9, 15, tzinfo=timezone.utc)
        c = candidate(base, ask="0.20")
        rows = [
            path(base, "c1", 15, 0.00, ask="0.40", bid=0.39),
            path(base, "c1", 30, 0.00, ask="0.40", bid=0.48),
        ]
        # Original 20c -> 48c would look like +28c, but a real 15s verification
        # enters at 40c, so the executable move is only +8c and must NOT hit +10.
        x = q.verify_entry(c, rows, 15)
        self.assertIsNotNone(x)
        self.assertAlmostEqual(x["entry_ask"], 0.40)
        self.assertEqual(x["plus10"], 0)
        rows.append(path(base, "c1", 45, 0.00, ask="0.40", bid=0.51))
        y = q.verify_entry(c, rows, 15)
        self.assertEqual(y["plus10"], 1)
        self.assertAlmostEqual(y["peak_gain"], 0.11)

    def test_serial_ladder_resets_only_after_protected_exit(self):
        base = datetime(2026, 9, 15, tzinfo=timezone.utc)
        c1 = candidate(base, cid="c1", contract="K1")
        c2 = candidate(base + timedelta(seconds=50), cid="c2", contract="K1")
        # c1 arms +5 and then gives back >=4c at 40s -> protected exit.
        p1 = [path(base, "c1", 10, .03), path(base, "c1", 20, .06), path(base, "c1", 40, .01)]
        p2 = [path(base + timedelta(seconds=50), "c2", 10, .11)]
        rows = [c1, *p1, result(base, "c1"), c2, *p2, result(base + timedelta(seconds=50), "c2")]
        opps = q.build_serial_opportunities(rows)
        self.assertEqual(len(opps), 2)
        self.assertEqual([o["opportunity_index"] for o in opps], [1, 2])

    def test_failed_prearm_blocks_later_serial_opportunity(self):
        base = datetime(2026, 9, 15, tzinfo=timezone.utc)
        c1 = candidate(base, cid="c1", contract="K1")
        c2 = candidate(base + timedelta(seconds=60), cid="c2", contract="K1")
        p1 = [path(base, "c1", 20, .02), path(base, "c1", 60, -.03)]  # never arms
        p2 = [path(base + timedelta(seconds=60), "c2", 20, .15)]
        rows = [c1, *p1, result(base, "c1"), c2, *p2, result(base + timedelta(seconds=60), "c2")]
        opps = q.build_serial_opportunities(rows)
        self.assertEqual(len(opps), 1)
        self.assertEqual(opps[0]["candidate_id"], "c1")


if __name__ == "__main__":
    unittest.main()
