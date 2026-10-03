"""External availability preconditions. No alpha, source polling or reducer calls.

Bounds are supplied by a trusted monitor, never learned from journal telemetry.
Certificates describe a continuous clock epoch with no steps/suspension ambiguity.
The caller must authenticate/approve them. No production clock provider ships.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction as F
import math

from btc15_directional_signal_authority_v1 import utc

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
SECOND = 1_000_000


def micros(stamp):
    d = utc(stamp) - EPOCH
    return (d.days * 86400 + d.seconds) * SECOND + d.microseconds


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('NONFINITE_OR_MISSING_CLOCK_INPUT')
    return F(value)  # Preserve the represented numeric value, not a rounded clock.


@dataclass(frozen=True)
class Bound:
    clock_id: str
    epoch: str
    measurement_id: str
    reference_utc: str
    valid_from_utc: str
    valid_until_utc: str
    error_us: int
    rate_ppm: int
    read_error_us: int = 0

    def witness(self, label):
        t, ref = micros(label), micros(self.reference_utc)
        if (not all((self.clock_id, self.epoch, self.measurement_id))
                or type(self.error_us) is not int or self.error_us < 0
                or type(self.read_error_us) is not int or self.read_error_us < 0
                or type(self.rate_ppm) is not int or not 0 <= self.rate_ppm < SECOND
                or not micros(self.valid_from_utc) <= t <= micros(self.valid_until_utc)):
            raise ValueError('CLOCK_BOUND_INVALID_OR_EXPIRED')
        # Assumes the monitor's no-step epoch and stated rate envelope. Unknown
        # drift must not be encoded as zero. error_us is reference offset error;
        # each timestamp read also has its own independent read_error_us.
        rate = F(self.rate_ppm, SECOND)
        error = self.error_us + self.read_error_us + abs(t - ref) * rate / (1 - rate)
        return Witness(label, t-error, t+error, self.clock_id, self.epoch,
                       self.measurement_id, rate, self.read_error_us)


@dataclass(frozen=True)
class Witness:
    label: str
    lo: F
    hi: F
    clock_id: str
    epoch: str
    measurement_id: str
    rate: F
    read_error_us: int


def elapsed(later, earlier):
    lo, hi = later.lo - earlier.hi, later.hi - earlier.lo
    # Same certificate/continuous epoch permits common-offset cancellation.
    # It does NOT permit cancellation across unverified epochs/certificates.
    if (later.clock_id, later.epoch, later.measurement_id) == (
            earlier.clock_id, earlier.epoch, earlier.measurement_id):
        delta = micros(later.label) - micros(earlier.label)
        r = max(later.rate, earlier.rate)
        read_error = later.read_error_us + earlier.read_error_us
        ends = tuple(F(d)/(1+sign*r) for d in (delta-read_error,delta+read_error)
                     for sign in (-1,1))
        lo, hi = max(lo, min(ends)), min(hi, max(ends))
    if lo > hi:
        raise ValueError('INCONSISTENT_CLOCK_BOUNDS')
    return lo, hi


def require_order(later, earlier, strict=False):
    lo, _ = elapsed(later, earlier)
    if lo < 0 or (strict and lo <= 0):
        raise ValueError('CLOCK_ORDER_UNCERTAIN')


def range_truth(iv, lower, upper, strict_upper=False):
    lo, hi = iv
    if lo >= lower and (hi < upper if strict_upper else hi <= upper):
        return True
    if hi < lower or (lo >= upper if strict_upper else lo > upper):
        return False
    raise ValueError('CLOCK_PREDICATE_UNCERTAIN')


def witness(bound, stamp):
    if not isinstance(bound, Bound):
        raise ValueError('CLOCK_BOUND_UNAVAILABLE')
    return bound.witness(stamp)


def admit(raw, source, bounds, now, consumer_bound, activated, activation_bound,
          previous=None, consumed=None, consumed_bound=None):
    """Check all time-sensitive frozen branches analytically, not by replaying
    the reducer at invented times. A stable false availability predicate rejects.
    Static evidence/identity/alpha is checked by the unchanged authority itself.
    """
    s = witness(bounds.get('native'), raw['source_timestamp_utc'])
    g = witness(bounds.get('native'), raw['generated_utc'])
    close = witness(bounds.get('native'), raw['timer']['close_utc'])
    p = witness(bounds.get('parity'), raw['parity']['timestamp_utc'])
    q = witness(bounds.get('collector'), source['request_started_utc'])
    receipt = witness(bounds.get('collector'), source['response_received_utc'])
    current = witness(consumer_bound, now)
    active = witness(activation_bound, activated)
    for later, earlier in ((s,active),(g,s),(g,q),(receipt,g),(current,receipt)):
        require_order(later, earlier)
    age = elapsed(current,s)
    if not range_truth(age,0,15*SECOND):raise ValueError('STALE_SOURCE')
    if not range_truth(elapsed(current,p),0,45*SECOND):raise ValueError('STALE_PARITY')
    require_order(close,current,True)
    left = number(raw['timer']['seconds_left'])*SECOND
    if age[1] >= left:raise ValueError('REMAINING_TIME_UNCERTAIN_OR_EXPIRED')
    if not range_truth(elapsed(close,s),0,900*SECOND):
        raise ValueError('CONTRACT_WINDOW_UNCERTAIN')
    # Existing +/-2-second window alignment is preserved, never repurposed as
    # permission to tolerate cross-host skew. Prove the same canonical ticker.
    canonical = round(F(micros(close.label),900*SECOND)) * (900*SECOND)
    if not canonical-2*SECOND <= close.lo <= close.hi <= canonical+2*SECOND:
        raise ValueError('CONTRACT_ALIGNMENT_UNCERTAIN')
    ds = elapsed(close,s)
    if not -2*SECOND <= ds[0]-left <= ds[1]-left <= 2*SECOND:
        raise ValueError('CONTRACT_REMAINING_ALIGNMENT_UNCERTAIN')
    if previous:
        old_s = witness(previous['bounds']['native'],previous['raw']['source_timestamp_utc'])
        old_c = witness(previous['bounds']['native'],previous['raw']['timer']['close_utc'])
        if raw['contract'] != previous['raw']['contract']:
            require_order(close,old_c,True)
        else:
            dc = elapsed(close,old_c)
            if not -2*SECOND <= dc[0] <= dc[1] <= 2*SECOND:
                raise ValueError('CONTRACT_CLOSE_UNCERTAIN')
        if raw['source_timestamp_utc'] != previous['raw']['source_timestamp_utc']:
            require_order(s,old_s,True)
    if consumed is not None:
        cw = witness(consumed_bound, consumed)
        if not range_truth(elapsed(current,cw),0,15*SECOND):
            raise ValueError('PROJECTION_LEASE_EXPIRED')
    # EARLY does not acquire a new BRTI qualification gate. Nevertheless the
    # truth must be stable because confirmation/saw_strong_final can depend on it.
    try:a = number(raw['market'].get('brti_age_seconds'))*SECOND
    except ValueError:
        return dict(brti_age_predicate=False, source_interval_us=[str(x) for x in age],
                    brti_interval_us=None)
    brti = range_truth((a+age[0],a+age[1]),0,5*SECOND)
    return dict(brti_age_predicate=brti, source_interval_us=[str(x) for x in age],
                brti_interval_us=[str(a+x) for x in age])
