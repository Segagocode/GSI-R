"""Таймер лотосов: появление каждые LOTUS_PERIOD с LOTUS_FIRST."""

from __future__ import annotations

from typing import Any

import settings
from timers._util import in_seconds, next_after

ALERT_ID = "lotus"


def tick(state: Any) -> None:
    if not state.in_game():
        state.remove(ALERT_ID)
        return
    now = state.clock()
    moment = next_after(settings.LOTUS_FIRST, settings.LOTUS_PERIOD, now)
    if moment is None:
        state.remove(ALERT_ID)
        return
    remaining = moment - now
    if remaining > settings.LOTUS_LEAD_SECONDS:
        state.remove(ALERT_ID)
        return
    urgent = remaining <= settings.URGENT_SECONDS
    tail = "СЕЙЧАС" if urgent else in_seconds(remaining)
    state.upsert(ALERT_ID, f"Лотосы\n{tail}", urgent=urgent, event_in=remaining)
