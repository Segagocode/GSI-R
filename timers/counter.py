"""Контр-подсказки: OpenDota matchups + враги из GSI payload.

Сеть только в opendota background; tick только читает кэш и state.
"""

from __future__ import annotations

from typing import Any

import opendota
import settings

ALERT_ID = "counter"

# кэш последних увиденных врагов на время матча (модульный, сбрасывается редко)
_known: dict[str, dict] = {}


def _parse_enemies(payload: dict) -> list[dict]:
    raw = payload.get("enemies")
    result: list[dict] = []
    if not isinstance(raw, dict):
        return result
    for _key, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        hero = entry.get("hero") if isinstance(entry.get("hero"), dict) else entry
        name = str((hero or {}).get("name") or entry.get("name") or "")
        if not name or name == "null":
            continue
        items_src = entry.get("items") if isinstance(entry.get("items"), dict) else {}
        item_names: list[str] = []
        for _slot, it in (items_src or {}).items():
            if not isinstance(it, dict):
                continue
            iname = str(it.get("name") or "")
            if iname and iname != "empty":
                if iname.startswith("item_"):
                    iname = iname[5:]
                item_names.append(iname)
        info = {"name": name, "items": item_names}
        result.append(info)
        _known[name] = info
    return result


def tick(state: Any) -> None:
    if not settings.OPENDOTA_ENABLED or not state.in_game():
        state.remove(ALERT_ID)
        return

    enemies = _parse_enemies(state.payload())
    if not enemies:
        enemies = list(_known.values())
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
            tip_lines.append(f"{loc}: {", ".join(items[:3])}")
        if tip_lines:
            break

    if not tip_lines:
        state.remove(ALERT_ID)
        return

    text = tip_lines[0] if len(tip_lines) == 1 else tip_lines[0] + "\n" + tip_lines[1]
    state.upsert(ALERT_ID, text, urgent=False)
