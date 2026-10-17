"""Capture schema for the pinned completed_candles producer, without relabeling.

The owner sets BOTH native clocks to bucket end. Bucket start is read from the
original raw frame and is additional evidence, never a replacement source time.
"""
import math

SCHEMA = 'NATIVE_COMPLETED_END_WITH_ORIGINAL_BUCKET_V2'
PRODUCER_SHA256 = 'f4ff1bbaf1da21a025c5f1e073c651ae430756b6074d26d4481ac9ba98541f2a'
OHLCV = ('Open', 'High', 'Low', 'Close', 'Volume')


def acceptance_rows(completed, original):
    from .policy import need
    need(len(completed) == len(original) <= 60000, 'COMPLETED_ORIGINAL_ROW_COUNT')
    need(not completed.index.has_duplicates and not original.index.has_duplicates,
         'COMPLETED_DUPLICATE_INDEX')
    # Positional pairing is only accepted after exact clock/value verification.
    # No inferred timestamps, nearest rows, mutation or sorting of native inputs.
    for (end, row), (start, raw) in zip(completed.iterrows(), original.iterrows()):
        values = [end.timestamp(), row['source_utc'].timestamp(), start.timestamp(),
                  *[float(row[k]) for k in OHLCV]]
        native, upstream = decode(values)
        need(upstream[1:] == [float(raw[k]) for k in OHLCV], 'COMPLETED_ORIGINAL_OHLCV')
        yield values


def decode(row):
    from .policy import need
    need(isinstance(row, list) and len(row) == 8 and
         all(type(x) in (int, float) and math.isfinite(x) for x in row),
         'COMPLETED_V2_SCHEMA')
    end, source, start, op, hi, lo, cl, vol = row
    need(end == source == start + 60 and start % 60 == 0,
         'COMPLETED_V2_ORIGINAL_END_CLOCK')
    need(min(op, hi, lo, cl) > 0 and vol >= 0 and
         hi >= max(op, lo, cl) and lo <= min(op, hi, cl), 'COMPLETED_V2_OHLCV')
    return [end, source, op, hi, lo, cl, vol], [start, op, hi, lo, cl, vol]
