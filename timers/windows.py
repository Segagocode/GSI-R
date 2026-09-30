"""Объединённые окна: руны + кемпы, если спавнятся близко."""

from __future__ import annotations

from typing import Any

import settings
from timers._util import in_seconds, next_after

ALERT_ID = "windows:rune_camp"


def _next_rune_moment(now: float) -> float | None:
    candidates: list[float] = []
    for first, period, last in (
        (settings.RUNE_BOUNTY_FIRST, settings.RUNE_BOUNTY_PERIOD, None),
        (settings.RUNE_POWER_FIRST, settings.RUNE_POWER_PERIOD, settings.RUNE_POWER_LAST),
        (settings.RUNE_ARCANE_FIRST, settings.RUNE_ARCANE_PERIOD, settings.RUNE_ARCANE_LAST),
    ):
        m = next_after(first, period, now, last)
        if m is not None:
            candidates.append(m)
    return min(candidates) if candidates else None


def tick(state: Any) -> None:
    if not state.in_game():
        state.remove(ALERT_ID)
        return
    now = state.clock()
    rune_at = _next_rune_moment(now)
    camp_at = next_after(settings.CAMP_FIRST, settings.CAMP_PERIOD, now)
    if rune_at is None or camp_at is None:
        state.remove(ALERT_ID)
        return
    if abs(rune_at - camp_at) > settings.WINDOW_MERGE_SECONDS:
        state.remove(ALERT_ID)
        return
    moment = min(rune_at, camp_at)
    remaining = moment - now
    if remaining > settings.WINDOW_LEAD_SECONDS:
        state.remove(ALERT_ID)
        return
    tail = "СЕЙЧАС" if remaining <= settings.URGENT_SECONDS else in_seconds(remaining)
    state.upsert(ALERT_ID, f"Руны + кемпы\n{tail}", urgent=True, event_in=remaining)
