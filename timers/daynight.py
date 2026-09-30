"""Таймер дня/ночи.

Основа - map.daytime прямо от GSI (истина в игре). Предупреждения
"за N секунд" считаем по часам: ночь начинается на NIGHT_START,
рассвет на NIGHT_END. Если GSI не прислал daytime - работаем по часам.
"""

from __future__ import annotations

from typing import Any

import settings
from timers._util import ceil_int

ALERT_ID = "daynight"


def _hint(name: str, left: float) -> tuple[str, bool]:
    urgent = left <= settings.URGENT_SECONDS
    tail = "СЕЙЧАС" if urgent else f"через {ceil_int(left)} с"
    return f"{name}\n{tail}", urgent


def _night_block(state: Any, now: float) -> None:
    """Плашка 'Ночь' на NIGHT_LINGER секунд после её начала (общая для обеих веток).

    Считаем от константы NIGHT_START, а не от момента перехода: переход можно
    и пропустить (окно приложения свёрнуто, лаг пакетов), тогда плашка висела бы вечно.
    """
    since = now - settings.NIGHT_START
    if settings.SHOW_WHOLE_NIGHT:
        state.upsert(ALERT_ID, "Ночь\nврага видно", ttl=settings.NIGHT_END - now + 1.0, urgent=True)
    elif 0 <= since < settings.NIGHT_LINGER:
        state.upsert(ALERT_ID, "Ночь\nврага видно",
                     ttl=settings.NIGHT_LINGER - since, urgent=True)
    else:
        state.remove(ALERT_ID)


def _by_clock(state: Any, now: float) -> None:
    """Запасной вариант без map.daytime: чистая арифметика по часам."""
    start, end = settings.NIGHT_START, settings.NIGHT_END
    lead = settings.DAYNIGHT_LEAD_SECONDS
    if start - lead <= now < start:
        left = start - now
        text, urgent = _hint("Ночь", left)
        state.upsert(ALERT_ID, text, urgent=urgent, event_in=left)
    elif start <= now < end:
        _night_block(state, now)
    elif now < end + lead:
        left = max(0.0, end - now)
        text, urgent = _hint("Рассвет", left)
        state.upsert(ALERT_ID, text, urgent=urgent, event_in=left)
    else:
        state.remove(ALERT_ID)


def tick(state: Any) -> None:
    if not state.in_game():
        state.remove(ALERT_ID)
        return

    now = state.clock()
    daytime = state.is_daytime()

    if daytime is None:                      # GSI не дал daytime - считаем по часам
        _by_clock(state, now)
        return

    if daytime is False:                     # сейчас ночь
        _night_block(state, now)
        return

    # сейчас день: предупреждаем по часам перед ночью и перед рассветом
    start, end, lead = settings.NIGHT_START, settings.NIGHT_END, settings.DAYNIGHT_LEAD_SECONDS
    if start - lead <= now < start:
        left = start - now
        text, urgent = _hint("Ночь", left)
        state.upsert(ALERT_ID, text, urgent=urgent, event_in=left)
    elif end - lead <= now < end:
        left = max(0.0, end - now)
        text, urgent = _hint("Рассвет", left)
        state.upsert(ALERT_ID, text, urgent=urgent, event_in=left)
    else:
        state.remove(ALERT_ID)