#!/usr/bin/env python3
"""BTC15 dashboard presentation session V1.

PURE PRESENTATION SESSION | NO NETWORK | NO SIGNAL LOGIC | NO ORDERS

Combines the green mobile View-Model V5 with Dashboard Session Reducer V1.
Maintains two presentation snapshots:
- last accepted display frame (may be source-fail-closed WAIT);
- last healthy same-contract frame (used only to preserve non-actionable wording
  context such as the original acceptable-entry path across a temporary stale
  source).

Safety always wins: a stale/current-unready frame displays WAIT immediately.
The last healthy frame is never shown instead of that WAIT. It is only used as
presentation context when a later healthy frame returns.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

import btc15_mobile_dashboard_view_model_v5 as v5
from btc15_dashboard_session_reducer_v1 import reduce_dashboard_session

VERSION = "BTC15_DASHBOARD_PRESENTATION_SESSION_V1"


def _contract(model: Mapping[str, Any] | None) -> str | None:
    x = str((model or {}).get("contract") or "").strip()
    return x or None


def _scalp(model: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict((((model or {}).get("cards") or {}).get("SCALP_OPPORTUNITY") or {}))


def _is_fail_closed(model: Mapping[str, Any] | None) -> bool:
    card = _scalp(model)
    action = str(card.get("action") or "").upper()
    primary = str(card.get("primary") or "").upper()
    return action.startswith("WAIT ·") or primary.startswith("NO ACTION · SOURCE NOT READY")


@dataclass(frozen=True)
class PresentationSessionState:
    version: str
    processed_frames: int
    accepted_contract: str | None
    last_healthy_contract: str | None
    current_fail_closed: bool
    has_last_healthy_context: bool
    manual_execution_only: bool = True
    orders: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "processed_frames": self.processed_frames,
            "accepted_contract": self.accepted_contract,
            "last_healthy_contract": self.last_healthy_contract,
            "current_fail_closed": self.current_fail_closed,
            "has_last_healthy_context": self.has_last_healthy_context,
            "manual_execution_only": self.manual_execution_only,
            "orders": self.orders,
        }


class DashboardPresentationSession:
    def __init__(self) -> None:
        self._accepted: dict[str, Any] | None = None
        self._last_healthy: dict[str, Any] | None = None
        self._processed = 0

    @property
    def accepted(self) -> dict[str, Any] | None:
        return copy.deepcopy(self._accepted)

    @property
    def last_healthy(self) -> dict[str, Any] | None:
        return copy.deepcopy(self._last_healthy)

    def reset(self) -> None:
        self._accepted = None
        self._last_healthy = None
        self._processed = 0

    def _context_previous(self, incoming_contract: str | None) -> dict[str, Any] | None:
        accepted_contract = _contract(self._accepted)
        healthy_contract = _contract(self._last_healthy)

        # On contract rollover, the immediately previous accepted model must be
        # supplied so V5 can build sanitized prior-contract history.
        if self._accepted and incoming_contract and accepted_contract and incoming_contract != accepted_contract:
            return copy.deepcopy(self._accepted)

        # Same contract: if the displayed accepted frame is fail-closed, use the
        # last healthy context for sticky entry wording and scalp memory only.
        if (
            self._accepted
            and _is_fail_closed(self._accepted)
            and self._last_healthy
            and incoming_contract
            and healthy_contract == incoming_contract
        ):
            return copy.deepcopy(self._last_healthy)

        return copy.deepcopy(self._accepted)

    def process(
        self,
        combined_state: Mapping[str, Any],
        scalp_ui_state: Mapping[str, Any],
    ) -> dict[str, Any]:
        incoming_contract = str(
            (combined_state or {}).get("contract")
            or (scalp_ui_state or {}).get("contract")
            or ""
        ).strip() or None

        context_previous = self._context_previous(incoming_contract)
        candidate = v5.build_mobile_dashboard_view_model(
            combined_state,
            scalp_ui_state,
            previous_model=context_previous,
        )
        accepted = reduce_dashboard_session(self._accepted, candidate)

        self._processed += 1
        self._accepted = copy.deepcopy(accepted)
        if not _is_fail_closed(accepted):
            self._last_healthy = copy.deepcopy(accepted)

        state = PresentationSessionState(
            VERSION,
            self._processed,
            _contract(self._accepted),
            _contract(self._last_healthy),
            _is_fail_closed(self._accepted),
            self._last_healthy is not None,
        )
        self._accepted["presentation_session"] = state.to_dict()
        if self._last_healthy is not None:
            self._last_healthy["presentation_session"] = state.to_dict()

        return copy.deepcopy(self._accepted)


__all__ = [
    "VERSION",
    "PresentationSessionState",
    "DashboardPresentationSession",
]
