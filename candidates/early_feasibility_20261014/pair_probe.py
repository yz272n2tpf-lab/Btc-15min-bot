"""One-shot qualification of independent *future* EARLY quote evidence.

Three pairs of GET-only reads over at most 5 seconds. This is not an order,
backtest, collector, daemon, live deployment, or evidence of profitability.
Only data present in exact original replies are considered. No resampling,
timestamp rounding, fabricated paths, private keys, or filesystem writes.
"""
import json
import time
from .public_probe import get_json


def validate_pair(decision, quote):
    """Validate a later observation of the SAME current native contract."""
    if not isinstance(decision, dict) or not isinstance(quote, dict):
        return dict(valid=False, reason="NOT_OBJECT")
    if any(v.get("signal_only") is not True or v.get("orders") is not False
           for v in (decision, quote)):
        return dict(valid=False, reason="SIGNAL_ONLY_IDENTITY")
    if decision.get("status") != "AVAILABLE" or quote.get("status") != "AVAILABLE":
        return dict(valid=False, reason="SOURCE_UNAVAILABLE")
    ident = quote.get("official_identity") or {}
    ticker = decision.get("contract")
    if not isinstance(ticker, str) or ticker != ident.get("contract"):
        return dict(valid=False, reason="CONTRACT_MISMATCH")
    if quote.get("schema") != "BTC15_EXECUTABLE_QUOTE_R1" or quote.get("authority") != "PRICE_PRESENTATION_ONLY":
        return dict(valid=False, reason="QUOTE_PROJECTION_IDENTITY")
    values=(decision.get("prices"), quote)
    for item in values:
        if not isinstance(item, dict):
            return dict(valid=False, reason="MISSING_PRICE_PROJECTION")
        prices=[item.get(k) for k in ("up_bid","up_ask","down_bid","down_ask")]
        if any(type(x) not in (float, int) for x in prices):
            return dict(valid=False, reason="INVALID_PRICES")
        if not (0<=prices[0]<=prices[1]<=1 and 0<=prices[2]<=prices[3]<=1):
            return dict(valid=False, reason="CROSSED_OR_INVALID_BOOK")
    qclk=[quote.get(k) for k in ("exchange_ts","accepted_ts","published_ts","served_ts","expires_at")]
    if any(type(x) not in (float, int) for x in qclk):
        return dict(valid=False, reason="QUOTE_CLOCK_MISSING")
    source,accept,published,served,expires=qclk
    if not (ident.get("official_open",0)<=source<=accept<=published<=served<expires<=ident.get("official_close",0)
            and expires<=source+6):
        return dict(valid=False, reason="QUOTE_CLOCK_INVALID")
    if not isinstance(decision.get("early"),dict) or not isinstance(decision.get("final"),dict):
        return dict(valid=False, reason="EARLY_DECISION_MISSING")
    if type(decision.get("native_sequence")) is not int or type(decision.get("published_ts")) not in (float,int):
        return dict(valid=False, reason="NATIVE_DECISION_CLOCK_MISSING")
    dp=decision["published_ts"]
    # Quote projection is explicitly for price presentation, not proved fill depth.
    # Its source/accepted times are native, not local GET timestamps.
    return dict(valid=True, native_decision_sequence=decision["native_sequence"],
                same_contract=True, fresh_quote=True,
                later_quote_source=source>dp,
                later_quote_accepted=accept>dp,
                continuity_unproven=True, manual_fill_unproven=True)


def main():
    observations=[]
    errors=[]
    for i in range(3):
        if i:
            time.sleep(2)
        try:
            view=get_json("/ladders")
            quote=get_json("/ladders/quotes")
            observations.append(validate_pair(view,quote))
        except Exception as exc:
            errors.append(type(exc).__name__)
    matched=sum(bool(x.get("valid")) for x in observations)
    newer=sum(bool(x.get("valid") and x.get("later_quote_source") and x.get("later_quote_accepted"))
              for x in observations)
    result=dict(schema="BTC15_PROSPECTIVE_EARLY_OBSERVER_FEASIBILITY_V1",
                reads_attempted=6,interval_seconds=2,requests_per_sample=2,
                matched_pairs=matched,later_quote_pairs=newer,
                failure_reasons=[x.get("reason") for x in observations if not x.get("valid")],
                transport_errors=errors, sample_values_not_persisted=True,
                quote_source="EXISTING_SAME_PROVIDER_PUBLIC_PROJECTION",
                early_source="EXISTING_NATIVE_MAIN_CURRENT_VIEW",
                native_source_and_receipt_clocks_retained=True,
                complete_market_path=False, fills_proven=False,
                strategy_untouched=True, signal_only=True, orders=False,
                ready_for_bounded_external_observation=matched>=1 and newer>=1,
                authorized_for_24h=False, authorized_for_strategy_changes=False,
                stop_if_failed="NO_MATCHED_POSTDECISION_SOURCE_RECEIPTS")
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result["ready_for_bounded_external_observation"] else 2


if __name__=="__main__":
    raise SystemExit(main())
