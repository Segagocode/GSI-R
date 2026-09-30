"""Объединённые окна: руны + кемпы, если спавнятся близко.

Первый простой «предикт»/эвристика на базе тех же таймингов, что runes/camps:
если следующее событие рун и сток кемпов разнесены меньше чем WINDOW_MERGE_SECONDS,
показываем одну срочную плашку вместо двух разрозненных напоминаний.
"""

from __future__ import annotations

from typing import Any

import settings
from timers._util import in_seconds, next_after

ALERT_ID = "windows:rune_camp"


def _next_rune_moment(now: float) -> float | None:
    candidates: list[float] = []
    m = next_after(settings.RUNE_BOUNTY_FIRST, settings.RUNE_BOUNTY_PERIOD, now)
    if m is not None:
        candidates.append(m)
    m = next_after(settings.RUNE_POWER_FIRST, settings.RUNE_POWER_PERIOD, now,
                   settings.RUNE_POWER_LAST)
    if m is not None:
        candidates.append(m)
    m = next_after(settings.RUNE_ARCANE_FIRST, settings.RUNE_ARCANE_PERIOD, now,
                   settings.RUNE_ARCANE_LAST)
    if m is not None:
        candidates.append(m)
    return min(candidates) if candidates else None


def _next_camp_moment(now: float) -> float | None:
    return next_after(settings.CAMP_FIRST, settings.CAMP_PERIOD, now)


def tick(state: Any) -> None:
    if not state.in_game():
        state.remove(ALERT_ID)
        return

    now = state.clock()
    rune_at = _next_rune_moment(now)
    camp_at = _next_camp_moment(now)
    if rune_at is None or camp_at is None:
        state.remove(ALERT_ID)
        return

    gap = abs(rune_at - camp_at)
    if gap > settings.WINDOW_MERGE_SECONDS:
        state.remove(ALERT_ID)
        return

    moment = min(rune_at, camp_at)
    remaining = moment - now
    if remaining > settings.WINDOW_LEAD_SECONDS:
        state.remove(ALERT_ID)
        return

    urgent = remaining <= settings.URGENT_SECONDS
    tail = "СЕЙЧАС" if urgent else in_seconds(remaining)
    # Одна плашка вместо двух — выше ценность в слоте MAX_ALERTS=2
    state.upsert(
        ALERT_ID,
        f"Руны + кемпы\n{tail}",
        urgent=True,  # склеенное окно всегда приоритетное
        event_in=remaining,
    )
