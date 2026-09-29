"""Injected adversarial clock tests: none are real UTC certificates."""
from copy import deepcopy
import errno
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sprint_evidence.clock_monitor import ClockMonitor, StepDetector, _digest


def observation(second=0, *, wall_shift=0, boot_shift=0, epoch="TEST_RUNTIME_A"):
    base = 1_000_000_000_000 + second * 1_000_000_000
    rows = {}
    for name in ("CLOCK_REALTIME", "CLOCK_MONOTONIC", "CLOCK_MONOTONIC_RAW", "CLOCK_BOOTTIME"):
        ns = base
        if name == "CLOCK_REALTIME":
            ns += wall_shift
        if name == "CLOCK_BOOTTIME":
            ns += boot_shift
        rows[name] = dict(state="OBSERVED", ns=ns, raw_before_ns=base-100,
                          raw_after_ns=base+100, read_bracket_ns=200)
    return dict(probe_kind="INJECTED_TEST_ONLY", runtime_epoch=epoch,
                boot_id=dict(state="OBSERVED", value="TEST_BOOT_A"),
                time_namespace=dict(state="OBSERVED", value="TEST_NAMESPACE_A"),
                clocks=rows, adjtimex=dict(state="OBSERVED", synchronized_status=True,
                    maxerror=0, tolerance=32768000, frequency_ppm=0),
                step_detector_before=dict(state="ARMED"), step_detector_after=dict(state="ARMED"))


class ClockSafetyTests(unittest.TestCase):
    def setUp(self):
        self.monitor = ClockMonitor(synthetic_only=True)

    def test_apparently_perfect_synced_kernel_never_substitutes_reference_or_rate(self):
        for index in range(5):
            result = self.monitor.observe(observation(index))
            self.assertEqual(result["state"], "UNAVAILABLE")
            self.assertIsNone(result["bound"])
            self.assertIn("JUSTIFIED_WORST_CASE_RATE_ENVELOPE_UNAVAILABLE", result["reasons"])
            self.assertIn("AUTHENTICATED_UTC_REFERENCE_AND_OFFSET_ENVELOPE_UNAVAILABLE", result["reasons"])

    def test_injected_fixture_cannot_enter_live_mode(self):
        result = ClockMonitor().observe(observation())
        self.assertIn("CLOCK_MODE_CONFLICT", result["reasons"])

    def test_actual_label_cannot_enter_test_mode(self):
        row = observation()
        row["probe_kind"] = "ACTUAL_LINUX_READS"
        self.assertIn("CLOCK_MODE_CONFLICT", self.monitor.observe(row)["reasons"])

    def test_both_400ms_steps_revoke(self):
        for shift in (-400_000_000, 400_000_000):
            monitor = ClockMonitor(synthetic_only=True)
            monitor.observe(observation())
            result = monitor.observe(observation(1, wall_shift=shift))
            self.assertIn("WALL_RAW_STEP_OR_RATE_ANOMALY", result["reasons"])
            self.assertIn("CLOCK_EPOCH_UNQUALIFIED_OR_REVOKED", result["reasons"])
            self.assertIsNone(result["bound"])

    def test_detector_catches_step_and_return_between_identical_observations(self):
        self.monitor.observe(observation())
        row = observation(1)
        row["step_detector_after"] = dict(state="UNAVAILABLE", reason="CLOCK_STEP_DETECTED")
        result = self.monitor.observe(row)
        self.assertIn("CLOCK_STEP_DETECTED", result["reasons"])
        self.assertIsNone(result["bound"])

    def test_restart_never_inherits_epoch(self):
        self.monitor.observe(observation())
        result = self.monitor.observe(observation(1, epoch="TEST_RUNTIME_B"))
        self.assertIn("CLOCK_RESTART_OR_DOMAIN_CHANGE", result["reasons"])
        self.assertEqual(len(self.monitor.revoked_epochs), 2)

    def test_boot_and_namespace_changes_each_invalidate(self):
        for field in ("boot_id", "time_namespace"):
            monitor = ClockMonitor(synthetic_only=True)
            monitor.observe(observation())
            row = observation(1)
            row[field]["value"] = "CHANGED"
            self.assertIn("CLOCK_RESTART_OR_DOMAIN_CHANGE", monitor.observe(row)["reasons"])

    def test_unknown_namespace_is_unavailable(self):
        row = observation()
        row["time_namespace"] = dict(state="UNAVAILABLE", errno=2)
        self.assertIn("CLOCK_EPOCH_OR_NAMESPACE_UNAVAILABLE", self.monitor.observe(row)["reasons"])

    def test_suspend_invalidation(self):
        self.monitor.observe(observation())
        result = self.monitor.observe(observation(1, boot_shift=50_000_000))
        self.assertIn("SUSPENSION_OR_ELAPSED_CLOCK_ANOMALY", result["reasons"])

    def test_monitor_gap_cannot_be_rehabilitated(self):
        self.monitor.observe(observation())
        self.assertIn("MONITOR_HEARTBEAT_MISSED", self.monitor.observe(observation(2))["reasons"])
        result = self.monitor.observe(observation(3))
        self.assertIn("CLOCK_EPOCH_UNQUALIFIED_OR_REVOKED", result["reasons"])

    def test_backwards_all_clocks_is_not_stable(self):
        self.monitor.observe(observation(2))
        self.assertIn("CLOCK_MOVED_BACKWARDS", self.monitor.observe(observation(1))["reasons"])

    def test_malformed_and_missing_reads_are_unavailable(self):
        for mutation in (lambda row: row["clocks"].pop("CLOCK_REALTIME"),
                         lambda row: row["clocks"]["CLOCK_REALTIME"].update(ns=True),
                         lambda row: row["clocks"]["CLOCK_REALTIME"].update(read_bracket_ns=-1)):
            row = observation()
            mutation(row)
            result = self.monitor.observe(row)
            self.assertTrue(any("CLOCK_READ_UNAVAILABLE_OR_MALFORMED" in reason for reason in result["reasons"]))

    def test_consumer_mutation_cannot_rewrite_previous_observation(self):
        row = observation()
        result = self.monitor.observe(row)
        row["clocks"]["CLOCK_REALTIME"]["ns"] += 99_000_000_000
        self.assertNotEqual(row["clocks"], result["observation"]["clocks"])
        result["observation"]["clocks"]["CLOCK_REALTIME"]["ns"] += 99_000_000_000
        next_result = self.monitor.observe(observation(1))
        self.assertNotIn("WALL_RAW_STEP_OR_RATE_ANOMALY", next_result["reasons"])

    def test_hash_covers_raw_evidence(self):
        result = self.monitor.observe(observation())
        digest = result.pop("measurement_sha256")
        self.assertEqual(digest, _digest(result))
        result["observation"]["adjtimex"]["maxerror"] += 1
        self.assertNotEqual(digest, _digest(result))

    def test_expired_unknown_future_all_fail_bound_request(self):
        self.monitor.observe(observation())
        for label in (None, "2000-01-01T00:00:00Z", "2100-01-01T00:00:00Z", "malformed"):
            with self.assertRaisesRegex(ValueError, "REAL_PREMISES_NOT_QUALIFIED"):
                self.monitor.require_bound(label)

    def test_timerfd_cancel_is_latched(self):
        detector = StepDetector.__new__(StepDetector)
        detector.fd = 99999
        detector.status = dict(state="ARMED")
        with patch("sprint_evidence.clock_monitor.os.read", side_effect=OSError(errno.ECANCELED, "test")):
            self.assertEqual(detector.check()["reason"], "CLOCK_STEP_DETECTED")
        with patch("sprint_evidence.clock_monitor.os.read") as read:
            detector.check()
            read.assert_not_called()

    def test_timerfd_no_event_is_not_a_certificate(self):
        detector = StepDetector.__new__(StepDetector)
        detector.fd = 99999
        detector.status = dict(state="ARMED")
        with patch("sprint_evidence.clock_monitor.os.read", side_effect=BlockingIOError(errno.EAGAIN, "test")):
            self.assertEqual(detector.check()["state"], "ARMED")
        result = self.monitor.observe(observation())
        self.assertIsNone(result["bound"])

    def test_cli_actual_probe_outputs_raw_measurements_not_certificates(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "probe.jsonl"
            run = subprocess.run([sys.executable, "-m", "sprint_evidence.clock_monitor", "--samples", "2",
                                  "--interval", "0.01", "--output", str(output)],
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stderr)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[1]["observation"]["probe_kind"], "ACTUAL_LINUX_READS")
            self.assertTrue(all(row["bound"] is None for row in rows[1:]))


if __name__ == "__main__":
    unittest.main()
