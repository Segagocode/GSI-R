"""Таймер терзателя: только первый спавн по часам (TORMENTOR_FIRST)."""

from __future__ import annotations

from typing import Any

import settings
from timers._util import in_seconds

ALERT_ID = "tormentor"


def tick(state: Any) -> None:
    if not state.in_game():
        state.remove(ALERT_ID)
        return
    now = state.clock()
    moment = float(settings.TORMENTOR_FIRST)
    remaining = moment - now
    if remaining < 0 or remaining > settings.TORMENTOR_LEAD_SECONDS:
        state.remove(ALERT_ID)
        return
    urgent = remaining <= settings.URGENT_SECONDS
    tail = "СЕЙЧАС" if urgent else in_seconds(remaining)
    state.upsert(ALERT_ID, f"Терзатель\n{tail}", urgent=urgent, event_in=remaining)
