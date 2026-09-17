import unittest

from integrity.railway_evidence_log_adapter_v1 import (
    attach_global_events,
    build_contract_windows,
    parse_log_entry,
    to_integrity_observations,
)


class RailwayEvidenceLogAdapterTests(unittest.TestCase):
    def test_parse_real_brti_heartbeat_shape(self):
        event = parse_log_entry(
            "2026-09-17T02:13:43.707258589Z",
            "BRTI_SHARED HEARTBEAT | status=PRIMARY_ERROR | clean=False | age_ms=354148 | seq=77875 | upstream_ok=77875/97132 (80.2%) | 429=19239 | errors=19257 | NO ORDERS",
            source="brti-shared-feed-v1",
        )
        self.assertEqual(event.kind, "BRTI_HEARTBEAT")
        self.assertAlmostEqual(event.fields["brti_age_sec"], 354.148)
        self.assertEqual(event.fields["brti_attempts_total"], 97132)
        self.assertEqual(event.fields["brti_429_total"], 19239)
        self.assertFalse(event.fields["brti_clean"])

    def test_rollover_window_uses_exact_probe_boundary(self):
        event = parse_log_entry(
            "2026-09-17T03:00:50.071466154Z",
            "ROLLOVER PROBE V3 SUMMARY | boundary=2026-09-17T03:00:00Z | target=KXBTC15M-26SEP162315-15 | samples=34 | exact_active_quoted=4.931 | identity_all=True | clock_all=True | broad_active=31.615 | FRESH ONLY | NO ORDERS",
            source="combined-forward-scorecard-v1",
        )
        windows = build_contract_windows([event])
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0].start_utc, "2026-09-17T03:00:00Z")
        self.assertEqual(windows[0].end_utc, "2026-09-17T03:15:00Z")
        self.assertAlmostEqual(windows[0].rollover_quote_lag_sec, 4.931)

    def test_global_brti_heartbeat_attaches_only_inside_known_window(self):
        rollover = parse_log_entry(
            "2026-09-17T03:00:50Z",
            "ROLLOVER PROBE V3 SUMMARY | boundary=2026-09-17T03:00:00Z | target=KXBTC15M-26SEP162315-15 | samples=34 | exact_active_quoted=4.931 | identity_all=True | clock_all=True | broad_active=31.615 | FRESH ONLY | NO ORDERS",
            source="combined",
        )
        brti = parse_log_entry(
            "2026-09-17T03:04:35.815996670Z",
            "BRTI_SHARED HEARTBEAT | status=PRIMARY_ERROR | clean=False | age_ms=167693 | seq=78660 | upstream_ok=78660/98074 (80.2%) | 429=19396 | errors=19414 | NO ORDERS",
            source="brti",
        )
        windows = build_contract_windows([rollover])
        attached = attach_global_events([rollover, brti], windows)
        self.assertEqual(attached[1].contract_id, "KXBTC15M-26SEP162315-15")
        self.assertGreater(attached[1].fields["seconds_left"], 600)

    def test_parity_fail_preserves_hard_evidence(self):
        event = parse_log_entry(
            "2026-09-17T03:04:40.336035040Z",
            "PARITY FAIL | KXBTC15M-26SEP162315-15 | age 4.2s | clock Δ0.0s | target Δ$0.00 | quotes Δ0.0c | BRTI Δ$3.03 @ 0.3s | BRTI",
            source="production_root",
        )
        self.assertEqual(event.kind, "PARITY_FAIL")
        self.assertFalse(event.fields["parity_ok"])
        self.assertEqual(event.fields["kalshi_age_sec"], 4.2)
        self.assertEqual(event.fields["brti_age_sec"], 0.3)

    def test_combined_late_start_is_kept_separate_from_exact_probe_lag(self):
        event = parse_log_entry(
            "2026-09-17T03:00:37.449761702Z",
            "COMBINED V2 LATE START | KXBTC15M-26SEP162315-15 | first_seen_lag=35.700000000000045s | EXCLUDED FROM GATE | NO ORDERS",
            source="combined",
        )
        self.assertEqual(event.kind, "COMBINED_LATE_START")
        self.assertAlmostEqual(event.fields["combined_first_seen_lag_sec"], 35.7)

    def test_final_lock_parses_without_claiming_certification(self):
        event = parse_log_entry(
            "2026-09-17T02:38:04.959531000Z",
            "FINAL V4 FIRST LOCK | KXBTC15M-26SEP162245-45 | UP | fair=0.922 | left=7.00m | ask=0.966 | band=>85C | <=50c=False | NO ORDERS",
            source="final",
        )
        self.assertEqual(event.kind, "FINAL_LOCK")
        self.assertEqual(event.fields["final_side"], "UP")
        self.assertEqual(event.fields["seconds_left"], 420.0)
        self.assertNotIn("valid_for_certification", event.fields)

    def test_observations_do_not_infer_missing_operational_fields(self):
        rollover = parse_log_entry(
            "2026-09-17T03:00:50Z",
            "ROLLOVER PROBE V3 SUMMARY | boundary=2026-09-17T03:00:00Z | target=KXBTC15M-26SEP162315-15 | samples=34 | exact_active_quoted=4.931 | identity_all=True | clock_all=True | broad_active=31.615 | FRESH ONLY | NO ORDERS",
            source="combined",
        )
        brti = parse_log_entry(
            "2026-09-17T03:04:35Z",
            "BRTI_SHARED HEARTBEAT | status=PRIMARY_ERROR | clean=False | age_ms=167693 | seq=78660 | upstream_ok=78660/98074 (80.2%) | 429=19396 | errors=19414 | NO ORDERS",
            source="brti",
        )
        windows = build_contract_windows([rollover])
        rows = to_integrity_observations([rollover, brti], windows)
        brti_row = [r for r in rows if r["source_kind"] == "BRTI_HEARTBEAT"][0]
        self.assertNotIn("storage_ok", brti_row)
        self.assertFalse(brti_row["brti_feed_clean"])


if __name__ == "__main__":
    unittest.main()
