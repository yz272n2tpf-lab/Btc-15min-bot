"""Read-only Linux clock measurements; missing premises NEVER become Bounds.

Run ``python -m sprint_evidence.clock_monitor --samples 6 --interval 1``.
This producer reads actual clocks and adjtimex(modes=0), and installs a private
timerfd discontinuity detector. It neither disciplines clocks nor calls BTC15.
Kernel maxerror/tolerance are retained as observations, not promoted to an
authenticated UTC reference or a worst-case oscillator guarantee. Consequently
this implementation cannot issue live certificates without the missing host
reference/rate/domain qualification. This is an explicit deployment blocker.
"""
import argparse
import ctypes
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import uuid


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def _read(path, symlink=False):
    try:
        value = os.readlink(path) if symlink else Path(path).read_text().strip()
        return {"state": "OBSERVED", "value": value}
    except OSError as exc:
        return {"state": "UNAVAILABLE", "errno": exc.errno}


class _Timeval(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_long)]


class _Timex(ctypes.Structure):
    # glibc LP64 ABI, verified against installed bits/timex.h; other ABIs fail.
    _fields_ = [("modes", ctypes.c_uint)] + [
        (name, ctypes.c_long) for name in ("offset", "freq", "maxerror", "esterror")
    ] + [("status", ctypes.c_int)] + [
        (name, ctypes.c_long) for name in ("constant", "precision", "tolerance")
    ] + [("time", _Timeval)] + [
        (name, ctypes.c_long) for name in ("tick", "ppsfreq", "jitter")
    ] + [("shift", ctypes.c_int)] + [
        (name, ctypes.c_long) for name in ("stabil", "jitcnt", "calcnt", "errcnt", "stbcnt")
    ] + [("tai", ctypes.c_int), ("reserved", ctypes.c_int * 11)]


def adjtimex_read():
    """No mode parameter is exposed: this function cannot adjust the clock."""
    if platform.system() != "Linux" or ctypes.sizeof(ctypes.c_long) != 8 or ctypes.sizeof(_Timex) != 208:
        return {"state": "UNAVAILABLE", "reason": "UNSUPPORTED_TIMEX_ABI"}
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        call = libc.adjtimex
        call.argtypes = [ctypes.POINTER(_Timex)]
        call.restype = ctypes.c_int
        value = _Timex()  # modes == 0: read only
        result = call(ctypes.byref(value))
        if result < 0:
            return {"state": "UNAVAILABLE", "errno": ctypes.get_errno(), "modes": 0}
        observed = {name: int(getattr(value, name)) for name in (
            "modes", "offset", "freq", "maxerror", "esterror", "status", "constant",
            "precision", "tolerance", "tick", "ppsfreq", "jitter", "stabil", "tai")}
        return {"state": "OBSERVED", "return_state": result, **observed,
                "frequency_ppm": value.freq / 65536,
                "kernel_tolerance_ppm": value.tolerance / 65536,
                "synchronized_status": result == 0 and not value.status & (0x40 | 0x1000),
                "is_authenticated_reference": False,
                "is_oscillator_rate_certificate": False}
    except (AttributeError, OSError) as exc:
        return {"state": "UNAVAILABLE", "reason": type(exc).__name__}


class _Timespec(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


class _Itimerspec(ctypes.Structure):
    _fields_ = [("it_interval", _Timespec), ("it_value", _Timespec)]


class StepDetector:
    """Private timerfd CANCEL_ON_SET; catches step-and-return between polls.

    If unsupported/expired/cancelled, it stays unavailable until a NEW monitor
    epoch. A new descriptor never rehabilitates evidence from the old epoch.
    """
    def __init__(self):
        self.fd = None
        self.status = {"state": "UNAVAILABLE", "reason": "NOT_ARMED"}
        try:
            if ctypes.sizeof(ctypes.c_long) != 8:
                raise OSError(errno.ENOSYS, "Unsupported ABI")
            libc = ctypes.CDLL(None, use_errno=True)
            create, arm = libc.timerfd_create, libc.timerfd_settime
            create.argtypes = [ctypes.c_int, ctypes.c_int]
            create.restype = ctypes.c_int
            arm.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(_Itimerspec), ctypes.c_void_p]
            arm.restype = ctypes.c_int
            descriptor = create(time.CLOCK_REALTIME, os.O_NONBLOCK | os.O_CLOEXEC)
            if descriptor < 0:
                raise OSError(ctypes.get_errno(), "timerfd_create")
            self.fd = descriptor
            timer = _Itimerspec(_Timespec(0, 0), _Timespec(time.time_ns() // 10**9 + 86400, 0))
            # ABSTIME=1, CANCEL_ON_SET=2: discontinous realtime changes cancel.
            if arm(self.fd, 3, ctypes.byref(timer), None) < 0:
                raise OSError(ctypes.get_errno(), "timerfd_settime")
            self.status = {"state": "ARMED", "mechanism": "TFD_TIMER_CANCEL_ON_SET"}
        except (OSError, AttributeError) as exc:
            self.close()
            self.status = {"state": "UNAVAILABLE", "reason": type(exc).__name__,
                           "errno": getattr(exc, "errno", None)}

    def check(self):
        if self.status["state"] != "ARMED":
            return dict(self.status)
        try:
            result = os.read(self.fd, 8)
            self.status = {"state": "UNAVAILABLE", "reason": "DETECTOR_EXPIRED_OR_EMPTY_READ",
                           "bytes_read": len(result)}
        except BlockingIOError:
            pass
        except OSError as exc:
            self.status = {"state": "UNAVAILABLE", "reason": (
                "CLOCK_STEP_DETECTED" if exc.errno == errno.ECANCELED else "DETECTOR_READ_ERROR"),
                "errno": exc.errno}
        return dict(self.status)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def _chrony(command):
    executable = shutil.which("chronyc")
    if executable is None:
        return {"state": "UNAVAILABLE", "reason": "CHRONYC_NOT_INSTALLED"}
    try:
        result = subprocess.run([executable, "-n", "-c", command], capture_output=True,
                                text=True, timeout=0.5, check=False)
        return {"state": "OBSERVED" if result.returncode == 0 else "UNAVAILABLE",
                "returncode": result.returncode, "output": result.stdout[:16384],
                "stderr": result.stderr[:1024]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"state": "UNAVAILABLE", "reason": type(exc).__name__}


class LinuxClockProbe:
    def __init__(self):
        self.detector = StepDetector()
        self.runtime_epoch = str(uuid.uuid4())

    def capture(self):
        start = time.monotonic_ns()
        detector_before = self.detector.check()
        clocks = {}
        for name in ("CLOCK_REALTIME", "CLOCK_MONOTONIC", "CLOCK_MONOTONIC_RAW", "CLOCK_BOOTTIME"):
            try:
                before = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                value = time.clock_gettime_ns(getattr(time, name))
                after = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                clocks[name] = {"state": "OBSERVED", "ns": value, "raw_before_ns": before,
                                "raw_after_ns": after, "read_bracket_ns": after - before}
            except (OSError, AttributeError) as exc:
                clocks[name] = {"state": "UNAVAILABLE", "reason": type(exc).__name__}
        return {"schema": "BTC15_CLOCK_OBSERVATION_V1", "probe_kind": "ACTUAL_LINUX_READS",
                "runtime_epoch": self.runtime_epoch, "platform": platform.platform(),
                "boot_id": _read("/proc/sys/kernel/random/boot_id"),
                "time_namespace": _read("/proc/self/ns/time", symlink=True),
                "time_namespace_offsets": _read("/proc/self/timens_offsets"),
                "clocksource": _read("/sys/devices/system/clocksource/clocksource0/current_clocksource"),
                "clocks": clocks, "adjtimex": adjtimex_read(),
                "step_detector_before": detector_before, "step_detector_after": self.detector.check(),
                "measurement_work_ns": time.monotonic_ns() - start}

    def close(self):
        self.detector.close()


class ClockMonitor:
    """Measurement producer with explicit unavailable guard output.

    An anomaly threshold is only a diagnostic alarm, never an acceptance bound.
    No number of apparently stable observations fills a missing bound premise.
    """
    MISSING_PREMISES = (
        "AUTHENTICATED_UTC_REFERENCE_AND_OFFSET_ENVELOPE_UNAVAILABLE",
        "JUSTIFIED_WORST_CASE_RATE_ENVELOPE_UNAVAILABLE",
        "PRODUCER_CLOCK_DOMAIN_BINDING_UNQUALIFIED",
        "ALL_EVENT_READ_ERROR_BOUNDS_UNQUALIFIED",
    )

    def __init__(self, *, synthetic_only=False, heartbeat_ns=1_250_000_000,
                 anomaly_ns=5_000_000):
        if type(heartbeat_ns) is not int or not 0 < heartbeat_ns <= 5_000_000_000:
            raise ValueError("INVALID_HEARTBEAT")
        if type(anomaly_ns) is not int or anomaly_ns <= 0:
            raise ValueError("INVALID_DIAGNOSTIC_THRESHOLD")
        self.synthetic_only = synthetic_only
        self.heartbeat_ns, self.anomaly_ns = heartbeat_ns, anomaly_ns
        self.previous = None
        self.sequence = 0
        self.revoked_epochs = set()

    def observe(self, observation):
        # Detach caller-owned dictionaries before any comparison or persistence.
        observation = json.loads(json.dumps(observation, allow_nan=False))
        self.sequence += 1
        reasons = list(self.MISSING_PREMISES)
        anomalies = []
        expected = "INJECTED_TEST_ONLY" if self.synthetic_only else "ACTUAL_LINUX_READS"
        if observation.get("probe_kind") != expected:
            anomalies.append("CLOCK_MODE_CONFLICT")
        clocks = observation.get("clocks", {})
        valid_reads = True
        for name in ("CLOCK_REALTIME", "CLOCK_MONOTONIC", "CLOCK_MONOTONIC_RAW", "CLOCK_BOOTTIME"):
            row = clocks.get(name, {})
            if (row.get("state") != "OBSERVED" or
                any(type(row.get(key)) is not int for key in ("ns", "raw_before_ns", "raw_after_ns", "read_bracket_ns")) or
                row.get("raw_after_ns", -1) < row.get("raw_before_ns", 0) or
                row.get("read_bracket_ns") != row.get("raw_after_ns", 0) - row.get("raw_before_ns", 0)):
                valid_reads = False
                anomalies.append("CLOCK_READ_UNAVAILABLE_OR_MALFORMED:" + name)
        epoch = (observation.get("runtime_epoch"), observation.get("boot_id", {}).get("value"),
                 observation.get("time_namespace", {}).get("value"))
        if not all(isinstance(value, str) and value for value in epoch):
            anomalies.append("CLOCK_EPOCH_OR_NAMESPACE_UNAVAILABLE")
            epoch = ("INVALID_EPOCH", _digest(list(epoch)), "UNAVAILABLE")
        for detector in ("step_detector_before", "step_detector_after"):
            if observation.get(detector, {}).get("state") != "ARMED":
                anomalies.append(observation.get(detector, {}).get("reason", "STEP_DETECTOR_UNAVAILABLE"))
        kernel = observation.get("adjtimex", {})
        if kernel.get("state") != "OBSERVED":
            reasons.append("KERNEL_CLOCK_STATUS_UNAVAILABLE")
        elif not kernel.get("synchronized_status"):
            reasons.append("KERNEL_CLOCK_NOT_SYNCHRONIZED")
        deltas = None
        if self.previous and valid_reads and self.previous["valid_reads"]:
            prior, old_epoch = self.previous["observation"], self.previous["epoch"]
            if epoch != old_epoch:
                anomalies.append("CLOCK_RESTART_OR_DOMAIN_CHANGE")
                self.revoked_epochs.add(old_epoch)
            else:
                names = ("CLOCK_REALTIME", "CLOCK_MONOTONIC", "CLOCK_MONOTONIC_RAW", "CLOCK_BOOTTIME")
                deltas = {name: clocks[name]["ns"] - prior["clocks"][name]["ns"] for name in names}
                if min(deltas.values()) < 0:
                    anomalies.append("CLOCK_MOVED_BACKWARDS")
                if deltas["CLOCK_BOOTTIME"] > self.heartbeat_ns:
                    anomalies.append("MONITOR_HEARTBEAT_MISSED")
                raw_delta = deltas["CLOCK_MONOTONIC_RAW"]
                bracket = sum(clocks[name]["read_bracket_ns"] + prior["clocks"][name]["read_bracket_ns"] for name in names)
                if abs(deltas["CLOCK_REALTIME"] - raw_delta) > self.anomaly_ns + bracket:
                    anomalies.append("WALL_RAW_STEP_OR_RATE_ANOMALY")
                if abs(deltas["CLOCK_BOOTTIME"] - deltas["CLOCK_MONOTONIC"]) > self.anomaly_ns + bracket:
                    anomalies.append("SUSPENSION_OR_ELAPSED_CLOCK_ANOMALY")
        if anomalies:
            self.revoked_epochs.add(epoch)
        if epoch in self.revoked_epochs:
            reasons.append("CLOCK_EPOCH_UNQUALIFIED_OR_REVOKED")
        reasons.extend(anomalies)
        self.previous = {"observation": json.loads(json.dumps(observation)), "epoch": epoch,
                         "valid_reads": valid_reads}
        body = {"schema": "BTC15_CLOCK_MONITOR_V1", "state": "UNAVAILABLE", "bound": None,
                "monitor_sequence": self.sequence, "synthetic": self.synthetic_only,
                "diagnostic_state": "ANOMALY" if anomalies else "NO_ANOMALY_OBSERVED",
                "reasons": sorted(set(reasons)), "deltas_ns": deltas,
                "observation": observation}
        body["measurement_sha256"] = _digest(body)
        return body

    def require_bound(self, now_utc=None):
        raise ValueError("CLOCK_CERTIFICATE_UNAVAILABLE:REAL_PREMISES_NOT_QUALIFIED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=6)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--environment-label", default="unbound-local-environment")
    parser.add_argument("--output", help="New JSONL file; refuses to overwrite existing evidence")
    args = parser.parse_args()
    if not 1 <= args.samples <= 3600 or not 0.01 <= args.interval <= 1:
        parser.error("samples must be 1..3600 and interval 0.01..1 seconds")
    probe, monitor = LinuxClockProbe(), ClockMonitor()
    manifest = {"schema": "BTC15_CLOCK_PROBE_RUN_V1", "environment_label": args.environment_label,
                "label_is_attestation": False, "runtime_epoch": probe.runtime_epoch,
                "recorded_utc": datetime.now(timezone.utc).isoformat(),
                "chrony_tracking": _chrony("tracking"), "chrony_sources": _chrony("sources"),
                "chrony_authdata": _chrony("authdata"), "signal_only": True, "orders": False}
    output = open(args.output, "x") if args.output else sys.stdout
    print(json.dumps(manifest, sort_keys=True), file=output, flush=True)
    try:
        for index in range(args.samples):
            if index:
                time.sleep(args.interval)
            print(json.dumps(monitor.observe(probe.capture()), sort_keys=True), file=output, flush=True)
    finally:
        probe.close()
        if args.output:
            output.close()


if __name__ == "__main__":
    main()
