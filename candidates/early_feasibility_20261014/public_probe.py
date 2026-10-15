"""One-shot, GET-only EARLY evidence feasibility check. NO RECORDER.

Checks the EXISTING public MAIN decision view and native-journal coverage
endpoint. It does not collect, poll, submit orders, restart a service, request
market credentials, modify source strategy or alter stored evidence.

These APIs do not expose original historical decision event bodies; a passing
probe establishes interface/denominator availability, NOT EARLY performance.
A separately authorized read-only snapshot of the native SQLite journal is
required for any honest BUY / later BID / official result linking.
"""
import json
import sys
import urllib.error
import urllib.request

ORIGIN = "https://btc-15min-bot-production.up.railway.app"
PATHS = ("/ladders/coverage", "/ladders", "/ladders/quotes")
MAX_BYTES = 262144


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("REDIRECT_REJECTED")


def get_json(path):
    if path not in PATHS:
        raise ValueError("PATH_NOT_ALLOWED")
    req = urllib.request.Request(
        ORIGIN + path,
        headers={"Accept": "application/json", "User-Agent": "BTC15-early-readonly-feasibility"},
        method="GET")
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=7) as response:
        if response.status != 200:
            raise ValueError("HTTP_STATUS_NOT_200")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("RESPONSE_TOO_LARGE")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("NOT_JSON_OBJECT")
    return value


def evaluate(coverage, view):
    """Pure, deterministic, no JSON source payload is included in the receipt."""
    for label, data in (("coverage", coverage), ("view", view)):
        if not isinstance(data, dict):
            raise ValueError(label + "_NOT_OBJECT")
        if data.get("signal_only") is not True or data.get("orders") is not False:
            raise ValueError(label + "_SIGNAL_ONLY_IDENTITY")
    rows = coverage.get("contracts")
    if not isinstance(rows, list) or len(rows) > 96:
        raise ValueError("COVERAGE_SHAPE_OR_LIMIT")
    counts = dict(contracts=len(rows), with_observations=0,
                  missing_or_partial=0, unavailable_frames=0,
                  official_results=0, pending_results=0, buys_reported=0)
    defects = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("opened"), int):
            defects.append("BAD_CONTRACT_ROW")
            continue
        observed = row.get("observations")
        if type(observed) is not int or observed < 0:
            defects.append("BAD_OBSERVATION_COUNT")
            continue
        counts["with_observations"] += (observed > 0)
        counts["missing_or_partial"] += (row.get("missing") == 1)
        counts["unavailable_frames"] += row.get("unavailable") if type(row.get("unavailable")) is int else 0
        counts["buys_reported"] += row.get("signals") if type(row.get("signals")) is int else 0
        status = row.get("settlement_status")
        if status == "AUTHORITATIVE":
            receipt = row.get("settlement")
            if (isinstance(receipt, dict) and receipt.get("status") == "AUTHORITATIVE"
                    and receipt.get("ticker") == row.get("ticker")
                    and receipt.get("open_ts") == row["opened"]
                    and receipt.get("side") in ("UP", "DOWN")):
                counts["official_results"] += 1
            else:
                defects.append("UNLINKED_OFFICIAL_SETTLEMENT")
        else:
            counts["pending_results"] += 1
    active = view.get("status") == "AVAILABLE"
    fields = dict(
        early= isinstance(view.get("early"), dict),
        market_prices=isinstance(view.get("prices"), dict),
        final=isinstance(view.get("final"), dict),
        native_clock=(view.get("native_sequence") is not None and view.get("feature_cutoff") is not None),
        immutable_origin=isinstance(view.get("origin"), dict),
        early_management=isinstance(view.get("management"), dict))
    if active:
        prices = view.get("prices") or {}
        fields["bid_ask_paired"] = (
            all(type(prices.get(k)) in (float, int)
                for k in ("up_bid", "up_ask", "down_bid", "down_ask"))
            and 0 <= prices["up_bid"] <= prices["up_ask"] <= 1
            and 0 <= prices["down_bid"] <= prices["down_ask"] <= 1)
    else:
        fields["bid_ask_paired"] = False
    access = len(rows) > 0 and counts["with_observations"] > 0 and not defects
    return dict(
        schema="BTC15_EARLY_EXISTING_JOURNAL_FEASIBILITY_V1",
        read_only=True, no_orders=True, requests=2,
        source="LIVE_PUBLIC_JOURNAL_COVERAGE_AND_CURRENT_VIEW",
        coverage=counts, latest_view=dict(
            status=view.get("status"), reason=view.get("reason") if not active else None,
            fields=fields),
        defects=sorted(set(defects)),
        access_confirmed=access,
        native_event_bodies_exported=False,
        chronological_buy_exit_quote_join_verified=False,
        official_result_join_in_native_event_verified=False,
        ready_to_grade_early=False,
        status=("EXISTING_JOURNAL_ACCESSIBLE_NEEDS_RAW_RECEIPTS"
                if access else "NOT_YET_PROVEN"),
        next_gate=("READ_ONLY_NATIVE_MAIN_SQLITE_SNAPSHOT_AND_EXACT_RECEIPT_VALIDATION"
                   if access else "STOP_AND_REPORT_WHICH_LIVE_PUBLIC_INTERFACE_FAILED"))


def main():
    try:
        c = get_json("/ladders/coverage")
        v = get_json("/ladders")
        receipt = evaluate(c, v)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0 if receipt["access_confirmed"] else 2
    except (OSError, ValueError, KeyError, TypeError, urllib.error.HTTPError) as e:
        print(json.dumps(dict(
            schema="BTC15_EARLY_EXISTING_JOURNAL_FEASIBILITY_V1",
            status="STOP_READ_ONLY_INTERFACE_NOT_CONFIRMED",
            error=type(e).__name__,
            detail=str(e)[:160],
            ready_to_grade_early=False, no_orders=True,
            no_production_changes=True), sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
