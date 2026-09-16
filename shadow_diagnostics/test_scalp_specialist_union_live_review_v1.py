#!/usr/bin/env python3
import unittest
from unittest.mock import patch

import scalp_specialist_union_live_review_v1 as r


class LiveReviewTests(unittest.TestCase):
    def test_empty_rows_fail_closed_and_never_enable_orders(self):
        state = r.analyze_rows([], sha="abc", source_bytes=0)
        self.assertFalse(state["ok"])
        self.assertEqual(state["status"], "FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE")
        self.assertFalse(state["orders"])
        self.assertTrue(state["shadow_only"])
        self.assertFalse(state["production_logic_changed"])

    def test_fetch_rows_uses_bearer_when_token_present(self):
        class Resp:
            content = b"record_type,contract,seconds_left,timestamp_utc\nSNAPSHOT,A,890,2026-09-16T00:00:10Z\n"
            def raise_for_status(self):
                return None
        with patch.object(r, "SOURCE_TOKEN", "secret"), patch.object(r.requests, "get", return_value=Resp()) as get:
            rows, sha, n = r.fetch_rows()
        self.assertEqual(len(rows), 1)
        self.assertTrue(sha)
        self.assertGreater(n, 0)
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer secret")

    def test_fetch_rows_rejects_non_event_payload(self):
        class Resp:
            content = b"<html>not csv</html>"
            def raise_for_status(self):
                return None
        with patch.object(r.requests, "get", return_value=Resp()):
            with self.assertRaises(ValueError):
                r.fetch_rows()


if __name__ == "__main__":
    unittest.main()
