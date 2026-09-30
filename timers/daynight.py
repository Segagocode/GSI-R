"""Таймер дня/ночи.

Основа — map.daytime прямо от GSI (истина в игре).
Предупреждения «за N секунд» и fallback считаем по повторяющемуся циклу:
  день 5 мин → ночь 5 мин, первая ночь на 5:00.
Если GSI не прислал daytime — работаем только по часам.
"""

from __future__ import annotations

from typing import Any

import settings
from timers._util import ceil_int

ALERT_ID = "daynight"

# Полный цикл день+ночь и длительность ночи (стандарт Dota).
_CYCLE = 600.0          # 10 минут
_NIGHT_LEN = 300.0      # 5 минут
_FIRST_NIGHT = 300.0    # 5:00


def _hint(name: str, left: float) -> tuple[str, bool]:
    urgent = left <= settings.URGENT_SECONDS
    tail = "СЕЙЧАС" if urgent else f"через {ceil_int(left)} с"
    return f"{name}\n{tail}", urgent


def _next_night_start(now: float) -> float:
    """Ближайшее начало ночи строго после now (5:00, 15:00, 25:00, …)."""
    if now < _FIRST_NIGHT:
        return _FIRST_NIGHT
    k = int((now - _FIRST_NIGHT) // _CYCLE) + 1
    return _FIRST_NIGHT + k * _CYCLE


def _next_dawn(now: float) -> float:
    """Ближайший рассвет строго после now (10:00, 20:00, 30:00, …)."""
    first_dawn = _FIRST_NIGHT + _NIGHT_LEN  # 10:00
    if now < first_dawn:
        return first_dawn
    k = int((now - first_dawn) // _CYCLE) + 1
    return first_dawn + k * _CYCLE


def _is_night_by_clock(now: float) -> bool:
    if now < _FIRST_NIGHT:
        return False
    return ((now - _FIRST_NIGHT) % _CYCLE) < _NIGHT_LEN


def _show_night(state: Any, ttl: float | None = None) -> None:
    kwargs: dict[str, Any] = {"urgent": True}
    if ttl is not None:
        kwargs["ttl"] = max(0.5, ttl)
    state.upsert(ALERT_ID, "Ночь\nврага видно", **kwargs)


def _show_day_brief(state: Any, since_dawn: float) -> None:
    """Короткая плашка «День» сразу после рассвета."""
    left = settings.DAY_LINGER - since_dawn
    if left <= 0:
        state.remove(ALERT_ID)
        return
    state.upsert(ALERT_ID, "День", ttl=left, urgent=False)


def _night_block_clock(state: Any, now: float) -> None:
    """Плашка «Ночь» по часам (fallback)."""
    if settings.SHOW_WHOLE_NIGHT:
        if _is_night_by_clock(now):
            dawn = _next_dawn(now)
            _show_night(state, ttl=dawn - now + 0.5)
        else:
            state.remove(ALERT_ID)
        return

    if not _is_night_by_clock(now):
        state.remove(ALERT_ID)
        return
    k = int((now - _FIRST_NIGHT) // _CYCLE)
    night_start = _FIRST_NIGHT + k * _CYCLE
    since = now - night_start
    if 0 <= since < settings.NIGHT_LINGER:
        _show_night(state, ttl=settings.NIGHT_LINGER - since)
    else:
        state.remove(ALERT_ID)


def _by_clock(state: Any, now: float) -> None:
    """Запасной вариант без map.daytime: чистая арифметика по циклу."""
    lead = settings.DAYNIGHT_LEAD_SECONDS
    night_at = _next_night_start(now)
    dawn_at = _next_dawn(now)

    if night_at - lead <= now < night_at:
        left = night_at - now
        text, urgent = _hint("Ночь", left)
        state.upsert(ALERT_ID, text, urgent=urgent, event_in=left)
    elif _is_night_by_clock(now):
        _night_block_clock(state, now)
    elif dawn_at - lead <= now < dawn_at:
        left = dawn_at - now
        text, urgent = _hint("Рассвет", left)
        state.upsert(ALERT_ID, text, urgent=urgent, event_in=left)
    else:
        first_dawn = _FIRST_NIGHT + _NIGHT_LEN
        if now >= first_dawn:
            k = int((now - first_dawn) // _CYCLE)
            last_dawn = first_dawn + k * _CYCLE
            since_dawn = now - last_dawn
            if 0 <= since_dawn < settings.DAY_LINGER:
                _show_day_brief(state, since_dawn)
                return
        state.remove(ALERT_ID)


def tick(state: Any) -> None:
    if not state.in_game():
        state.remove(ALERT_ID)
        return

    now = state.clock()
    daytime = state.is_daytime()

    if daytime is None:
        _by_clock(state, now)
        return

    if daytime is False:
        # Главный путь: GSI говорит «ночь» — держим плашку.
        # upsert каждый тик, поэтому живёт всю ночь.
        if settings.SHOW_WHOLE_NIGHT:
            _show_night(state)
        else:
            _show_night(state, ttl=settings.NIGHT_LINGER)
        return

    # день по GSI: предупреждение перед ночью + короткий «День» после рассвета
    lead = settings.DAYNIGHT_LEAD_SECONDS
    night_at = _next_night_start(now)

    if night_at - lead <= now < night_at:
        left = night_at - now
        text, urgent = _hint("Ночь", left)
        state.upsert(ALERT_ID, text, urgent=urgent, event_in=left)
        return

    first_dawn = _FIRST_NIGHT + _NIGHT_LEN
    if now >= first_dawn:
        k = int((now - first_dawn) // _CYCLE)
        last_dawn = first_dawn + k * _CYCLE
        since_dawn = now - last_dawn
        if 0 <= since_dawn < settings.DAY_LINGER:
            _show_day_brief(state, since_dawn)
            return

    state.remove(ALERT_ID)
