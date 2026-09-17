"""Fail-closed checks of explicit Early/Final watchdog observations.

Frozen producers put watchdog at root. Also accept a live.watchdog envelope;
when both exist, validate both independently (no positive field masks a fault).
See WATCHDOG_SCHEMA_V3.json for pinned producer code and field semantics.
"""
import math
from collections.abc import Mapping


def _measurement(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and value >= 0
    except (ValueError, OverflowError):
        return False


def watchdog_failures(payload, *, required=False):
    failures = []
    locations = [("watchdog", payload)]
    if isinstance(payload.get("live"), Mapping):
        locations.append(("live.watchdog", payload["live"]))
    found = False
    for path, envelope in locations:
        if "watchdog" not in envelope:
            continue
        found = True
        watchdog = envelope["watchdog"]
        if not isinstance(watchdog, Mapping):
            failures.append(path + ":invalid_object")
            continue
        # No bool(), integer equality, string parsing, or fallback to wrapper ok.
        if "healthy" not in watchdog:
            failures.append(path + ".healthy:missing")
        for key in ("healthy", "observer_worker_alive", "ok", "source_ok", "fresh"):
            if key in watchdog and watchdog[key] is not True:
                reason = "false" if watchdog[key] is False else "invalid_boolean"
                failures.append(path + "." + key + ":" + reason)
        for key in ("stale", "dead", "failed"):
            if key in watchdog and watchdog[key] is not False:
                reason = "true" if watchdog[key] is True else "invalid_boolean"
                failures.append(path + "." + key + ":" + reason)
        # These are defensive compatibility fields, not claimed as emitted by
        # the frozen producers. Unknown/malformed states cannot assert health.
        for key in ("status", "state"):
            if key in watchdog:
                value = watchdog[key]
                if not isinstance(value, str):
                    failures.append(path + "." + key + ":invalid_state")
                elif value.strip().upper() not in {
                        "OK", "HEALTHY", "ALIVE", "RUNNING", "READY", "FRESH", "PASS"}:
                    failures.append(path + "." + key + ":negative_or_unknown:" + value)
        # Producers clear observer_last_exception only after a successful
        # iteration. It is current failure evidence, not a lifetime error count.
        if "observer_last_exception" in watchdog and watchdog["observer_last_exception"] is not None:
            value = watchdog["observer_last_exception"]
            reason = "present" if isinstance(value, str) and value else "invalid_exception"
            failures.append(path + ".observer_last_exception:" + reason)
        if "error" in watchdog:
            value = watchdog["error"]
            if not (value is None or value is False or (isinstance(value, str) and value == "")):
                failures.append(path + ".error:present_or_malformed")
        measurements = {}
        for key in ("observer_age_sec", "observer_stale_sec"):
            if key in watchdog:
                value = watchdog[key]
                if not _measurement(value) or (key == "observer_stale_sec" and value == 0):
                    failures.append(path + "." + key + ":invalid_measurement")
                else:
                    measurements[key] = value
        if "observer_age_sec" in watchdog or "observer_stale_sec" in watchdog:
            for key in ("observer_age_sec", "observer_stale_sec"):
                if key not in watchdog:
                    failures.append(path + "." + key + ":missing")
        if len(measurements) == 2 and measurements["observer_age_sec"] > measurements["observer_stale_sec"]:
            failures.append(path + ".observer_age_sec:stale")
    if required and not found:
        failures.append("watchdog:missing")
    return failures
