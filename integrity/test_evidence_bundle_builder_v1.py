import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from integrity.evidence_bundle_builder_v1 import (
    apply_operational_manifest,
    build_bundle,
)
from integrity.evidence_integrity_reconciler_v1 import ReconcilerPolicy


def iso(d):
    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class EvidenceBundleBuilderTests(unittest.TestCase):
    def test_manifest_true_cannot_override_evidence_false(self):
        records = [{
            "contract_id": "KXBTC15M-TEST",
            "storage_ok": False,
        }]
        manifest = {"global": {"storage_ok": True, "process_alive": True}}
        out = apply_operational_manifest(records, manifest)
        self.assertFalse(out[0]["storage_ok"])
        self.assertTrue(out[0]["process_alive"])

    def test_missing_manifest_value_stays_missing(self):
        records = [{"contract_id": "KXBTC15M-TEST"}]
        out = apply_operational_manifest(records, {"global": {"storage_ok": True}})
        self.assertTrue(out[0]["storage_ok"])
        self.assertNotIn("process_alive", out[0])

    def test_end_to_end_clean_requires_explicit_operational_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rollover = root / "rollover.jsonl"
            brti = root / "brti.jsonl"

            start = datetime(2026, 9, 17, 3, 0, 0, tzinfo=timezone.utc)
            ticker = "KXBTC15M-26SEP162315-15"
            rollover.write_text(json.dumps({
                "timestamp": iso(start + timedelta(seconds=50)),
                "message": (
                    "ROLLOVER PROBE V3 SUMMARY | "
                    f"boundary={iso(start)} | target={ticker} | samples=34 | "
                    "exact_active_quoted=4.931 | identity_all=True | clock_all=True | "
                    "broad_active=31.615 | FRESH ONLY | NO ORDERS"
                ),
            }) + "\n")

            rows = []
            seq = 1000
            attempts = 2000
            # <=5 second spacing from second 1 through second 899 creates an
            # actually observed full path for this narrow BRTI-only test profile.
            for sec in range(1, 900, 5):
                seq += 5
                attempts += 5
                rows.append({
                    "timestamp": iso(start + timedelta(seconds=sec)),
                    "message": (
                        "BRTI_SHARED HEARTBEAT | status=PRIMARY_OK | clean=True | "
                        f"age_ms=500 | seq={seq} | upstream_ok={seq}/{attempts} "
                        f"(99.0%) | 429=0 | errors=0 | NO ORDERS"
                    ),
                })
            brti.write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n"
            )

            manifest = {
                "global": {
                    "service_deployment_ok": True,
                    "process_alive": True,
                    "storage_ok": True,
                    "collector_advancing": True,
                    "scorer_advancing": True,
                    "runtime_config_match": True,
                    "cutoff_valid": True,
                }
            }
            policy = ReconcilerPolicy(
                require_kalshi=False,
                require_coinbase=False,
                require_parity=False,
                max_brti_age_sec=5.0,
                max_source_gap_sec=10.0,
                max_rollover_lag_sec=15.0,
            )
            bundle = build_bundle(
                [("combined", str(rollover)), ("brti", str(brti))],
                operational_manifest=manifest,
                policy=policy,
            )
            self.assertEqual(bundle["summary"]["contract_records"], 1)
            self.assertEqual(bundle["summary"]["certifiable_contracts"], 1)
            self.assertEqual(
                bundle["assessments"][0]["classification"], "CLEAN"
            )

    def test_same_feed_path_without_operational_attestation_is_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rollover = root / "rollover.jsonl"
            brti = root / "brti.jsonl"

            start = datetime(2026, 9, 17, 3, 0, 0, tzinfo=timezone.utc)
            ticker = "KXBTC15M-26SEP162315-15"
            rollover.write_text(json.dumps({
                "timestamp": iso(start + timedelta(seconds=50)),
                "message": (
                    "ROLLOVER PROBE V3 SUMMARY | "
                    f"boundary={iso(start)} | target={ticker} | samples=34 | "
                    "exact_active_quoted=4.931 | identity_all=True | clock_all=True | "
                    "broad_active=31.615 | FRESH ONLY | NO ORDERS"
                ),
            }) + "\n")

            rows = []
            for i, sec in enumerate(range(1, 900, 5), start=1):
                rows.append({
                    "timestamp": iso(start + timedelta(seconds=sec)),
                    "message": (
                        "BRTI_SHARED HEARTBEAT | status=PRIMARY_OK | clean=True | "
                        f"age_ms=500 | seq={1000+i} | upstream_ok={1000+i}/{2000+i} "
                        f"(99.0%) | 429=0 | errors=0 | NO ORDERS"
                    ),
                })
            brti.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

            policy = ReconcilerPolicy(
                require_kalshi=False,
                require_coinbase=False,
                require_parity=False,
            )
            bundle = build_bundle(
                [("combined", str(rollover)), ("brti", str(brti))],
                policy=policy,
            )
            self.assertEqual(
                bundle["assessments"][0]["classification"], "UNKNOWN"
            )
            self.assertEqual(bundle["summary"]["certifiable_contracts"], 0)


if __name__ == "__main__":
    unittest.main()
