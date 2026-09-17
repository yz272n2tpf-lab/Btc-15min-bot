"""Exact BTC15 identifiers. No coercion, whitespace repair, or precedence."""
import re
from collections.abc import Mapping

# BTC15 namespace with a bounded uppercase alphanumeric ticker suffix. This
# includes existing synthetic TEST fixtures as well as exchange date tickers.
TICKER = re.compile(r"KXBTC15M-[A-Z0-9]+(?:-[A-Z0-9]+)*", re.ASCII)
FIELDS = ("contract", "contract_id", "ticker")


def validate_contract(value):
    if not isinstance(value, str) or len(value) > 128 or not TICKER.fullmatch(value):
        raise ValueError("invalid BTC15 contract ID")
    return value


def exact_contract(*objects):
    values = []
    for obj in objects:
        if isinstance(obj, Mapping):
            for key in FIELDS:
                if key in obj:
                    values.append(validate_contract(obj[key]))
    if len(set(values)) > 1:
        raise ValueError("conflicting explicit contract IDs")
    return values[0] if values else None
