"""Мелкие общие помощники для таймеров. Не таймер (имя начинается с "_")."""

from __future__ import annotations

import math


def ceil_int(value: float) -> int:
    """Округление вверх: 0.2 -> 1, 3.0 -> 3."""
    return max(0, int(math.ceil(value)))


def next_after(first: float, period: float, now: float,
               last: float | None = None) -> float | None:
    """Ближайшее время события строго после now в ряду first, first+period, ..."""
    if now < first:
        return first
    steps = math.floor((now - first) / period) + 1
    moment = first + steps * period
    if last is not None and moment > last:
        return None
    return moment


def current_or_next(first: float, period: float, now: float,
                    last: float | None = None) -> float | None:
    """Ближайшее время события в ряду first, first+period, ...

    От next_after отличается тем, что ПРОПУЩЕННЫЙ момент (now уже прошёл его)
    ещё считается актуальным - таймер покажет "СЕЙЧАС", если now не ушёл дальше
    lead-окна. Так не сгорает событие 0:00 (баунти-руны, первый сток кемпов),
    когда приложение стартовало через полсекунды после начала матча.
    """
    if now <= first:
        return first
    steps = math.floor((now - first) / period)
    passed = first + steps * period          # последний прошедший момент ряда
    upcoming = passed + period               # следующий за ним
    if last is not None and upcoming > last:
        return passed if passed <= last else None   # следующий уже за пределами ряда
    return upcoming


def in_seconds(value: float) -> str:
    return f"через {ceil_int(value)} с"