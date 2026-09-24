"""One causal decision cutoff after input receipt. SIGNAL ONLY / NO ORDERS."""
from datetime import datetime, timezone
import json
import math


def utc(value):
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Input clock requires a timezone')
    return parsed.astimezone(timezone.utc)


def decision_time(opened, closed, btc_source, btc_observed, now):
    """Keep source/receipt clocks intact; never move the cutoff into the future."""
    opened, closed, source, observed, now = map(utc, (opened, closed, btc_source, btc_observed, now))
    if (closed-opened).total_seconds() != 900 or opened.timestamp() % 900 != 0:
        raise ValueError('Official 15-minute window required')
    if not opened <= now < closed:
        raise ValueError('Contract changed during input collection')
    if not source <= observed <= now or (now-source).total_seconds() > 10:
        raise ValueError('BTC source/receipt unqualified at decision')
    return now


def record_model_input(path, *, ticker, target, decision, btc_source, btc_observed,
                       btc_price, features, feature_names, weights_sha256, artifact_sha256):
    """Append replayable past-only model inputs to a new versioned journal.

    Existing CSV layouts and evidence are untouched. No outcome is recorded in
    a feature row. Hashes identify the model; timestamps retain their meanings.
    """
    decision, source, observed = map(utc, (decision, btc_source, btc_observed))
    if not source <= observed <= decision:
        raise ValueError('Model cutoff precedes input receipt')
    if len(feature_names) != len(set(feature_names)) or any(k not in features for k in feature_names):
        raise ValueError('Model feature schema mismatch')
    vector = {k:float(features[k]) for k in feature_names}
    if not all(math.isfinite(v) for v in [float(target), float(btc_price), *vector.values()]):
        raise ValueError('Nonfinite model input')
    row = dict(schema='BTC15_FAIR_INPUT_V1', ticker=ticker, target=float(target),
               decision_utc=decision.isoformat(), btc_source_utc=source.isoformat(),
               btc_observed_utc=observed.isoformat(), btc_price=float(btc_price),
               features=vector, feature_order=feature_names, weights_sha256=weights_sha256,
               artifact_sha256=artifact_sha256, signal_only=True, orders=False)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(row, separators=(',', ':'), allow_nan=False)+'\n')

