"""Все настройки приложения в одном месте.

Правило модуля: только константы. Никаких импортов flask/PyQt6/state и
никакой игровой логики. Любой другой модуль читает значения отсюда и всё.
"""

from __future__ import annotations

import os
from pathlib import Path

# ----------------------------------------------------------------- сеть
HOST = "127.0.0.1"
PORT = 31337
GSI_KEY = ""
SERVER_LOG_LEVEL = "warning"

# ----------------------------------------------------------------- пути
GSI_CFG_DIR_NAME = "game/dota/cfg/gamestate_integration"
GSI_CFG_FILE_NAME = "gamestate_integration_overlay.cfg"

DOTA_DIR = os.environ.get("DOTA_DIR", "")
DOTA_DIR_NAMES = ("dota 2 beta", "dota 2")
STEAM_REGISTRY = (
    (r"Software\Valve\Steam", "SteamPath"),
    (r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
)
STEAM_LIBRARIES_FILE = "steamapps/libraryfolders.vdf"

GSI_DATA_KEYS = (
    "provider", "map", "player", "hero", "abilities", "items",
    "allies", "enemies", "units", "projectiles",
)
GSI_CFG_TIMEOUT = "5.0"
GSI_CFG_BUFFER = "0.1"
GSI_CFG_THROTTLE = "0.1"
GSI_CFG_HEARTBEAT = "30.0"
GSI_CFG_URI_WITH_SCHEME = True

# ----------------------------------------------------------------- окно
WINDOW_WIDTH = 380
WINDOW_HEIGHT = 260
WINDOW_MARGIN = 12
WINDOW_Y = None
WINDOW_CENTER_Y = True
WINDOW_ALPHA = 0.92
FONT_FAMILY = "Consolas"
FONT_SIZE = 20
TEXT_COLOR = "#e8e8ea"
URGENT_COLOR = "#ffd24a"
SHADOW_COLOR = "#000000"
BG_COLOR = "#0d0d12"
PANEL_PAD = 10
ACCENT_NORMAL = "#3ddc84"
ACCENT_URGENT = "#ff5a5a"
SHADOW_OFFSET = 1
CLICK_THROUGH = True
HIDE_WHEN_NOT_IN_GAME = True
DEBUG = False

# ----------------------------------------------------------------- подсказки
URGENT_SECONDS = 3.0
ALERT_TTL = 8.0
TICK_INTERVAL = 0.2
MAX_ALERTS = 3
HISTORY_MAX_EVENTS = 64
WINDOW_MERGE_SECONDS = 20.0
WINDOW_LEAD_SECONDS = 15.0

# ----------------------------------------------------------------- руны
RUNE_BOUNTY_FIRST = 0
RUNE_BOUNTY_PERIOD = 120
RUNE_POWER_FIRST = 6 * 60
RUNE_POWER_PERIOD = 120
RUNE_POWER_LAST = 40 * 60
RUNE_ARCANE_FIRST = 30 * 60
RUNE_ARCANE_PERIOD = 240
RUNE_ARCANE_LAST = 58 * 60
RUNE_LEAD_SECONDS = 15.0
RUNE_NAMES = {"bounty": "Баунти", "power": "Пауэр", "arcane": "Аркейн"}

# ----------------------------------------------------------------- день/ночь
NIGHT_START = 5 * 60
NIGHT_END = 10 * 60
DAYNIGHT_LEAD_SECONDS = 15.0
NIGHT_LINGER = 20.0
DAY_LINGER = 5.0
SHOW_WHOLE_NIGHT = True

# ----------------------------------------------------------------- кемпы
CAMP_FIRST = 0
CAMP_PERIOD = 90
CAMP_LEAD_SECONDS = 10.0

# ----------------------------------------------------------------- лотосы / wisdom / терзатель
LOTUS_FIRST = 3 * 60
LOTUS_PERIOD = 3 * 60
LOTUS_LEAD_SECONDS = 15.0
WISDOM_FIRST = 7 * 60
WISDOM_PERIOD = 7 * 60
WISDOM_LEAD_SECONDS = 20.0
TORMENTOR_FIRST = 20 * 60
TORMENTOR_LEAD_SECONDS = 30.0

# ----------------------------------------------------------------- OpenDota
OPENDOTA_ENABLED = True
OPENDOTA_BASE = "https://api.opendota.com/api"
OPENDOTA_TIMEOUT = 8.0
OPENDOTA_CACHE_TTL = 6 * 3600
COUNTER_LEAD_MIN = 0
COUNTER_MIN_MATCHES = 50

# ----------------------------------------------------------------- закуп
TP_ITEM_NAME = "tpscroll"
WARD_ITEM_NAMES = (("observer", "Обсерверы"), ("sentry", "Сентри"))
TELEPORT_ABILITY_NEEDLE = "teleport"
COURIER_ABILITY_NEEDLE = "courier"
SHOPPING_MIN_COOLDOWN = 5.0

# ----------------------------------------------------------------- отладка
LOG_DIR = Path(__file__).resolve().parent / "logs"
DUMP_GSI = True


def cfg_path(dota_dir: Path | str) -> Path:
    return Path(dota_dir) / GSI_CFG_DIR_NAME / GSI_CFG_FILE_NAME
