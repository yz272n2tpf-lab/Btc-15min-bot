#!/usr/bin/env python3
import unittest

import scalp_event_schema_adapter_v1 as a


class SchemaAdapterTests(unittest.TestCase):
    def candidate(self, **extra):
        row = {
            "record_type":"CANDIDATE",
            "entry_ask":"0.35","seconds_left":"600","confirm_count":"2","structure_ok":"1",
            "btc_against_side":"0","brti_against_side":"0","dual_reversal_evidence":"0","brti_status":"PRIMARY_OK",
            "entry_spread":"0.02","max_possible_upside_c":"65",
            "btc5":"5","btc15":"12","btc30":"25","brti5":"4","brti15":"10",
            "ask5":"0.01","ask15":"0.02","accel":"3","recent_btc_range60":"40",
            "btc5_norm":"0.2","btc15_norm":"0.4","brti_latency_ms":"250",
        }
        row.update(extra)
        return row

    def test_aliases_and_units_are_adapted(self):
        out = a.adapt_row(self.candidate())
        self.assertEqual(out["spread"], 0.02)
        self.assertEqual(out["max_possible_upside"], 0.65)
        self.assertEqual(out["btc_move5_side"], 5.0)
        self.assertEqual(out["brti_move15_side"], 10.0)
        self.assertEqual(out["acceleration"], 3.0)
        self.assertEqual(out["recent_range60"], 40.0)
        self.assertEqual(out["brti_latency_sec"], 0.25)

    def test_canonical_value_wins_over_alias(self):
        out = a.adapt_row(self.candidate(spread="0.03", entry_spread="0.02"))
        self.assertEqual(out["spread"], "0.03")

    def test_real_schema_dependencies_are_ready(self):
        status = a.candidate_schema_status([self.candidate()])
        self.assertTrue(status["ready"])
        self.assertEqual(status["missing_source_dependencies"], [])

    def test_missing_source_dependency_fails_closed(self):
        row = self.candidate()
        row.pop("brti15")
        status = a.candidate_schema_status([row])
        self.assertFalse(status["ready"])
        self.assertIn("brti_move15_side", status["missing_source_dependencies"])

    def test_no_future_outcome_field_is_an_alias_source(self):
        for sources in a.ALIASES.values():
            text = " ".join(sources).lower()
            for token in a.FORBIDDEN_SOURCE_TOKENS:
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
