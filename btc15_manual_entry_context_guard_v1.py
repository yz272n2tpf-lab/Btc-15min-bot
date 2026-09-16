#!/usr/bin/env python3
"""BTC15 manual-entry context continuity guard V1.

PURE PRESENTATION | NO SIGNAL LOGIC | NO ORDERS

The app cannot know whether the user actually placed a manual trade. This guard
therefore tracks only whether a same-contract/same-opportunity path was presented
as an acceptable manual-entry path versus TRACKING ONLY.

Sticky rules for one scalp opportunity:
- acceptable entry path never falls back to TRACKING ONLY because of a later
  missing/transient entry-price field;
- TRACKING ONLY never retroactively becomes a manual-entry path because a later
  price changes;
- contract or opportunity change resets the context from the new opportunity.

This affects wording only. Underlying lifecycle state is never changed.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from typing import Any, Mapping

VERSION = "BTC15_MANUAL_ENTRY_CONTEXT_GUARD_V1"

NONE = "NONE"
ACCEPTABLE = "ACCEPTABLE_ENTRY_PATH"
TRACKING = "TRACKING_ONLY_NO_POSITION"
UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ManualEntryContext:
    version: str
    state: str
    contract: str | None
    opportunity_index: int | None
    sticky: bool
    origin_tier: str | None
    origin_entry_price_text: str | None
    source: str
    manual_position_confirmed: bool = False
    signal_filtering: bool = False
    signal_suppression: bool = False
    orders: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _contract(model: Mapping[str, Any] | None) -> str | None:
    x = str((model or {}).get("contract") or "").strip()
    return x or None


def _scalp(model: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict((((model or {}).get("cards") or {}).get("SCALP_OPPORTUNITY") or {}))


def _int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def _entry_price_text(card: Mapping[str, Any]) -> str | None:
    for row in card.get("rows") or []:
        if str(row.get("label") or "") == "Entry Price":
            value = str(row.get("value") or "").strip()
            return value if value and value != "—" else None
    return None


def _tier_from_card(card: Mapping[str, Any]) -> str | None:
    if card.get("manual_entry_path_available") is True:
        # The view-model intentionally exposes only acceptable/not acceptable,
        # not the original tier, so preserve a stable acceptable label.
        return "ACCEPTABLE_LE50"
    if card.get("tracking_only") is True:
        text = (str(card.get("action") or "") + " " + str(card.get("primary") or "")).upper()
        return "ABOVE_50_OR_NONENTRY" if "DON'T CHASE" in text or "NO ENTRY" in text else "NONENTRY"
    return None


def _infer_current(model: Mapping[str, Any]) -> ManualEntryContext:
    contract = _contract(model)
    card = _scalp(model)
    lifecycle = str(card.get("underlying_lifecycle_state") or "PASS").upper()
    opp = _int(card.get("opportunity_index"))
    tier = _tier_from_card(card)
    price = _entry_price_text(card)

    if opp is None or lifecycle == "PASS":
        return ManualEntryContext(VERSION, NONE, contract, opp, False, tier, price, "CURRENT_NO_ACTIVE_OPPORTUNITY")
    if card.get("manual_entry_path_available") is True:
        return ManualEntryContext(VERSION, ACCEPTABLE, contract, opp, True, tier, price, "CURRENT_ACCEPTABLE_ENTRY")
    if card.get("tracking_only") is True or lifecycle in {"ACTIVE", "PROTECT", "EXIT"}:
        return ManualEntryContext(VERSION, TRACKING, contract, opp, True, tier, price, "CURRENT_NONENTRY_PATH")
    return ManualEntryContext(VERSION, UNKNOWN, contract, opp, False, tier, price, "CURRENT_UNKNOWN")


def _previous_context(previous_model: Mapping[str, Any] | None) -> ManualEntryContext | None:
    if not previous_model:
        return None
    raw = (previous_model or {}).get("manual_entry_context")
    if isinstance(raw, Mapping):
        state = str(raw.get("state") or UNKNOWN)
        if state in {NONE, ACCEPTABLE, TRACKING, UNKNOWN}:
            return ManualEntryContext(
                VERSION,
                state,
                str(raw.get("contract") or "").strip() or _contract(previous_model),
                _int(raw.get("opportunity_index")),
                raw.get("sticky") is True,
                str(raw.get("origin_tier") or "").strip() or None,
                str(raw.get("origin_entry_price_text") or "").strip() or None,
                "PREVIOUS_EXPLICIT_CONTEXT",
            )
    inferred = _infer_current(previous_model)
    return ManualEntryContext(
        VERSION,
        inferred.state,
        inferred.contract,
        inferred.opportunity_index,
        inferred.sticky,
        inferred.origin_tier,
        inferred.origin_entry_price_text,
        "PREVIOUS_INFERRED_CONTEXT",
    )


def resolve_manual_entry_context(
    previous_model: Mapping[str, Any] | None,
    current_model: Mapping[str, Any],
) -> ManualEntryContext:
    current = _infer_current(current_model)
    if current.state == NONE:
        return current

    previous = _previous_context(previous_model)
    same_key = bool(
        previous
        and previous.contract
        and current.contract
        and previous.contract == current.contract
        and previous.opportunity_index is not None
        and previous.opportunity_index == current.opportunity_index
    )
    if not same_key or previous is None:
        return current

    if previous.state == TRACKING:
        return ManualEntryContext(
            VERSION,
            TRACKING,
            current.contract,
            current.opportunity_index,
            True,
            previous.origin_tier or current.origin_tier,
            previous.origin_entry_price_text or current.origin_entry_price_text,
            "STICKY_TRACKING_CONTEXT",
        )
    if previous.state == ACCEPTABLE:
        return ManualEntryContext(
            VERSION,
            ACCEPTABLE,
            current.contract,
            current.opportunity_index,
            True,
            previous.origin_tier or current.origin_tier,
            previous.origin_entry_price_text or current.origin_entry_price_text,
            "STICKY_ACCEPTABLE_CONTEXT",
        )
    return current


def _set_row(rows: list[dict[str, Any]], label: str, value: str) -> list[dict[str, Any]]:
    out = [dict(r) for r in rows]
    for row in out:
        if str(row.get("label") or "") == label:
            row["value"] = value
            return out
    return out


def apply_manual_entry_context_to_scalp_card(
    card: Mapping[str, Any],
    context: ManualEntryContext,
) -> dict[str, Any]:
    out = copy.deepcopy(dict(card or {}))
    lifecycle = str(out.get("underlying_lifecycle_state") or "PASS").upper()
    opp = _int(out.get("opportunity_index"))
    side_action = str(out.get("action") or "")
    side = None
    for candidate in ("UP", "DOWN"):
        if side_action.upper().startswith(candidate + " ") or side_action.upper().startswith(candidate + "#"):
            side = candidate
            break

    if lifecycle not in {"ACTIVE", "PROTECT", "EXIT"} or opp is None:
        out["manual_entry_context_applied"] = False
        return out

    if context.state == TRACKING:
        out["tracking_only"] = True
        out["manual_entry_path_available"] = False
        out["action"] = f"{side or 'SCALP'} #{opp} · TRACKING ONLY"
        out["primary"] = (
            "MOVE VALID · NO ENTRY · DON'T CHASE"
            if context.origin_tier == "ABOVE_50_OR_NONENTRY"
            else "TRACKING ONLY · NO POSITION ASSUMED"
        )
        out["tone"] = "caution"
        out["rows"] = _set_row(out.get("rows") or [], "Profit Protection", "MODEL TRACKING ONLY · NO POSITION ASSUMED")
    elif context.state == ACCEPTABLE:
        out["tracking_only"] = False
        out["manual_entry_path_available"] = True
        if context.origin_entry_price_text:
            out["rows"] = _set_row(out.get("rows") or [], "Entry Price", context.origin_entry_price_text)
        if lifecycle == "ACTIVE":
            out["action"] = f"{side or 'SCALP'} #{opp} · ENTRY AVAILABLE"
            out["primary"] = "HOLD · MOVE STILL BUILDING"
            out["tone"] = "positive"
            out["rows"] = _set_row(out.get("rows") or [], "Profit Protection", "PROTECTION NOT ARMED")
        elif lifecycle == "PROTECT":
            out["action"] = "PROTECT PROFITS"
            out["primary"] = "MOVE REACHED PROTECTION LEVEL"
            out["tone"] = "protect"
            out["rows"] = _set_row(out.get("rows") or [], "Profit Protection", "WATCH FOR GIVEBACK")
        else:
            out["action"] = "EXIT NOW · PROTECT PROFITS"
            out["primary"] = "VALIDATED GIVEBACK EXIT"
            out["tone"] = "exit"
            out["rows"] = _set_row(out.get("rows") or [], "Profit Protection", "PROTECTED EXIT")

    out["manual_entry_context_applied"] = context.state in {ACCEPTABLE, TRACKING}
    out["manual_entry_context_state"] = context.state
    out["manual_position_confirmed"] = False
    return out


__all__ = [
    "VERSION",
    "NONE",
    "ACCEPTABLE",
    "TRACKING",
    "UNKNOWN",
    "ManualEntryContext",
    "resolve_manual_entry_context",
    "apply_manual_entry_context_to_scalp_card",
]
