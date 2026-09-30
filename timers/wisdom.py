"""Таймер wisdom (руна/shrine XP): с WISDOM_FIRST каждые WISDOM_PERIOD."""

from __future__ import annotations

from typing import Any

import settings
from timers._util import in_seconds, next_after

ALERT_ID = "wisdom"


def tick(state: Any) -> None:
    if not state.in_game():
        state.remove(ALERT_ID)
        return
    now = state.clock()
    moment = next_after(settings.WISDOM_FIRST, settings.WISDOM_PERIOD, now)
    if moment is None:
        state.remove(ALERT_ID)
        return
    remaining = moment - now
    if remaining > settings.WISDOM_LEAD_SECONDS:
        state.remove(ALERT_ID)
        return
    urgent = remaining <= settings.URGENT_SECONDS
    tail = "СЕЙЧАС" if urgent else in_seconds(remaining)
    state.upsert(ALERT_ID, f"Wisdom XP\n{tail}", urgent=urgent, event_in=remaining)
