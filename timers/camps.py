"""Таймер стока нейтральных кемпов.

Спавн идёт по часам от начала игры: 0:00, 1:30, 3:00, ...
"""

from __future__ import annotations

from typing import Any

import settings
from timers._util import in_seconds, next_after

ALERT_ID = "camps"


def tick(state: Any) -> None:
    if not state.in_game():
        state.remove(ALERT_ID)
        return

    now = state.clock()
    moment = next_after(settings.CAMP_FIRST, settings.CAMP_PERIOD, now)
    if moment is None:
        state.remove(ALERT_ID)
        return

    remaining = moment - now
    if remaining > settings.CAMP_LEAD_SECONDS:
        state.remove(ALERT_ID)
        return

    urgent = remaining <= settings.URGENT_SECONDS
    state.upsert(ALERT_ID, f"Кемпы\n{'СПАВН' if urgent else in_seconds(remaining)}",
                 urgent=urgent)