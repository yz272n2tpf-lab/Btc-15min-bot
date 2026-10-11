"""Evidence-bound EARLY opportunity gate, not a new price forecasting model.

There are deliberately NO trusted production profiles in this repository.
An externally reviewed, hash-pinned validation profile and exact causal forecast
are required. Fixture profiles exercise mechanics but never gain live authority.
No fixed profit target, minimum contract-clock cutoff or invented latency.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import math

from btc15_v2_product.directional import qualify, protected_frame
from btc15_v2_product.early_entry import assess, route, fee_valid
from btc15_v2_product.opportunities import fee_scenario

POLICY = 'OFFLINE_EARLY_OPPORTUNITY_INTEGRITY_V1'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_quote(f):
    q=f['quote']
    if not all(type(q.get(k)) is int and q[k]>=0 for k in ('sid','seq')):
        raise ValueError('QUOTE_SEQUENCE_REQUIRED')
    if abs(f['up_ask']+f['down_bid']-1)>1e-9 or abs(f['down_ask']+f['up_bid']-1)>1e-9:
        raise ValueError('BINARY_BID_ASK_MAPPING')


def settlement_context(f):
    """Exact known sum and UNOBSERVED-second hurdle, not a settlement forecast.

Samples are already received, same-contract, one per second in [close-60,close).
Missing past seconds stay unknown; revised/future seconds cannot be smuggled in.
Official rounding/tie semantics must be handled by a validated forecast provider.
"""
    cut, close = f['feature_cutoff'], f['official_close']
    if cut < close-60:
        return dict(phase='BEFORE_AVERAGING', known_count=0, unknown_count=60,
                    known_sum='0', raw_unknown_mean_hurdle=str(f['target']),
                    evidence_hash=None, missing_elapsed_seconds=[])
    e = f.get('settlement_evidence')
    if not isinstance(e, dict):
        raise ValueError('CAUSAL_SETTLEMENT_SAMPLES_REQUIRED')
    if (e.get('contract') != f['contract'] or e.get('target') != f['target'] or
        e.get('official_close') != close or e.get('asof') != cut or
        e.get('owner_epoch') != f['brti']['delivery']['owner_epoch'] or
        not isinstance(e.get('samples'), list)):
        raise ValueError('SETTLEMENT_BINDING')
    seen = set(); total = Decimal(0)
    for sample in e['samples']:
        second, value, received = (sample.get(k) for k in ('second', 'value', 'received_ts'))
        if (type(second) is not int or second in seen or not close-60 <= second < close or
            not finite(value) or value <= 0 or not finite(received) or
            not second <= received <= cut):
            raise ValueError('SETTLEMENT_CAUSAL_SECOND_INVALID')
        seen.add(second); total += Decimal(str(value))
    unknown = 60-len(seen)
    hurdle = ((Decimal(60)*Decimal(str(f['target']))-total)/unknown) if unknown else None
    elapsed = set(range(int(close-60), min(int(cut)+1, int(close))))
    return dict(phase='AVERAGING', known_count=len(seen), unknown_count=unknown,
                known_sum=str(total), raw_unknown_mean_hurdle=str(hurdle) if hurdle is not None else None,
                evidence_hash=digest(e), missing_elapsed_seconds=sorted(elapsed-seen),
                raw_average=str(total/len(seen)) if seen else None,
                official_rounding_applied=False, settlement_authority=False)


class EvidenceRegistry:
    """Trust is an explicit reviewed profile hash, never an incoming 'validated' flag.

This gate verifies binding/causality and consumes a prior validation decision;
it does not manufacture or independently establish statistical validation.
"""
    def __init__(self, profiles=(), *, permit_test_fixtures=False):
        self.profiles = {digest(p): deepcopy(p) for p in profiles}
        self.permit_test_fixtures = permit_test_fixtures

    def verify(self, f, prediction, settlement):
        if not isinstance(prediction, dict):
            raise ValueError('VALIDATED_OPPORTUNITY_EVIDENCE_REQUIRED')
        profile = self.profiles.get(prediction.get('profile_sha256'))
        if profile is None:
            raise ValueError('UNREVIEWED_OPPORTUNITY_PROFILE')
        cls = profile.get('evidence_class')
        if cls == 'SYNTHETIC_FIXTURE':
            if not self.permit_test_fixtures:
                raise ValueError('FIXTURE_CANNOT_QUALIFY_REAL_EVIDENCE')
        elif cls != 'INDEPENDENT_HELDOUT_REVIEW':
            raise ValueError('PROFILE_VALIDATION_CLASS')
        if (profile.get('purpose') != 'EARLY_DIRECTIONAL_OPPORTUNITY' or
            profile.get('validated') is not True or profile.get('not_for_scalp') is not True or
            not isinstance(profile.get('validation_report_sha256'), str) or
            len(profile['validation_report_sha256']) != 64 or
            not finite(profile.get('validation_completed_ts')) or
            profile['validation_completed_ts'] >= f['official_open']):
            raise ValueError('PROFILE_VALIDATION_OR_LEAKAGE')
        horizon = profile.get('horizon_seconds')
        budget = profile.get('manual_execution_budget_seconds')
        reserve = profile.get('execution_reserve_dollars')
        # Horizon is supplied by the prior independent study, not tuned here.
        if (not finite(horizon) or horizon <= 0 or not finite(budget) or budget <= 0 or
            not finite(reserve) or reserve < 0 or not profile.get('horizon_evidence_sha256') or
            not profile.get('execution_evidence_sha256')):
            raise ValueError('VALIDATED_HORIZON_AND_EXECUTION_EVIDENCE_REQUIRED')
        if (prediction.get('frame_sha256') != digest(f) or
            prediction.get('contract') != f['contract'] or prediction.get('target') != f['target'] or
            prediction.get('side') != f['fair']['side'] or
            prediction.get('feature_cutoff') != f['feature_cutoff'] or
            prediction.get('settlement_evidence_hash') != settlement['evidence_hash'] or
            prediction.get('horizon_seconds') != horizon):
            raise ValueError('OPPORTUNITY_FRAME_BINDING')
        available, until = prediction.get('available_ts'), prediction.get('valid_until')
        if (not finite(available) or not finite(until) or
            not f['feature_cutoff'] <= available <= f['captured_ts'] <= until or
            until > f['official_close']):
            raise ValueError('OPPORTUNITY_CAUSAL_TIME')
        mean, lower = prediction.get('mean_future_bid'), prediction.get('lower_bound_mean_future_bid')
        if not all(finite(x) and 0 <= x <= 1 for x in (mean, lower)) or lower > mean:
            raise ValueError('LIQUIDATION_ESTIMATE_INVALID')
        if (prediction.get('basis') != 'HELDOUT_SAME_SIDE_BID_AT_VALIDATED_HORIZON' or
            prediction.get('model_fair_used_as_future_bid') is not False or
            prediction.get('directional_support') is not True or
            prediction.get('regime_in_validation_support') is not True or
            prediction.get('uncertainty_method') != profile.get('uncertainty_method') or
            not prediction.get('uncertainty_method')):
            raise ValueError('SUPPORTED_LIQUIDATION_ESTIMATE_REQUIRED')
        if settlement['phase'] == 'AVERAGING' and (
            prediction.get('settlement_conditioned') is not True or
            prediction.get('settlement_path_supported') is not True):
            raise ValueError('SETTLEMENT_PATH_UNSUPPORTED')
        return profile


def qualify_opportunity(f, now, prediction=None, registry=None):
    result = dict(policy=POLICY, ready=False, reasons=[], signal_only=True, orders=False,
                  actionable=False, mode='OFFLINE_CANDIDATE', economics=None,
                  guaranteed_profit=False, live_profitability_validated=False)
    try:
        if f.get('kind') != 'NATIVE_DECISION':
            raise ValueError('NATIVE_DECISION_REQUIRED')
        expires = qualify(f, now)
        validate_quote(f)
        raw, qualified = protected_frame(f, now)
        baseline = assess(raw, f); raw, _ = route(raw, qualified, baseline)
        result['baseline'] = baseline
        # Apply full evidence requirements to BOTH historical and value routes.
        if not raw['early']['ready'] or not baseline['ready']:
            raise ValueError('EXISTING_DIRECTIONAL_AND_COST_QUALIFICATION_FAILED')
        settlement = settlement_context(f); result['settlement'] = settlement
        profile = (registry or EvidenceRegistry()).verify(f, prediction, settlement)
        side = f['fair']['side']; ask, bid = f[side.lower()+'_ask'], f[side.lower()+'_bid']
        horizon, budget = profile['horizon_seconds'], profile['manual_execution_budget_seconds']
        # Data age is not a substitute for the opportunity's measured horizon.
        if now+horizon+budget >= f['official_close']:
            raise ValueError('OPPORTUNITY_HORIZON_DOES_NOT_FIT_CONTRACT')
        if now > prediction['valid_until']:
            raise ValueError('OPPORTUNITY_EXPIRED')
        if not fee_valid(f):
            raise ValueError('CURRENT_FEES_REQUIRED')
        lower = prediction['lower_bound_mean_future_bid']; multiplier = f['fee_schedule']['multiplier']
        entry_fee = fee_scenario(ask, multiplier)
        # Bound fees for ANY possible exit price, not merely fee(E[BID]).
        exit_fee_upper = fee_scenario(.5, multiplier)
        spread = ask-bid; reserve = max(spread, profile['execution_reserve_dollars'])
        conservative_net = lower-ask-entry_fee-exit_fee_upper-reserve
        result['economics'] = dict(original_ask=ask, current_same_side_bid=bid,
            observed_spread=spread, entry_fee=entry_fee, exit_fee_upper=exit_fee_upper,
            execution_reserve=reserve, mean_future_bid=prediction['mean_future_bid'],
            lower_bound_mean_future_bid=lower, conservative_expected_net=conservative_net,
            spread_basis='ASK-to-future-BID includes crossing; reserve is additional execution stress',
            inference='Statistical bound on mean, not guaranteed per-trade profit', realized_profit=None)
        result['economics'].update(quantity=1,fee_basis='Current published quadratic schedule; account/event overrides and actual fills unverified')
        if conservative_net <= 0 or lower <= bid:
            raise ValueError('NO_SUPPORTED_NET_APPRECIATION_AFTER_COSTS')
        result.update(ready=True, horizon_seconds=horizon, execution_budget_seconds=budget,
                      horizon_end=now+horizon, profile_sha256=prediction['profile_sha256'],
                      evidence_class=profile['evidence_class'], prediction_sha256=digest(prediction),
                      expires_at=min(expires, prediction['valid_until']))
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        result['reasons'].append(str(exc))
    return result
