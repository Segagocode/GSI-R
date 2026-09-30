"""Контр-подсказки: OpenDota matchups + видимые враги из GSI.

Сеть только в opendota background; tick только читает кэш и state.
"""

from __future__ import annotations

from typing import Any

import opendota
import settings

ALERT_ID = "counter"


def tick(state: Any) -> None:
    if not settings.OPENDOTA_ENABLED or not state.in_game():
        state.remove(ALERT_ID)
        return

    enemies = state.visible_enemies()
    if not enemies:
        enemies = state.known_enemies()
    if not enemies:
        state.remove(ALERT_ID)
        return

    tip_lines: list[str] = []
    for enemy in enemies[:2]:
        name = str(enemy.get("name") or "")
        if not name:
            continue
        eid = opendota.hero_id_from_gsi_name(name)
        if not eid:
            continue
        loc = opendota.localized_name(name)
        items = enemy.get("items") or []
        counters = opendota.best_counters_for_enemy(eid, limit=2)
        if counters:
            names = ", ".join(c["name"] for c in counters if c.get("name"))
            if names:
                tip_lines.append(f"vs {loc}: {names}")
        elif items:
            short = ", ".join(items[:3])
            tip_lines.append(f"{loc}: {short}")
        if tip_lines:
            break

    if not tip_lines:
        state.remove(ALERT_ID)
        return

    text = tip_lines[0]
    if len(tip_lines) > 1:
        text = tip_lines[0] + "\n" + tip_lines[1]
    state.upsert(ALERT_ID, text, urgent=False)
