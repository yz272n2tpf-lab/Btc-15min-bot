import unittest

import BTC15_SCALP_UNARMED_TERMINAL_HANDOFF_AUDIT_V1 as auditmod


def c(ts, cid, contract="KXBTC15M-26SEP150000-00", ask="0.31", side="UP", left="600", btc30="20"):
    return {
        "record_type": "CANDIDATE",
        "timestamp_utc": ts,
        "candidate_id": cid,
        "contract": contract,
        "entry_ask": ask,
        "side": side,
        "seconds_left": left,
        "btc30": btc30,
    }


def p(ts, cid, gain, elapsed, contract="KXBTC15M-26SEP150000-00"):
    return {
        "record_type": "PATH",
        "timestamp_utc": ts,
        "candidate_id": cid,
        "contract": contract,
        "exec_gain": str(gain),
        "elapsed_sec": str(elapsed),
    }


def r(ts, cid, contract="KXBTC15M-26SEP150000-00"):
    return {
        "record_type": "RESULT",
        "timestamp_utc": ts,
        "candidate_id": cid,
        "contract": contract,
    }


class UnarmedTerminalHandoffAuditTests(unittest.TestCase):
    def test_unarmed_result_becomes_informational_terminal_and_exposes_next(self):
        rows = [
            c("2026-09-15T00:00:00Z", "a"),
            p("2026-09-15T00:00:10Z", "a", -0.02, 10),
            p("2026-09-15T00:00:30Z", "a", 0.02, 30),
            r("2026-09-15T00:01:00Z", "a"),
            c("2026-09-15T00:01:10Z", "b", ask="0.44", side="DOWN"),
            p("2026-09-15T00:01:20Z", "b", 0.12, 10),
            p("2026-09-15T00:01:30Z", "b", 0.07, 20),
            r("2026-09-15T00:02:00Z", "b"),
        ]
        out = auditmod.audit(rows)
        self.assertEqual(out["ended_unarmed_n"], 1)
        self.assertEqual(out["post_unarmed_later_qualified_n"], 1)
        self.assertEqual(out["post_unarmed_later_completed_n"], 1)
        self.assertEqual(out["post_unarmed_later_plus10_n"], 1)
        self.assertFalse(out["ended_unarmed_is_actionable_exit"])
        self.assertFalse(out["orders"])

    def test_high_price_candidate_is_not_filtered(self):
        rows = [
            c("2026-09-15T00:00:00Z", "a"),
            p("2026-09-15T00:00:15Z", "a", 0.01, 15),
            r("2026-09-15T00:00:45Z", "a"),
            c("2026-09-15T00:00:50Z", "b", ask="0.86", side="DOWN"),
            p("2026-09-15T00:01:00Z", "b", 0.11, 10),
            p("2026-09-15T00:01:10Z", "b", 0.06, 20),
            r("2026-09-15T00:01:30Z", "b"),
        ]
        out = auditmod.audit(rows)
        self.assertEqual(out["post_unarmed_later_qualified_n"], 1)
        self.assertAlmostEqual(out["recovered_handoffs"][0]["to_entry_ask"], 0.86)
        self.assertFalse(out["entry_price_filter_applied"])

    def test_incomplete_unarmed_candidate_does_not_fabricate_terminal(self):
        rows = [
            c("2026-09-15T00:00:00Z", "a"),
            p("2026-09-15T00:00:15Z", "a", -0.10, 15),
            c("2026-09-15T00:00:30Z", "b"),
            p("2026-09-15T00:00:40Z", "b", 0.20, 10),
            r("2026-09-15T00:01:00Z", "b"),
        ]
        out = auditmod.audit(rows)
        self.assertEqual(out["ended_unarmed_n"], 0)
        self.assertEqual(out["projected_completed_serial_opportunities"], 0)

    def test_existing_protected_exit_remains_existing_protected_exit(self):
        rows = [
            c("2026-09-15T00:00:00Z", "a"),
            p("2026-09-15T00:00:10Z", "a", 0.06, 10),
            p("2026-09-15T00:00:20Z", "a", 0.01, 20),
            r("2026-09-15T00:00:40Z", "a"),
            c("2026-09-15T00:00:30Z", "b"),
            p("2026-09-15T00:00:40Z", "b", 0.10, 10),
            p("2026-09-15T00:00:50Z", "b", 0.05, 20),
            r("2026-09-15T00:01:00Z", "b"),
        ]
        out = auditmod.audit(rows)
        self.assertGreaterEqual(len(out["projected_ladder"]), 1)
        self.assertEqual(out["projected_ladder"][0]["terminal_kind"], "PROTECTED_EXIT")
        self.assertEqual(out["ended_unarmed_n"], 0)
        self.assertFalse(out["protected_thresholds_changed"])


if __name__ == "__main__":
    unittest.main()
