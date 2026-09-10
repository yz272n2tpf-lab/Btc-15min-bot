#!/usr/bin/env python3
"""Research-only BRTI resilience guard.

Purpose:
- improve BRTI transport reliability without weakening V6/V7 qualification
- distinguish transport failure from true missing/invalid BRTI data
- keep a tiny diagnostic last-known-good cache that is NEVER used to qualify a signal
- support an optional secondary verifier callback for endpoint cross-checking
- expose compact counters for checkpoint reports

Signal-only. NO ORDERS. Production behavior is untouched.
"""

from dataclasses import dataclass, asdict
from typing import Callable, Optional, Any, Dict, Tuple
import time


@dataclass
class BrtiSample:
    value: Optional[float]
    status: str
    attempts: int
    latency_ms: float
    verifier_value: Optional[float]
    verifier_status: str
    last_good_value: Optional[float]
    last_good_age_s: Optional[float]
    last_error_type: Optional[str] = None
    last_error_text: Optional[str] = None

    @property
    def clean_for_qualification(self) -> bool:
        # Important safety invariant: only a fresh primary success is clean.
        # Cached values and verifier-only values are diagnostic evidence only.
        return self.status == 'PRIMARY_OK' and self.value is not None


class BrtiResilienceGuard:
    def __init__(
        self,
        retries: int = 4,
        backoff_s: Tuple[float, ...] = (0.05, 0.10, 0.20),
        diagnostic_cache_ttl_s: float = 3.0,
    ) -> None:
        self.retries = max(1, int(retries))
        self.backoff_s = tuple(float(x) for x in backoff_s)
        self.diagnostic_cache_ttl_s = max(0.0, float(diagnostic_cache_ttl_s))
        self.last_good_value: Optional[float] = None
        self.last_good_ts: Optional[float] = None
        self.counters: Dict[str, int] = {
            'samples': 0,
            'primary_ok': 0,
            'recovered_by_retry': 0,
            'primary_missing': 0,
            'primary_error': 0,
            'error_timeout': 0,
            'error_http': 0,
            'error_connection': 0,
            'error_other': 0,
            'verifier_ok': 0,
            'verifier_disagree': 0,
            'verifier_missing': 0,
            'diagnostic_cache_available': 0,
        }

    @staticmethod
    def _valid(v: Any) -> bool:
        try:
            x = float(v)
        except (TypeError, ValueError):
            return False
        return x > 0.0

    @staticmethod
    def _classify_exception(exc: Exception) -> str:
        """Classify transport errors without importing the caller's HTTP library."""
        name = exc.__class__.__name__.lower()
        text = str(exc).lower()
        if 'timeout' in name or 'timed out' in text or 'timeout' in text:
            return 'timeout'
        if 'http' in name or 'status code' in text or '503' in text or '502' in text or '429' in text:
            return 'http'
        if 'connection' in name or 'connect' in text or 'dns' in text or 'name resolution' in text:
            return 'connection'
        return 'other'

    def _cache_state(self, now: float) -> Tuple[Optional[float], Optional[float]]:
        if self.last_good_value is None or self.last_good_ts is None:
            return None, None
        age = max(0.0, now - self.last_good_ts)
        if age <= self.diagnostic_cache_ttl_s:
            self.counters['diagnostic_cache_available'] += 1
            return self.last_good_value, age
        return None, age

    def fetch(
        self,
        primary_fetch: Callable[[], Optional[float]],
        verifier_fetch: Optional[Callable[[], Optional[float]]] = None,
        now: Optional[float] = None,
    ) -> BrtiSample:
        start = time.monotonic()
        wall_now = time.time() if now is None else float(now)
        self.counters['samples'] += 1

        primary_value: Optional[float] = None
        status = 'PRIMARY_MISSING'
        attempts = 0
        saw_exception = False
        last_error_type: Optional[str] = None
        last_error_text: Optional[str] = None

        for attempt in range(self.retries):
            attempts = attempt + 1
            try:
                v = primary_fetch()
                if self._valid(v):
                    primary_value = float(v)
                    status = 'PRIMARY_OK'
                    self.last_good_value = primary_value
                    self.last_good_ts = wall_now
                    self.counters['primary_ok'] += 1
                    if attempt > 0:
                        self.counters['recovered_by_retry'] += 1
                    break
            except Exception as exc:
                saw_exception = True
                last_error_type = self._classify_exception(exc)
                last_error_text = str(exc)[:160]

            if attempt < self.retries - 1:
                delay = self.backoff_s[min(attempt, len(self.backoff_s) - 1)] if self.backoff_s else 0.0
                if delay > 0:
                    time.sleep(delay)

        if primary_value is None:
            if saw_exception:
                status = 'PRIMARY_ERROR'
                self.counters['primary_error'] += 1
                self.counters['error_' + (last_error_type or 'other')] += 1
            else:
                self.counters['primary_missing'] += 1

        verifier_value: Optional[float] = None
        verifier_status = 'NOT_RUN'
        if verifier_fetch is not None:
            try:
                vv = verifier_fetch()
                if self._valid(vv):
                    verifier_value = float(vv)
                    verifier_status = 'VERIFIER_OK'
                    self.counters['verifier_ok'] += 1
                    if primary_value is not None:
                        # Cross-check only; disagreement is diagnostic and never substitutes for primary.
                        if abs(verifier_value - primary_value) > 25.0:
                            verifier_status = 'VERIFIER_DISAGREE'
                            self.counters['verifier_disagree'] += 1
                else:
                    verifier_status = 'VERIFIER_MISSING'
                    self.counters['verifier_missing'] += 1
            except Exception:
                verifier_status = 'VERIFIER_ERROR'

        cached_value, cached_age = self._cache_state(wall_now)
        latency_ms = (time.monotonic() - start) * 1000.0

        return BrtiSample(
            value=primary_value,
            status=status,
            attempts=attempts,
            latency_ms=latency_ms,
            verifier_value=verifier_value,
            verifier_status=verifier_status,
            last_good_value=cached_value,
            last_good_age_s=cached_age,
            last_error_type=last_error_type,
            last_error_text=last_error_text,
        )

    def compact_stats(self) -> str:
        c = self.counters
        n = max(1, c['samples'])
        return (
            'BRTI_RESILIENCE | samples=%d | primary_ok=%d (%.1f%%) | retry_recovered=%d | '
            'missing=%d | errors=%d | timeout=%d | http=%d | connection=%d | other=%d | '
            'verifier_ok=%d | verifier_disagree=%d | diag_cache=%d'
            % (
                c['samples'], c['primary_ok'], 100.0 * c['primary_ok'] / n,
                c['recovered_by_retry'], c['primary_missing'], c['primary_error'],
                c['error_timeout'], c['error_http'], c['error_connection'], c['error_other'],
                c['verifier_ok'], c['verifier_disagree'], c['diagnostic_cache_available'],
            )
        )

    def snapshot(self) -> Dict[str, int]:
        return dict(self.counters)


def qualification_value(sample: BrtiSample) -> Optional[float]:
    """Return only data that is safe for V6/V7 qualification.

    This intentionally refuses cached values and verifier-only values.
    """
    return sample.value if sample.clean_for_qualification else None


def diagnostic_dict(sample: BrtiSample) -> Dict[str, Any]:
    """JSON/log friendly diagnostic payload."""
    d = asdict(sample)
    d['clean_for_qualification'] = sample.clean_for_qualification
    return d


def _self_test() -> None:
    # Retry recovery should become clean qualification data.
    seq = iter([None, None, 78000.25])
    g = BrtiResilienceGuard(retries=4, backoff_s=(0, 0, 0))
    s = g.fetch(lambda: next(seq), now=100.0)
    assert s.clean_for_qualification
    assert s.attempts == 3
    assert qualification_value(s) == 78000.25
    assert g.counters['recovered_by_retry'] == 1

    # Total primary failure must NEVER qualify from cache or verifier.
    s2 = g.fetch(lambda: None, verifier_fetch=lambda: 78001.0, now=101.0)
    assert not s2.clean_for_qualification
    assert qualification_value(s2) is None
    assert s2.last_good_value == 78000.25
    assert s2.verifier_value == 78001.0

    # Expired diagnostic cache disappears.
    s3 = g.fetch(lambda: None, now=110.0)
    assert s3.last_good_value is None

    # Failure classification is diagnostic only and must never qualify.
    g2 = BrtiResilienceGuard(retries=1, backoff_s=())
    def _timeout():
        raise TimeoutError('timed out')
    s4 = g2.fetch(_timeout, now=200.0)
    assert not s4.clean_for_qualification
    assert s4.last_error_type == 'timeout'
    assert g2.counters['error_timeout'] == 1

    print('BRTI_RESILIENCE_SELF_TEST | PASS')
    print(g.compact_stats())
    print(g2.compact_stats())


if __name__ == '__main__':
    _self_test()
