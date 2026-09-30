"""Таймер закупа: телепорт, курьер, варды.

Всё берём из GSI: предметы (items.slot*/teleport0/stash*) и способности.
Свиток ТП прямо в GSI отдаёт cooldown и charges, способность ТП у части героев
ищем по имени. Курьера - по слову "courier" в имени способности.
"""

from __future__ import annotations

from typing import Any

import settings
from timers._util import ceil_int

TP_ALERT_ID = "shopping:tp"
COURIER_ALERT_ID = "shopping:courier"
WARD_ALERT_ID = "shopping:wards"


def _tick_tp(state: Any, items: dict[str, dict[str, Any]]) -> None:
    scroll = items.get(settings.TP_ITEM_NAME)
    if scroll is not None:
        if scroll["charges"] <= 0:
            state.upsert(TP_ALERT_ID, "Свиток ТП кончился\nкупи новый", urgent=True)
        elif scroll["cooldown"] > settings.SHOPPING_MIN_COOLDOWN:
            state.upsert(TP_ALERT_ID, f"Свиток ТП на откате\n{ceil_int(scroll['cooldown'])} с")
        else:
            state.remove(TP_ALERT_ID)
        return

    # свитка нет - значит ТП у героя как способность (Ио, Чен, Венге, Пугна...)
    cooldown = state.cooldown_by_name(settings.TELEPORT_ABILITY_NEEDLE)
    if cooldown > settings.SHOPPING_MIN_COOLDOWN:
        state.upsert(TP_ALERT_ID, f"ТП на кулдауне\n{ceil_int(cooldown)} с")
    else:
        state.remove(TP_ALERT_ID)


def _tick_courier(state: Any) -> None:
    cooldown = state.cooldown_by_name(settings.COURIER_ABILITY_NEEDLE)
    if cooldown > settings.SHOPPING_MIN_COOLDOWN:
        state.upsert(COURIER_ALERT_ID, f"Курьер на кулдауне\n{ceil_int(cooldown)} с")
    else:
        state.remove(COURIER_ALERT_ID)


def _tick_wards(state: Any, items: dict[str, dict[str, Any]]) -> None:
    """Напоминаем только если варды уже есть в инвентаре, но кончились."""
    empty = [label for name, label in settings.WARD_ITEM_NAMES
             if name in items and items[name]["charges"] <= 0]
    if not empty:
        state.remove(WARD_ALERT_ID)
        return

    text = f"Варды кончились\n{', '.join(empty)}"
    restock = state.ward_purchase_cooldown()
    if restock > settings.URGENT_SECONDS:
        text = f"Варды кончились\nмагазин через {ceil_int(restock)} с"
    state.upsert(WARD_ALERT_ID, text, urgent=True)


def tick(state: Any) -> None:
    if not state.in_game():
        for alert_id in (TP_ALERT_ID, COURIER_ALERT_ID, WARD_ALERT_ID):
            state.remove(alert_id)
        return

    items = state.items()
    _tick_tp(state, items)
    _tick_courier(state)
    _tick_wards(state, items)