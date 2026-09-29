"""Read-only PHC/chrony identity diagnostics. Never creates a UTC certificate.

Use on the actual nonproduction producer host, without sudo/installation:
  python -m sprint_evidence.host_clock_diagnostics --output host_clock.json
Only allowlisted non-secret chrony directives and public clock device facts are
retained. PHC devices are opened O_RDONLY and read using clock_gettime only.
"""
import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

from sprint_evidence.clock_monitor import LinuxClockProbe, _chrony, _read


SAFE_DIRECTIVES = frozenset(("refclock", "maxclockerror", "maxdrift", "maxslewrate",
    "corrtimeratio", "makestep", "maxchange", "maxupdateskew", "minsources",
    "leapsecmode", "leapsectz", "rtcsync", "noclientlog", "hwtimestamp"))


def summarize_tracking(text):
    """Interpret arithmetic conditional on the selected reference, not UTC."""
    try:
        rows = list(csv.reader(text.splitlines()))
        if len(rows) != 1 or len(rows[0]) != 14:
            raise ValueError("TRACKING_FIELD_COUNT")
        row = rows[0]
        names = ("reference_unix_seconds", "system_offset_seconds", "last_offset_seconds",
                 "rms_offset_seconds", "frequency_ppm", "residual_frequency_ppm",
                 "skew_ppm", "root_delay_seconds", "root_dispersion_seconds", "update_seconds")
        numbers = [Decimal(value) for value in row[3:13]]
        if any(not value.is_finite() for value in numbers):
            raise ValueError("NONFINITE_TRACKING")
        values = dict(zip(names, numbers))
        if min(values["skew_ppm"], values["root_delay_seconds"],
               values["root_dispersion_seconds"], values["update_seconds"]) < 0:
            raise ValueError("NEGATIVE_UNCERTAINTY")
        error_us = (abs(values["system_offset_seconds"]) + values["root_dispersion_seconds"]
                    + values["root_delay_seconds"] / 2) * Decimal(1_000_000)
        return {"state": "OBSERVED", "reference_id": row[0], "reference_name": row[1],
                "stratum": int(row[2]), "leap_status": row[13],
                "values": {key: str(value) for key, value in values.items()},
                "conditional_system_reference_error_us": str(error_us),
                "conditional_on_reference_correctness": True,
                "absolute_utc_error_us": None, "justified_worst_case_rate_ppm": None,
                "is_certificate": False,
                "reason": "REFERENCE_UPSTREAM_UTC_ERROR_AND_RATE_PREMISES_NOT_ESTABLISHED"}
    except (ValueError, InvalidOperation, TypeError) as exc:
        return {"state": "UNAVAILABLE", "reason": str(exc), "is_certificate": False}


def chrony_config():
    # Never print key material, include paths or arbitrary config lines.
    candidates = {Path("/etc/chrony/chrony.conf"), Path("/etc/chrony.conf")}
    for directory in (Path("/etc/chrony/conf.d"), Path("/etc/chrony/sources.d")):
        if directory.is_dir():
            candidates.update(path for path in directory.glob("*") if path.is_file())
    reports = []
    for path in sorted(candidates):
        try:
            raw = path.read_bytes()
            selected = []
            for lineno, line in enumerate(raw.decode("utf-8", errors="replace").splitlines(), 1):
                line = line.split("#", 1)[0].strip()
                if line and line.split()[0].lower() in SAFE_DIRECTIVES:
                    selected.append({"line": lineno, "directive": line})
            reports.append({"path": str(path), "state": "OBSERVED",
                "sha256": hashlib.sha256(raw).hexdigest(), "allowlisted_directives": selected,
                "not_a_complete_config_expansion": True})
        except OSError as exc:
            reports.append({"path": str(path), "state": "UNAVAILABLE", "errno": exc.errno})
    return reports


def phc_devices():
    devices = []
    for directory in sorted(Path("/sys/class/ptp").glob("ptp*")):
        device = Path("/dev") / directory.name
        report = {"sysfs_path": str(directory), "device": str(device),
                  "clock_name": _read(directory / "clock_name"),
                  "device_number": _read(directory / "dev"),
                  "max_adjustment": _read(directory / "max_adjustment"),
                  "syspath": str(directory.resolve()), "reads": []}
        descriptor = None
        try:
            descriptor = os.open(device, os.O_RDONLY | os.O_CLOEXEC)
            # Linux FD_TO_CLOCKID; a dynamic clock_gettime is a read operation.
            clock_id = ((~descriptor) << 3) | 3
            for _ in range(3):
                raw_before = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                realtime_before = time.clock_gettime_ns(time.CLOCK_REALTIME)
                phc_ns = time.clock_gettime_ns(clock_id)
                realtime_after = time.clock_gettime_ns(time.CLOCK_REALTIME)
                raw_after = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
                report["reads"].append({"raw_before_ns": raw_before, "raw_after_ns": raw_after,
                    "realtime_before_ns": realtime_before, "phc_ns": phc_ns,
                    "realtime_after_ns": realtime_after,
                    "read_bracket_ns": raw_after - raw_before,
                    "reference_is_phc_not_verified_utc": True})
            report["state"] = "OBSERVED"
        except (OSError, ValueError) as exc:
            report.update(state="UNAVAILABLE", errno=getattr(exc, "errno", None), reason=type(exc).__name__)
        finally:
            if descriptor is not None:
                os.close(descriptor)
        devices.append(report)
    return devices


def collect():
    probe = LinuxClockProbe()
    try:
        tracking = _chrony("tracking")
        return {"schema": "BTC15_HOST_CLOCK_DIAGNOSTICS_V1", "signal_only": True, "orders": False,
            "platform": platform.platform(), "runtime_epoch": probe.runtime_epoch,
            "chrony_tracking": tracking, "tracking_interpretation": summarize_tracking(tracking.get("output", "")),
            "chrony_sources": _chrony("sources"), "chrony_sourcestats": _chrony("sourcestats"),
            "chrony_authdata": _chrony("authdata"), "chrony_config": chrony_config(),
            "ptp_hyperv_symlink": _read("/dev/ptp_hyperv", symlink=True),
            "phc_devices": phc_devices(), "linux_probe": probe.capture(),
            "qualification": {"state": "UNAVAILABLE", "bound": None,
                "no_cross_domain_transfer": True,
                "missing": ["ACTUAL_PHC_UPSTREAM_UTC_ERROR_ENVELOPE",
                    "ACTUAL_DISCIPLINED_OSCILLATOR_RATE_ENVELOPE", "EVENT_READ_AND_LIFETIME_BINDING"]}}
    finally:
        probe.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output")
    args = parser.parse_args()
    data = collect()
    if args.output:
        with open(args.output, "x") as out:
            json.dump(data, out, indent=2, sort_keys=True)
            out.write("\n")
    else:
        json.dump(data, sys.stdout, indent=2, sort_keys=True)
        print()


if __name__ == "__main__":
    main()
