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

_prev_daytime: bool | None = None     # прошлый тик - чтобы поймать сам момент смены


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
        text, urgent = _hint("Ночь", start - now)
        state.upsert(ALERT_ID, text, urgent=urgent)
    elif start <= now < end:
        _night_block(state, now)
    elif now < end + lead:
        text, urgent = _hint("Рассвет", max(0.0, end - now))
        state.upsert(ALERT_ID, text, urgent=urgent)
    else:
        state.remove(ALERT_ID)


def tick(state: Any) -> None:
    global _prev_daytime

    if not state.in_game():
        _prev_daytime = None
        state.remove(ALERT_ID)
        return

    now = state.clock()
    daytime = state.is_daytime()

    if daytime is None:                      # GSI не дал daytime - считаем по часам
        _prev_daytime = None
        _by_clock(state, now)
        return

    _prev_daytime = daytime                  # переходы больше не нужны - плашка считается от NIGHT_START

    if daytime is False:                     # сейчас ночь
        _night_block(state, now)
        return

    # сейчас день: предупреждаем по часам перед ночью и перед рассветом
    start, end, lead = settings.NIGHT_START, settings.NIGHT_END, settings.DAYNIGHT_LEAD_SECONDS
    if start - lead <= now < start:
        text, urgent = _hint("Ночь", start - now)
        state.upsert(ALERT_ID, text, urgent=urgent)
    elif end - lead <= now < end:
        text, urgent = _hint("Рассвет", max(0.0, end - now))
        state.upsert(ALERT_ID, text, urgent=urgent)
    else:
        state.remove(ALERT_ID)