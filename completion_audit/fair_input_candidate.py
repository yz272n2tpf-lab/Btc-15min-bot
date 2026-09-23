"""Offline candidate input boundary; not imported by any production entrypoint.

Completed Coinbase candles become available at bucket END. Live spot samples
must carry both a source timestamp and their actual observation timestamp.
This module does not fit models, fetch data, change gates or produce signals.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

OHLCV = ['Open', 'High', 'Low', 'Close', 'Volume']
ROLES = ('fit', 'calibration', 'historical_evaluation_already_opened')


def utc(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError('An explicit UTC-aware timestamp is required')
    return stamp.tz_convert('UTC')


def completed_candles(raw):
    """Index full one-minute candles by earliest possible availability.

    Historical bucket ends are a lower bound on real receipt time. This is not
    a historical API latency reconstruction. In-progress buckets are excluded
    later by the decision cutoff; receipt time never replaces source time.
    """
    if not isinstance(raw.index, pd.DatetimeIndex) or raw.index.tz is None:
        raise ValueError('Candle index must be timezone aware')
    if raw.index.hasnans or raw.index.has_duplicates:
        raise ValueError('Missing or duplicate candle timestamps')
    if any(raw.index != raw.index.floor('min')):
        raise ValueError('Expected one-minute bucket starts')
    frame = raw[OHLCV].astype(float).copy()
    if not np.isfinite(frame.to_numpy()).all():
        raise ValueError('Nonfinite candle value')
    if ((frame[['Open', 'High', 'Low', 'Close']] <= 0).any().any()
            or (frame['Volume'] < 0).any()
            or (frame['High'] < frame[['Open', 'Close', 'Low']].max(axis=1)).any()
            or (frame['Low'] > frame[['Open', 'Close', 'High']].min(axis=1)).any()):
        raise ValueError('Invalid OHLCV candle')
    frame.index = frame.index.tz_convert('UTC') + pd.Timedelta(minutes=1)
    frame.index.name = 'available_at_utc'
    frame['source_utc'] = frame.index
    return frame.sort_index()


def load_frozen_inputs(root, manifest_path):
    """Verify immutable bytes/membership without referring to today's date."""
    root = Path(root).resolve()
    manifest = json.loads(Path(manifest_path).read_text())
    for name, expected in manifest['input_sha256'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Input path escapes frozen root')
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('Frozen input hash mismatch: ' + name)
    roles = manifest['roles']
    if set(roles) != set(ROLES):
        raise ValueError('Missing or unknown role')
    flattened = [ticker for role in ROLES for ticker in roles[role]]
    if len(flattened) != len(set(flattened)) or any(not roles[r] for r in ROLES):
        raise ValueError('Empty or overlapping frozen membership')
    if len(roles['calibration']) < 20:
        raise ValueError('Existing minimum calibration support not met')
    labels = pd.read_csv(root / 'brti_calibration_results.csv')
    if labels['ticker'].duplicated().any() or set(labels['ticker']) != set(flattened):
        raise ValueError('Label universe differs from frozen membership')
    frame = pd.read_csv(root / 'btc_35d_live_cache.csv', index_col='Datetime', parse_dates=True)
    return manifest, labels, completed_candles(frame)


def select_frozen_rows(rows, manifest, minimum_snapshots=10):
    """Fail on lost support instead of repartitioning the surviving contracts."""
    if rows[['ticker', 'elapsed']].duplicated().any():
        raise ValueError('Duplicate contract snapshot')
    roles = manifest['roles']
    intended = {t for role in ROLES for t in roles[role]}
    if set(rows['ticker']) != intended:
        raise ValueError('Missing or extra contracts; do not re-split')
    coverage = rows.groupby('ticker')['elapsed'].nunique()
    if (coverage < minimum_snapshots).any():
        raise ValueError('Frozen contract has insufficient snapshots')
    return {role: rows[rows['ticker'].isin(roles[role])].copy() for role in ROLES}


def frame_at_cut(completed, ticks, cutoff):
    """Combine past completed candles with genuinely observed partial ticks.

    ticks columns: source_utc, observed_utc, price. Replays may contain later
    observations; those rows cannot influence this cutoff. A tick whose source
    time is after its observation time is rejected, not relabeled.
    Full production integration still requires capturing this provenance.
    """
    cut = utc(cutoff)
    if not isinstance(completed.index, pd.DatetimeIndex) or completed.index.tz is None:
        raise ValueError('Completed candle availability must be explicit')
    base = completed.loc[completed.index <= cut, OHLCV + ['source_utc']].copy()
    if ticks.empty:
        return base
    points = ticks.copy()
    points['source_utc'] = points['source_utc'].map(utc)
    points['observed_utc'] = points['observed_utc'].map(utc)
    points = points[points['observed_utc'] <= cut]
    if (points['source_utc'] > points['observed_utc']).any():
        raise ValueError('Future-source tick at receipt')
    points['price'] = pd.to_numeric(points['price'], errors='raise')
    if not np.isfinite(points['price']).all() or (points['price'] <= 0).any():
        raise ValueError('Invalid spot value')
    points = points[points['source_utc'] <= cut]
    if points.empty:
        return base
    # Same-source corrections received later are not available to earlier cuts.
    points = points.sort_values(['source_utc', 'observed_utc'])
    points = points.drop_duplicates('source_utc', keep='last')
    bucket = points['source_utc'].dt.floor('min')
    partial_rows = []
    for opened, group in points.groupby(bucket):
        end = opened + pd.Timedelta(minutes=1)
        # A historical full candle supersedes a sampled partial bucket. Spot
        # ticks are only a fallback for missing buckets or the current bucket.
        if end <= cut and end in base.index:
            continue
        available = max(end, group['observed_utc'].max()) if end <= cut else group['observed_utc'].max()
        prices = group['price']
        partial_rows.append(dict(available_at_utc=available, source_utc=group['source_utc'].max(), Open=float(prices.iloc[0]),
                                 High=float(prices.max()), Low=float(prices.min()),
                                 Close=float(prices.iloc[-1]), Volume=0.))
    if not partial_rows:
        return base
    partial = pd.DataFrame(partial_rows).set_index('available_at_utc')
    # At an exact boundary, the preceding full bucket and the first observed
    # tick may be available simultaneously. Keep the full bar's range/open and
    # use the newest source price. Never overwrite source time with receipt.
    for when in partial.index.intersection(base.index):
        b, p = base.loc[when], partial.loc[when]
        if isinstance(p, pd.DataFrame):
            raise ValueError('Ambiguous partial availability')
        if p['source_utc'] >= b['source_utc']:
            base.loc[when, 'Close'] = p['Close']
            base.loc[when, 'source_utc'] = p['source_utc']
        base.loc[when, 'High'] = max(b['High'], p['High'])
        base.loc[when, 'Low'] = min(b['Low'], p['Low'])
    pieces = [part for part in (base, partial.loc[~partial.index.isin(base.index)]) if not part.empty]
    merged = pd.concat(pieces).sort_index()
    if merged.index.has_duplicates:
        raise ValueError('Ambiguous availability')
    return merged


def price_at_or_before(frame, query):
    """Same existing two-minute support limit, now checked against source time."""
    query = utc(query)
    i = frame.index.searchsorted(query, side='right') - 1
    if i < 0:
        return np.nan, pd.NaT
    row = frame.iloc[i]
    source = utc(row['source_utc'])
    if not pd.Timedelta(0) <= query - source <= pd.Timedelta(minutes=2):
        return np.nan, pd.NaT
    return float(row['Close']), frame.index[i]
