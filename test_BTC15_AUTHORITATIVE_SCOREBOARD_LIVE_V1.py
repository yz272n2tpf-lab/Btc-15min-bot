import unittest

import BTC15_AUTHORITATIVE_SCOREBOARD_LIVE_V1 as m


class Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
    def json(self):
        return self._payload


def payload(version, summary=None, **top):
    d = {
        "version": version,
        "orders": False,
        "manual_execution_only": True,
    }
    if summary is not None:
        d["summary"] = summary
    d.update(top)
    return d


class LiveScoreboardTests(unittest.TestCase):
    def test_fetch_valid_version(self):
        expected = m.SOURCES["early"]["version"]
        p = payload(expected, {"early_calls": 1})
        got, h = m.fetch_source("early", get=lambda *a, **k: Resp(200, p))
        self.assertIsNotNone(got)
        self.assertTrue(h["connected"])
        self.assertEqual(h["version"], expected)

    def test_fetch_wrong_version_fails_closed(self):
        p = payload("WRONG_VERSION", {})
        got, h = m.fetch_source("final", get=lambda *a, **k: Resp(200, p))
        self.assertIsNone(got)
        self.assertFalse(h["connected"])
        self.assertEqual(h["reason"], "version_mismatch")

    def test_fetch_http_error_is_missing_not_stale(self):
        got, h = m.fetch_source("handoff", get=lambda *a, **k: Resp(503, {}))
        self.assertIsNone(got)
        self.assertEqual(h["reason"], "http_503")

    def test_fetch_unsafe_orders_true_fails_closed(self):
        expected = m.SOURCES["excursion"]["version"]
        p = payload(expected, {}, orders=True)
        got, h = m.fetch_source("excursion", get=lambda *a, **k: Resp(200, p))
        self.assertIsNone(got)
        self.assertIn("unsafe_orders_true", h["reason"])

    def test_partial_collection_marks_lane_not_connected(self):
        def f(name):
            if name == "early":
                return payload(m.SOURCES[name]["version"], {"eligibility_complete_contracts": 6, "early_calls": 1}), {"connected": True}
            return None, {"connected": False, "reason": "test_missing"}
        out = m.collect_live(fetcher=f)
        self.assertEqual(out["connected_sources"], 1)
        self.assertFalse(out["all_sources_connected"])
        self.assertTrue(out["scoreboard"]["sources"]["early"]["connected"])
        self.assertFalse(out["scoreboard"]["sources"]["final"]["connected"])
        self.assertIsNone(out["scoreboard"]["final"]["directional_accuracy"])

    def test_all_sources_connected(self):
        summaries = {
            "final": {"eligibility_complete_contracts": 9, "lock_calls": 6, "settled_lock_calls": 6, "qualified_accuracy": 1.0, "final_only_coverage": 2/3},
            "early": {"eligibility_complete_contracts": 6, "early_calls": 1, "settled_early_calls": 1, "early_only_coverage": 1/6},
            "handoff": {"eligibility_complete_contracts": 6, "early_calls": 0, "final_calls": 4, "handoffs": 0, "union_coverage": 4/6, "sample_ready": False},
            "excursion": {"eligibility_complete_contracts": 1, "early_calls": 0, "completed_excursions": 0},
            "flip": {"complete_contracts": 1, "settled_preds": 6, "ready": False},
        }
        def f(name):
            return payload(m.SOURCES[name]["version"], summaries[name]), {"connected": True, "version": m.SOURCES[name]["version"]}
        out = m.collect_live(fetcher=f)
        self.assertEqual(out["connected_sources"], 5)
        self.assertTrue(out["all_sources_connected"])
        self.assertEqual(out["scoreboard"]["final"]["directional_accuracy"], 1.0)
        self.assertEqual(out["scoreboard"]["overall"]["certified_union_status"], "NOT CERTIFIED")

    def test_numeric_flip_remains_hidden_in_live_wrapper(self):
        def f(name):
            if name == "flip":
                return payload(m.SOURCES[name]["version"], {
                    "complete_contracts": 30,
                    "settled_preds": 240,
                    "ready": True,
                    "numeric_flip_risk_validated": True,
                    "current_flip_risk": .08,
                }), {"connected": True}
            return None, {"connected": False}
        out = m.collect_live(fetcher=f)
        self.assertEqual(out["scoreboard"]["flip_risk"]["display_status"], "HIDDEN_UNTIL_VALIDATED")
        self.assertIsNone(out["scoreboard"]["flip_risk"]["display_value"])

    def test_source_exception_does_not_crash_scoreboard(self):
        def f(name):
            if name == "final":
                raise RuntimeError("boom")
            return None, {"connected": False}
        out = m.collect_live(fetcher=f)
        self.assertTrue(out["ok"])
        self.assertFalse(out["source_health"]["final"]["connected"])
        self.assertIn("worker_error", out["source_health"]["final"]["reason"])

    def test_private_network_urls_only(self):
        for spec in m.SOURCES.values():
            self.assertTrue(spec["url"].startswith("http://"))
            self.assertIn(".railway.internal:8080/state", spec["url"])
            self.assertNotIn("up.railway.app", spec["url"])

    def test_live_output_safety_flags(self):
        out = m.collect_live(fetcher=lambda name: (None, {"connected": False}))
        self.assertFalse(out["orders"])
        self.assertTrue(out["manual_execution_only"])
        self.assertFalse(out["production_behavior_changed"])
        self.assertEqual(out["network_scope"], "RAILWAY_PRIVATE_COLLECTORS_ONLY")


if __name__ == "__main__":
    unittest.main()
