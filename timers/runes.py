"""Таймер рун: баунти / пауэр / аркейн.

Пользуется только state.clock() и константами из settings.
"""

from __future__ import annotations

from typing import Any

import settings
from timers._util import in_seconds, next_after

ALERT_ID = "runes"


def _next_runes(now: float) -> tuple[list[str], float] | None:
    """Какие руны появятся следующими и через сколько. Одновременные - склеиваем."""
    candidates: list[tuple[str, float]] = []

    moment = next_after(settings.RUNE_BOUNTY_FIRST, settings.RUNE_BOUNTY_PERIOD, now)
    if moment is not None:
        candidates.append(("bounty", moment))

    moment = next_after(settings.RUNE_POWER_FIRST, settings.RUNE_POWER_PERIOD,
                        now, settings.RUNE_POWER_LAST)
    if moment is not None:
        candidates.append(("power", moment))

    moment = next_after(settings.RUNE_ARCANE_FIRST, settings.RUNE_ARCANE_PERIOD,
                        now, settings.RUNE_ARCANE_LAST)
    if moment is not None:
        candidates.append(("arcane", moment))

    if not candidates:
        return None

    soonest = min(moment for _, moment in candidates)
    kinds = [kind for kind, moment in candidates if abs(moment - soonest) < 1.0]
    return kinds, soonest


def tick(state: Any) -> None:
    if not state.in_game():
        state.remove(ALERT_ID)
        return

    now = state.clock()
    upcoming = _next_runes(now)
    if upcoming is None:
        state.remove(ALERT_ID)
        return

    kinds, moment = upcoming
    remaining = moment - now
    if remaining > settings.RUNE_LEAD_SECONDS:
        state.remove(ALERT_ID)
        return

    names = " / ".join(settings.RUNE_NAMES.get(kind, kind) for kind in kinds)
    urgent = remaining <= settings.URGENT_SECONDS
    tail = "СЕЙЧАС" if urgent else in_seconds(remaining)
    state.upsert(ALERT_ID, f"Руны: {names}\n{tail}", urgent=urgent, event_in=remaining)
