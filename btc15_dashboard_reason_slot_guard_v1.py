#!/usr/bin/env python3
"""BTC15 dashboard reason-slot guard V1.

PURE PRESENTATION | NO SIGNAL LOGIC | NO ORDERS

Normalizes dynamic explanation text into a stable short slot while preserving
the complete normalized text for an optional detail view. This prevents reason
copy from changing the main card geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

VERSION = "BTC15_DASHBOARD_REASON_SLOT_GUARD_V1"
DEFAULT_MAX_CHARS = 88


@dataclass(frozen=True)
class ReasonSlot:
    visible_text: str
    detail_text: str
    truncated: bool
    max_lines: int = 2
    fixed_slot: bool = True


def normalize_reason(text: object) -> str:
    raw = "" if text is None else str(text)
    return re.sub(r"\s+", " ", raw).strip()


def _truncate_word_boundary(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars < 2:
        return "…"[:max_chars]
    body_limit = max_chars - 1
    cut = text[:body_limit].rstrip()
    space = cut.rfind(" ")
    if space >= max(12, body_limit // 2):
        cut = cut[:space].rstrip()
    return cut + "…"


def reason_slot(text: object, *, max_chars: int = DEFAULT_MAX_CHARS) -> ReasonSlot:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    detail = normalize_reason(text)
    if not detail:
        detail = "Waiting for validated evidence."
    visible = _truncate_word_boundary(detail, max_chars)
    return ReasonSlot(
        visible_text=visible,
        detail_text=detail,
        truncated=visible != detail,
    )


__all__ = ["ReasonSlot", "reason_slot", "normalize_reason", "VERSION"]
