"""Мелкие общие помощники для таймеров. Не таймер (имя начинается с "_")."""

from __future__ import annotations

import math


def ceil_int(value: float) -> int:
    """Округление вверх: 0.2 -> 1, 3.0 -> 3."""
    return max(0, int(math.ceil(value)))


def next_after(first: float, period: float, now: float,
               last: float | None = None) -> float | None:
    """Ближайшее время события строго после now в ряду first, first+period, ...

    None, если ряд кончился (moment > last). Событие, которое now уже перевалил,
    больше не возвращается - иначе плашка "СЕЙЧАС" висела бы на минуты после спавна.
    """
    if now < first:
        return first
    steps = math.floor((now - first) / period) + 1
    moment = first + steps * period
    if last is not None and moment > last:
        return None
    return moment


def in_seconds(value: float) -> str:
    return f"через {ceil_int(value)} с"