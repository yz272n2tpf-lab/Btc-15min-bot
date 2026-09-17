#!/usr/bin/env python3
"""BTC15 Railway Evidence Log Adapter V1.

Pure parser/normalizer for preserved Railway runtime log entries.

It does not call Railway, Kalshi, Coinbase, or any service.  It only converts
already-captured timestamp/message pairs into timestamped evidence observations
that can be passed to ``evidence_integrity_adapter_v1``.

Important:
- read-only / deterministic
- unknown values stay unknown
- global feed events are attached only when a contract window is known
- no trading or production behavior
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
import json
import math
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


VERSION = "BTC15_RAILWAY_EVIDENCE_LOG_ADAPTER_V1"
CONTRACT_LENGTH_SEC = 900.0


@dataclass(frozen=True)
class ParsedEvent:
    observed_at_utc: str
    source: str
    kind: str
    contract_id: Optional[str] = None
    fields: Dict[str, Any] = field(default_factory=dict)
    raw_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContractWindow:
    contract_id: str
    start_utc: str
    end_utc: str
    rollover_quote_lag_sec: Optional[float] = None

    def start_dt(self) -> datetime:
        return _dt(self.start_utc)

    def end_dt(self) -> datetime:
        return _dt(self.end_utc)


def _dt(value: Any) -> datetime:
    d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _float(text: Any) -> Optional[float]:
    try:
        x = float(text)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _bool(text: Any) -> Optional[bool]:
    if isinstance(text, bool):
        return text
    s = str(text).strip().lower()
    if s == "true":
        return True
    if s == "false":
        return False
    return None


ROLLOVER_RE = re.compile(
    r"ROLLOVER PROBE V3(?: SUMMARY)? \| boundary=(?P<boundary>[^ |]+) "
    r"\| target=(?P<ticker>KXBTC15M-[A-Z0-9-]+)"
)
ROLLOVER_SUMMARY_LAG_RE = re.compile(r"\| exact_active_quoted=(?P<lag>-?\d+(?:\.\d+)?)")
COMBINED_LATE_RE = re.compile(
    r"COMBINED V2 LATE START \| (?P<ticker>KXBTC15M-[A-Z0-9-]+) "
    r"\| first_seen_lag=(?P<lag>[^s|]+)s"
)
BRTI_HEARTBEAT_RE = re.compile(
    r"BRTI_SHARED HEARTBEAT \| status=(?P<status>[A-Z_]+) "
    r"\| clean=(?P<clean>True|False) "
    r"\| age_ms=(?P<age>\d+(?:\.\d+)?) "
    r"\| seq=(?P<seq>\d+) "
    r"\| upstream_ok=(?P<ok>\d+)/(?P<attempts>\d+) "
    r"\([^)]*\) \| 429=(?P<count429>\d+) \| errors=(?P<errors>\d+)"
)
PARITY_RE = re.compile(
    r"PARITY (?P<result>PASS|FAIL) \| (?P<ticker>KXBTC15M-[A-Z0-9-]+) "
    r"\| age (?P<kalshi_age>\d+(?:\.\d+)?)s .*?"
    r"BRTI .*? @ (?P<brti_age>\d+(?:\.\d+)?)s"
)
CONTRACT_STATUS_RE = re.compile(
    r"^(?P<clock>\d{2}:\d{2}:\d{2}Z) \| "
    r"(?P<ticker>KXBTC15M-[A-Z0-9-]+) \| "
    r"(?P<minutes>\d+(?:\.\d+)?)m left"
)
DIRECT_BRTI_RE = re.compile(
    r"^\s*DIRECT BRTI \| .*? \| age (?P<age>\d+(?:\.\d+)?)s "
    r"\| ready (?P<ready>True|False)"
)
FINAL_COVERAGE_RE = re.compile(
    r"FINAL V4 COVERAGE-ELIGIBLE CONTRACT \| "
    r"(?P<ticker>KXBTC15M-[A-Z0-9-]+) \| first_seen_left=(?P<left>\d+(?:\.\d+)?)s"
)
EARLY_COVERAGE_RE = re.compile(
    r"EARLY COVERAGE-ELIGIBLE CONTRACT \| "
    r"(?P<ticker>KXBTC15M-[A-Z0-9-]+) \| first_seen_left=(?P<left>\d+(?:\.\d+)?)s"
)
FINAL_LOCK_RE = re.compile(
    r"FINAL V4 FIRST LOCK \| (?P<ticker>KXBTC15M-[A-Z0-9-]+) "
    r"\| (?P<side>UP|DOWN) \| .*?left=(?P<minutes>\d+(?:\.\d+)?)m "
    r"\| ask=(?P<ask>\d+(?:\.\d+)?)"
)
FINAL_SETTLED_RE = re.compile(
    r"FINAL SETTLED \| (?P<ticker>KXBTC15M-[A-Z0-9-]+) "
    r"\| call=(?P<call>UP|DOWN) \| official=(?P<official>UP|DOWN) "
    r"\| correct=(?P<correct>True|False)"
)
EARLY_SETTLED_RE = re.compile(
    r"EARLY SETTLED \| (?P<ticker>KXBTC15M-[A-Z0-9-]+) "
    r"\| early=(?P<call>UP|DOWN) \| official=(?P<official>UP|DOWN) "
    r"\| same_side=(?P<correct>True|False)"
)
EARLY_FIRST_RE = re.compile(
    r"EARLY FIRST OPPORTUNITY \| (?P<ticker>KXBTC15M-[A-Z0-9-]+) "
    r"\| (?P<side>UP|DOWN) \| .*?left=(?P<minutes>\d+(?:\.\d+)?)m "
    r"\| ask=(?P<ask>\d+(?:\.\d+)?)"
)
WARNING_429_RE = re.compile(r"(?:PARITY WARNING|DIRECT BRTI WARNING).*?429 Client Error")
COINBASE_TIMEOUT_RE = re.compile(r"Coinbase.*?(?:ReadTimeout|read timeout)", re.IGNORECASE)


def parse_log_entry(
    timestamp: str,
    message: str,
    *,
    source: str,
) -> Optional[ParsedEvent]:
    """Parse one Railway log record.

    Unknown lines return ``None`` rather than inventing semantics.
    """
    observed = _iso(_dt(timestamp))
    msg = str(message)

    m = ROLLOVER_RE.search(msg)
    if m:
        fields: Dict[str, Any] = {"boundary_utc": m.group("boundary")}
        lag = ROLLOVER_SUMMARY_LAG_RE.search(msg)
        if lag:
            fields["rollover_quote_lag_sec"] = _float(lag.group("lag"))
        return ParsedEvent(
            observed, source, "ROLLOVER_PROBE",
            m.group("ticker"), fields, msg,
        )

    m = COMBINED_LATE_RE.search(msg)
    if m:
        return ParsedEvent(
            observed, source, "COMBINED_LATE_START", m.group("ticker"),
            {"combined_first_seen_lag_sec": _float(m.group("lag"))}, msg,
        )

    m = BRTI_HEARTBEAT_RE.search(msg)
    if m:
        return ParsedEvent(
            observed, source, "BRTI_HEARTBEAT", None,
            {
                "brti_status": m.group("status"),
                "brti_clean": _bool(m.group("clean")),
                "brti_age_sec": _float(m.group("age")) / 1000.0,
                "brti_seq": int(m.group("seq")),
                "brti_upstream_ok_total": int(m.group("ok")),
                "brti_attempts_total": int(m.group("attempts")),
                "brti_429_total": int(m.group("count429")),
                "brti_errors_total": int(m.group("errors")),
            },
            msg,
        )

    m = PARITY_RE.search(msg)
    if m:
        return ParsedEvent(
            observed, source, f"PARITY_{m.group('result')}", m.group("ticker"),
            {
                "parity_ok": m.group("result") == "PASS",
                "kalshi_age_sec": _float(m.group("kalshi_age")),
                "brti_age_sec": _float(m.group("brti_age")),
            },
            msg,
        )

    m = CONTRACT_STATUS_RE.search(msg)
    if m:
        return ParsedEvent(
            observed, source, "CONTRACT_STATUS", m.group("ticker"),
            {"seconds_left": _float(m.group("minutes")) * 60.0},
            msg,
        )

    m = DIRECT_BRTI_RE.search(msg)
    if m:
        return ParsedEvent(
            observed, source, "DIRECT_BRTI", None,
            {
                "brti_age_sec": _float(m.group("age")),
                "direct_brti_ready": _bool(m.group("ready")),
            },
            msg,
        )

    m = FINAL_COVERAGE_RE.search(msg)
    if m:
        return ParsedEvent(
            observed, source, "FINAL_COVERAGE_ELIGIBLE", m.group("ticker"),
            {"seconds_left": _float(m.group("left")), "final_coverage_eligible": True},
            msg,
        )

    m = EARLY_COVERAGE_RE.search(msg)
    if m:
        return ParsedEvent(
            observed, source, "EARLY_COVERAGE_ELIGIBLE", m.group("ticker"),
            {"seconds_left": _float(m.group("left")), "early_coverage_eligible": True},
            msg,
        )

    m = FINAL_LOCK_RE.search(msg)
    if m:
        return ParsedEvent(
            observed, source, "FINAL_LOCK", m.group("ticker"),
            {
                "final_side": m.group("side"),
                "seconds_left": _float(m.group("minutes")) * 60.0,
                "final_ask": _float(m.group("ask")),
            },
            msg,
        )

    m = FINAL_SETTLED_RE.search(msg)
    if m:
        return ParsedEvent(
            observed, source, "FINAL_SETTLED", m.group("ticker"),
            {
                "final_side": m.group("call"),
                "official_side": m.group("official"),
                "final_correct": _bool(m.group("correct")),
            },
            msg,
        )

    m = EARLY_FIRST_RE.search(msg)
    if m:
        return ParsedEvent(
            observed, source, "EARLY_OPPORTUNITY", m.group("ticker"),
            {
                "early_side": m.group("side"),
                "seconds_left": _float(m.group("minutes")) * 60.0,
                "early_ask": _float(m.group("ask")),
            },
            msg,
        )

    m = EARLY_SETTLED_RE.search(msg)
    if m:
        return ParsedEvent(
            observed, source, "EARLY_SETTLED", m.group("ticker"),
            {
                "early_side": m.group("call"),
                "official_side": m.group("official"),
                "early_same_side": _bool(m.group("correct")),
            },
            msg,
        )

    if WARNING_429_RE.search(msg):
        return ParsedEvent(
            observed, source, "BRTI_429_WARNING", None,
            {"brti_429_warning": True}, msg,
        )

    if COINBASE_TIMEOUT_RE.search(msg):
        return ParsedEvent(
            observed, source, "COINBASE_TIMEOUT", None,
            {"coinbase_timeout": True}, msg,
        )

    return None


def parse_many(
    rows: Iterable[Mapping[str, Any]],
    *,
    source: str,
    timestamp_field: str = "timestamp",
    message_field: str = "message",
) -> List[ParsedEvent]:
    out: List[ParsedEvent] = []
    for row in rows:
        if timestamp_field not in row or message_field not in row:
            continue
        try:
            event = parse_log_entry(
                str(row[timestamp_field]),
                str(row[message_field]),
                source=source,
            )
        except Exception:
            continue
        if event is not None:
            out.append(event)
    out.sort(key=lambda e: _dt(e.observed_at_utc))
    return out


def build_contract_windows(events: Sequence[ParsedEvent]) -> List[ContractWindow]:
    """Build immutable 15-minute windows from exact-ticker rollover probe events."""
    by_contract: Dict[str, Dict[str, Any]] = {}
    for event in events:
        if event.kind != "ROLLOVER_PROBE" or not event.contract_id:
            continue
        boundary = event.fields.get("boundary_utc")
        if not boundary:
            continue
        start = _dt(boundary)
        row = by_contract.setdefault(
            event.contract_id,
            {
                "start": start,
                "lag": None,
            },
        )
        if start < row["start"]:
            row["start"] = start
        lag = event.fields.get("rollover_quote_lag_sec")
        if isinstance(lag, (int, float)):
            row["lag"] = float(lag)

    windows = [
        ContractWindow(
            contract_id=cid,
            start_utc=_iso(v["start"]),
            end_utc=_iso(v["start"] + timedelta(seconds=CONTRACT_LENGTH_SEC)),
            rollover_quote_lag_sec=v["lag"],
        )
        for cid, v in by_contract.items()
    ]
    windows.sort(key=lambda w: w.start_dt())
    return windows


def _window_for_time(
    at: datetime,
    windows: Sequence[ContractWindow],
) -> Optional[ContractWindow]:
    matches = [w for w in windows if w.start_dt() <= at < w.end_dt()]
    if len(matches) != 1:
        return None
    return matches[0]


def attach_global_events(
    events: Sequence[ParsedEvent],
    windows: Sequence[ContractWindow],
) -> List[ParsedEvent]:
    """Attach contract-less feed events only when exactly one window contains them."""
    out: List[ParsedEvent] = []
    for event in events:
        if event.contract_id:
            out.append(event)
            continue
        window = _window_for_time(_dt(event.observed_at_utc), windows)
        if window is None:
            out.append(event)
            continue
        fields = dict(event.fields)
        fields["seconds_left"] = max(
            0.0,
            (window.end_dt() - _dt(event.observed_at_utc)).total_seconds(),
        )
        out.append(
            ParsedEvent(
                event.observed_at_utc,
                event.source,
                event.kind,
                window.contract_id,
                fields,
                event.raw_message,
            )
        )
    return out


def to_integrity_observations(
    events: Sequence[ParsedEvent],
    windows: Sequence[ContractWindow],
) -> List[Dict[str, Any]]:
    """Convert parsed events to rows consumed by Evidence Integrity Adapter V1.

    The function deliberately emits only facts actually supported by a log line.
    Missing operational/feed fields remain absent and become UNKNOWN downstream.
    """
    window_by_id = {w.contract_id: w for w in windows}
    rows: List[Dict[str, Any]] = []
    for event in attach_global_events(events, windows):
        if not event.contract_id:
            continue
        row: Dict[str, Any] = {
            "contract_id": event.contract_id,
            "observed_at_utc": event.observed_at_utc,
            "source_kind": event.kind,
            "source_service": event.source,
        }
        row.update(event.fields)

        window = window_by_id.get(event.contract_id)
        if window and "seconds_left" not in row:
            at = _dt(event.observed_at_utc)
            if window.start_dt() <= at < window.end_dt():
                row["seconds_left"] = max(
                    0.0,
                    (window.end_dt() - at).total_seconds(),
                )
        if window and window.rollover_quote_lag_sec is not None:
            row["exact_ticker_rollover_quote_lag_sec"] = window.rollover_quote_lag_sec

        # A heartbeat's explicit clean=False is evidence of feed trouble. It is
        # not converted to operational process failure; those are separate gates.
        if event.kind == "BRTI_HEARTBEAT":
            if row.get("brti_clean") is False:
                row["brti_feed_clean"] = False
            elif row.get("brti_clean") is True:
                row["brti_feed_clean"] = True

        rows.append(row)

    rows.sort(key=lambda r: (_dt(r["observed_at_utc"]), r["contract_id"], r["source_kind"]))
    return rows


def dump_jsonl(rows: Iterable[Mapping[str, Any]]) -> str:
    return "\n".join(json.dumps(dict(r), sort_keys=True) for r in rows)
