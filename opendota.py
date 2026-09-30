"""Фоновый кэш OpenDota: публичные матчапы героев (не в tick таймеров)."""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import settings

LOGGER = logging.getLogger("dota.opendota")
_lock = threading.RLock()
_heroes_by_name: dict[str, dict[str, Any]] = {}
_matchups: dict[int, list[dict[str, Any]]] = {}
_fetched_at: dict[int, float] = {}
_started = False
_CACHE_DIR = Path(__file__).resolve().parent / "logs" / "opendota_cache"


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "GSI-R-overlay/1.0"})
    with urllib.request.urlopen(req, timeout=settings.OPENDOTA_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ensure_heroes() -> None:
    global _heroes_by_name
    with _lock:
        if _heroes_by_name:
            return
    try:
        data = _get_json(f"{settings.OPENDOTA_BASE}/heroes")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        LOGGER.warning("OpenDota heroes: %s", exc)
        return
    mapping: dict[str, dict[str, Any]] = {}
    if isinstance(data, list):
        for h in data:
            if not isinstance(h, dict):
                continue
            name = str(h.get("name") or "")
            if name:
                mapping[name] = h
    with _lock:
        _heroes_by_name = mapping
    LOGGER.info("OpenDota: загружено героев %s", len(mapping))


def hero_id_from_gsi_name(gsi_name: str) -> int | None:
    if not gsi_name:
        return None
    _ensure_heroes()
    with _lock:
        h = _heroes_by_name.get(gsi_name)
        if h and "id" in h:
            return int(h["id"])
    return None


def localized_name(gsi_name: str) -> str:
    _ensure_heroes()
    with _lock:
        h = _heroes_by_name.get(gsi_name) or {}
    return str(h.get("localized_name") or gsi_name.replace("npc_dota_hero_", ""))


def prefetch_matchups(hero_id: int) -> None:
    if not settings.OPENDOTA_ENABLED or hero_id <= 0:
        return
    now = time.monotonic()
    with _lock:
        if hero_id in _matchups and now - _fetched_at.get(hero_id, 0) < settings.OPENDOTA_CACHE_TTL:
            return
    try:
        data = _get_json(f"{settings.OPENDOTA_BASE}/heroes/{hero_id}/matchups")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        LOGGER.warning("OpenDota matchups %s: %s", hero_id, exp if False else exc)
        return
    if not isinstance(data, list):
        return
    with _lock:
        _matchups[hero_id] = data
        _fetched_at[hero_id] = now


def best_counters_for_enemy(enemy_hero_id: int, limit: int = 3) -> list[dict[str, Any]]:
    prefetch_matchups(enemy_hero_id)
    with _lock:
        rows = list(_matchups.get(enemy_hero_id) or [])
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        games = int(row.get("games_played") or 0)
        wins = int(row.get("wins") or 0)
        if games < settings.COUNTER_MIN_MATCHES:
            continue
        scored.append((wins / games, row))
    scored.sort(key=lambda x: x[0])
    result = []
    for wr, row in scored[:limit]:
        hid = int(row.get("hero_id") or 0)
        name = ""
        with _lock:
            for meta in _heroes_by_name.values():
                if int(meta.get("id") or -1) == hid:
                    name = str(meta.get("localized_name") or "")
                    break
        result.append({"hero_id": hid, "name": name or str(hid),
                       "enemy_winrate": round(wr * 100, 1),
                       "games": int(row.get("games_played") or 0)})
    return result


def start_background(game_state: Any) -> None:
    global _started
    if not settings.OPENDOTA_ENABLED or _started:
        return
    _started = True

    def loop() -> None:
        _ensure_heroes()
        while True:
            try:
                if game_state.in_game():
                    me = game_state.hero().get("name") or ""
                    mid = hero_id_from_gsi_name(me)
                    if mid:
                        prefetch_matchups(mid)
                    # враги из сырого payload (без новых методов state)
                    enemies = game_state.payload().get("enemies")
                    if isinstance(enemies, dict):
                        for entry in enemies.values():
                            if not isinstance(entry, dict):
                                continue
                            hero = entry.get("hero") if isinstance(entry.get("hero"), dict) else entry
                            name = str((hero or {}).get("name") or entry.get("name") or "")
                            eid = hero_id_from_gsi_name(name)
                            if eid:
                                prefetch_matchups(eid)
            except Exception:
                LOGGER.exception("OpenDota background")
            time.sleep(15.0)

    threading.Thread(target=loop, name="opendota", daemon=True).start()
    LOGGER.info("OpenDota: фоновый кэш запущен")
