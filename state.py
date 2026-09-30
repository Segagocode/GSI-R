"""Хранилище состояния игры и активных подсказок.

Сюда пишет сервер (сырые данные GSI), отсюда читают таймеры и overlay.
Модуль ничего не знает ни про flask, ни про GUI (tkinter/PyQt), ни про таймеры.

Схема GSI проверена на живой игре (проба героя), пример пакета - logs/gsi_last.json:
  map:     game_state, game_time, clock_time, daytime, nightstalker_night, ward_purchase_cooldown
  player:  steamid, name, gold, team_name, kills, deaths, ...
  hero:    name, level, alive, respawn_seconds, health, max_health, ...
  abilities: ability0..N -> {name, level, cooldown, max_cooldown, can_cast, passive}
  items:   slot0..8 / stash0..5 / teleport0 / neutral0.. -> {name, charges, cooldown, ...}
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

import settings

GAME_STATE_IN_PROGRESS = "GAME_IN_PROGRESS"
ITEM_PREFIX = "item_"


@dataclass
class Alert:
    """Одна подсказка на экране."""

    id: str
    text: str                      # может содержать "\n" - overlay рисует как 1-2 строки
    created_at: float              # time.monotonic()
    expires_at: float
    urgent: bool = False
    event_in: float | None = None  # секунд до события; None = отсчёт не рисуем

    def remaining(self, now: float) -> float:
        """Сколько подсказка ещё живёт без обновления (страховка от залипания)."""
        return max(0.0, self.expires_at - now)


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


class GameState:
    def __init__(self) -> None:
        self._lock = threading.RLock()

        self._payload: dict[str, Any] = {}
        self._has_payload = False
        self._last_packet_at = 0.0
        self._player_id = ""

        self._game_state = ""
        self._in_progress = False                 # матчи GO прямо сейчас (по последнему пакету с map)
        self._clock_anchor: float | None = None   # time.monotonic(), когда было 0:00
        self._clock_tick_at = 0.0                 # monotonic до какого момента якорь уже прокручен
        self._time_source = "local"
        self._paused_now = False                  # paused в последнем пакете с map
        self._pause_started_at = 0.0              # monotonic, когда началась текущая пауза

        self._alerts: dict[str, Alert] = {}

    # ------------------------------------------------------------ приём
    def update(self, payload: dict[str, Any]) -> None:
        """Вызывается сервером на каждый POST от Dota (их ~10 в секунду)."""
        with self._lock:
            now = time.monotonic()
            self._payload = payload if isinstance(payload, dict) else {}
            self._has_payload = True
            self._last_packet_at = now

            game_map = self._payload.get("map") or {}
            # heartbeat-пакеты Dota приходит раз в 30 с БЕЗ секции map -
            # состояние матча из них неизвестно, сохраняем прошлое.
            if not game_map:
                return

            game_state = str(game_map.get("game_state") or "")
            paused_now = bool(game_map.get("paused"))
            in_progress = GAME_STATE_IN_PROGRESS in game_state

            # Смена фазы матча: на входе GAME_IN_PROGRESS обнуляем local-часы,
            # чтобы prep-время разной длительности (Turbo/AllPick) не въедалось
            # в тайминги рун/кемпов. GSI-часы трогать не нужно - там prep это
            # отрицательный game_time, а нулевой якорь ставит сама игра на gtime=0.
            entered_game = (GAME_STATE_IN_PROGRESS in game_state
                            and GAME_STATE_IN_PROGRESS not in self._game_state)

            # Пауза: game_time замирает, monotonic идёт. За время паузы часы
            # не прокручиваем (clock() это учитывает); при снятии паузы якорь
            # сдвигаем на длительность паузы - продолжение без прыжка и без отката.
            if paused_now and not self._paused_now:
                self._pause_started_at = now
                if self._clock_anchor is not None:
                    self._clock_tick_at = now        # заморозить часы с этого момента
            elif not paused_now and self._paused_now and self._clock_anchor is not None:
                self._clock_anchor += now - self._pause_started_at
                self._clock_tick_at = now
            self._paused_now = paused_now

            gtime = game_map.get("game_time", game_map.get("clock_time"))
            gtime = float(gtime) if isinstance(gtime, (int, float)) and not isinstance(gtime, bool) else None

            if entered_game and gtime is None:
                self._clock_anchor = now
                self._clock_tick_at = now
                self._time_source = "local"

            if gtime is not None and gtime >= 0:
                # Время присылает сама игра (на паузе не идёт) - доверяем ему
                # полностью: anchor ставим ОТ game_time, никаких поправок на паузы.
                # (Раньше вычитали ещё и текущую паузу дважды - часы текли назад.)
                self._clock_anchor = now - gtime
                self._clock_tick_at = now
                self._time_source = "gsi"

            self._in_progress = in_progress
            self._game_state = game_state
            player = self._payload.get("player") or {}
            for key in ("steamid", "id"):
                value = player.get(key)
                if isinstance(value, str) and value:
                    self._player_id = value
                    break

    # ------------------------------------------------------------ время и фаза
    def clock(self) -> float:
        """Секунды от начала игры. На паузе стоит (игра тоже её не считает).

        НЕ мутирует состояние: local-часы = now - anchor; gsi-часы = game_time
        из последнего пакета + время с тех пор (на паузе при stops). Якорь при
        снятии паузы сдвигает update(), поэтому скачков нет.
        """
        with self._lock:
            if not self._has_payload or self._clock_anchor is None:
                return 0.0
            now = time.monotonic()
            if self._time_source == "local":
                running = self._in_progress and not self._paused_now
                if not running:
                    return max(0.0, self._clock_tick_at - self._clock_anchor)
                return max(0.0, now - self._clock_anchor)
            # gsi-часы: game_time приходит с задержкой ~throttle; monotonic между
            # пакетами идёт вместе с игрой, поэтому добавляем дельту от пакета.
            # На паузе game_time замирал - прибавлять нечего.
            if self._paused_now:
                return max(0.0, self._clock_tick_at - self._clock_anchor)
            return max(0.0, now - self._clock_anchor)

    def clock_source(self) -> str:
        with self._lock:
            return self._time_source

    def game_state(self) -> str:
        """Сырое значение map.game_state, например DOTA_GAMERULES_STATE_GAME_IN_PROGRESS."""
        with self._lock:
            return self._game_state

    def in_game(self) -> bool:
        """Идёт ли матч (в пробе героя тоже GAME_IN_PROGRESS)."""
        return GAME_STATE_IN_PROGRESS in self.game_state()

    def paused(self) -> bool:
        with self._lock:
            return bool((self._payload.get("map") or {}).get("paused"))

    def is_daytime(self) -> bool | None:
        """map.daytime прямо от игры. None = игра не прислала (старая версия)."""
        with self._lock:
            value = (self._payload.get("map") or {}).get("daytime")
            return value if isinstance(value, bool) else None

    def ward_purchase_cooldown(self) -> float:
        """Сколько секунд ещё нельзя/не восстановились варды в магазине."""
        with self._lock:
            return _number((self._payload.get("map") or {}).get("ward_purchase_cooldown"))

    def player_id(self) -> str:
        with self._lock:
            return self._player_id

    def last_packet_age(self) -> float:
        """Сколько секунд назад был последний пакет. -1 = пакетов не было."""
        with self._lock:
            if not self._has_payload:
                return -1.0
            return time.monotonic() - self._last_packet_at

    # ------------------------------------------------------------ герой
    def hero(self) -> dict[str, Any]:
        """Сводка по своему герою (только то, что GSI отдаёт про игрока)."""
        with self._lock:
            hero = self._payload.get("hero") or {}
            player = self._payload.get("player") or {}
            return {
                "name": hero.get("name") or "",
                "level": hero.get("level") or 0,
                "alive": hero.get("alive"),
                "respawn": _number(hero.get("respawn_seconds")),
                "health": hero.get("health"),
                "max_health": hero.get("max_health"),
                "gold": player.get("gold"),
                "team": player.get("team_name") or "",
                "name_player": player.get("name") or "",
            }

    # ------------------------------------------------------------ предметы
    def items(self) -> dict[str, dict[str, Any]]:
        """Сводка по предметам. Ключ - короткое имя без префикса item_.

        {"tpscroll": {"charges": 1, "cooldown": 36.0, "slots": ["teleport0"], ...}}
        """
        with self._lock:
            source = self._payload.get("items")
            merged: dict[str, dict[str, Any]] = {}
            if not isinstance(source, dict):
                return merged

            for slot, entry in source.items():
                if not isinstance(entry, dict):
                    continue
                raw_name = str(entry.get("name") or "")
                if not raw_name or raw_name == "empty":
                    continue
                name = raw_name[len(ITEM_PREFIX):] if raw_name.startswith(ITEM_PREFIX) else raw_name
                name = name.lower()

                info = merged.setdefault(name, {
                    "name": name,
                    "slots": [],
                    "charges": 0,
                    "cooldown": 0.0,
                    "max_cooldown": 0.0,
                    "can_cast": True,
                    "in_stash": False,
                })
                info["slots"].append(slot)
                info["charges"] += int(_number(entry.get("charges", entry.get("item_charges"))))
                info["cooldown"] = max(info["cooldown"], _number(entry.get("cooldown")))
                info["max_cooldown"] = max(info["max_cooldown"], _number(entry.get("max_cooldown")))
                info["in_stash"] = info["in_stash"] or str(slot).startswith("stash")
                if not entry.get("can_cast", True):
                    info["can_cast"] = False
            return merged

    def item(self, name: str) -> dict[str, Any] | None:
        return self.items().get(name)

    # ------------------------------------------------------------ способности
    def abilities(self) -> list[dict[str, Any]]:
        """Все способности героя списком: name, level, cooldown, can_cast."""
        with self._lock:
            source = self._payload.get("abilities") or {}
            result: list[dict[str, Any]] = []
            if not isinstance(source, dict):
                return result
            for key in sorted(source, key=lambda k: str(k)):
                entry = source[key]
                if not isinstance(entry, dict):
                    continue
                result.append({
                    "slot": key,
                    "name": str(entry.get("name") or ""),
                    "level": entry.get("level", 0),
                    "cooldown": _number(entry.get("cooldown")),
                    "max_cooldown": _number(entry.get("max_cooldown")),
                    "can_cast": bool(entry.get("can_cast")),
                    "passive": bool(entry.get("passive")),
                    "learned": bool(entry.get("level")),
                })
            return result

    def cooldown_by_name(self, needle: str) -> float:
        """Максимальный кулдаун среди способностей, в имени которых есть needle.

        Нужно для курьера и ТП-способности героев: индексы у героев разные,
        а имя способности - всегда одинаковое.
        """
        needle = needle.lower()
        best = 0.0
        for ability in self.abilities():
            if needle in ability["name"].lower():
                best = max(best, ability["cooldown"])
        return best

    def payload(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._payload)

    # ------------------------------------------------------------ подсказки
    def upsert(self, alert_id: str, text: str, ttl: float | None = None,
                urgent: bool = False, event_in: float | None = None) -> None:
        """Создать или обновить подсказку. Таймеры зовут это каждый тик.

        event_in - секунды до события: overlay рисует их у правого края карточки.
                   None = событие не впереди (например «Ночь / врага видно»), отсчёта нет.
        ttl      - сколько подсказка живёт без обновления, страховка от залипания.
                   На экран не выводится, поэтому не путать с event_in.
        """
        now = time.monotonic()
        life = settings.ALERT_TTL if ttl is None else ttl
        with self._lock:
            self._alerts[alert_id] = Alert(alert_id, text, now, now + life, urgent,
                                           None if event_in is None else max(0.0, event_in))

    def remove(self, alert_id: str) -> None:
        with self._lock:
            self._alerts.pop(alert_id, None)

    def clear_alerts(self) -> None:
        with self._lock:
            self._alerts.clear()

    def active_alerts(self) -> list[dict[str, Any]]:
        """Что overlay должен нарисовать прямо сейчас. Тухлые удаляются тут же."""
        now = time.monotonic()
        with self._lock:
            alive: list[dict[str, Any]] = []
            for alert_id, alert in list(self._alerts.items()):
                left = alert.remaining(now)
                if left <= 0:
                    del self._alerts[alert_id]
                    continue
                alive.append({
                    "id": alert.id,
                    "text": alert.text,
                    "urgent": alert.urgent,
                    "event_in": alert.event_in,   # None = отсчёт у правого края не рисуем
                    "ttl_left": left,             # остаток жизни подсказки, для затухания
                })
        # срочные сверху, внутри группы - ближайшие события
        alive.sort(key=lambda a: (0 if a["urgent"] else 1,
                                  a["event_in"] if a["event_in"] is not None else float("inf")))
        return alive[: settings.MAX_ALERTS]