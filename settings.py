"""Все настройки приложения в одном месте.

Правило модуля: только константы. Никаких импортов flask/tkinter/state и
никакой игровой логики. Любой другой модуль читает значения отсюда и всё.
"""

from __future__ import annotations

import os
from pathlib import Path

# ----------------------------------------------------------------- сеть
HOST = "127.0.0.1"
PORT = 31337                      # сюда пишется uri в cfg, тут же слушает сервер
GSI_KEY = ""                     # необязательный секрет. Пусто = не проверять
SERVER_LOG_LEVEL = "warning"

# ----------------------------------------------------------------- пути
GSI_CFG_DIR_NAME = "game/dota/cfg/gamestate_integration"
GSI_CFG_FILE_NAME = "gamestate_integration_overlay.cfg"

DOTA_DIR = os.environ.get("DOTA_DIR", "")   # можно задать руками, чтобы не искать Steam
DOTA_DIR_NAMES = ("dota 2 beta", "dota 2")
STEAM_REGISTRY = (
    (r"Software\Valve\Steam", "SteamPath"),
    (r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
)
STEAM_LIBRARIES_FILE = "steamapps/libraryfolders.vdf"

# что подписываем в cfg ("1" = хочу эти данные)
GSI_DATA_KEYS = (
    "provider",
    "map",
    "player",
    "hero",
    "abilities",
    "items",
    "allies",
    "enemies",
    "units",
    "projectiles",
)
GSI_CFG_TIMEOUT = "5.0"
GSI_CFG_BUFFER = "0.1"
GSI_CFG_THROTTLE = "0.1"
GSI_CFG_HEARTBEAT = "30.0"
# Если Dota не примет "http://" в uri, поставь False и будет голое "127.0.0.1:31337"
GSI_CFG_URI_WITH_SCHEME = True

# ----------------------------------------------------------------- окно
# Правый край: доводим WINDOW_RIGHT_EDGE до ширины монитора (или ставим руками).
WINDOW_WIDTH = 360
WINDOW_HEIGHT = 150
WINDOW_RIGHT_EDGE = 1920          # правый край экрана; X = RIGHT_EDGE - WIDTH - MARGIN
WINDOW_MARGIN = 12                # отступ от правого края и сверху
WINDOW_Y = 60                     # верх окна по вертикали
WINDOW_ALPHA = 0.92
FONT_FAMILY = "Consolas"          # терминальный шрифт, есть в Windows из коробки
FONT_SIZE = 20                    # компактный, читаемый размер
TEXT_COLOR = "#e8e8ea"
URGENT_COLOR = "#ffd24a"
SHADOW_COLOR = "#000000"          # тень под текстом = контраст
BG_COLOR = "#0d0d12"              # фон плашки (окно полупрозрачное, см. WINDOW_ALPHA)
PANEL_PAD = 10                    # внутренние поля плашки
ACCENT_NORMAL = "#3ddc84"         # левая полоска обычной подсказки
ACCENT_URGENT = "#ff5a5a"         # левая полоска срочной подсказки
BLOCK_GAP = 1.35                  # во сколько "выше шрифта" смещать блоки друг от друга
SHADOW_OFFSET = 1
CLICK_THROUGH = True              # клики проходят в игру (WS_EX_TRANSPARENT)
HIDE_WHEN_NOT_IN_GAME = True     # прятать окно, когда нет подсказок
DEBUG = False                     # всегда показывать часы и сырые цифры GSI

# ----------------------------------------------------------------- подсказки
LEAD_SECONDS = 12.0               # за сколько секунд предупреждать (рабочий диапазон 10-15)
URGENT_SECONDS = 3.0              # с этого момента писать "СЕЙЧАС"
ALERT_TTL = 8.0                   # сколько секунд живёт подсказка после показа
TICK_INTERVAL = 0.2               # как часто опрашивать таймеры (секунды)
MAX_ALERTS = 2                    # максимум строк-блоков одновременно

# ----------------------------------------------------------------- руны
RUNE_BOUNTY_FIRST = 0
RUNE_BOUNTY_PERIOD = 120
RUNE_POWER_FIRST = 6 * 60
RUNE_POWER_PERIOD = 120
RUNE_POWER_LAST = 40 * 60         # после 40:00 пауэр-руны не появляются
RUNE_ARCANE_FIRST = 30 * 60
RUNE_ARCANE_PERIOD = 240
RUNE_ARCANE_LAST = 58 * 60        # ВНИМАНИЕ: проверь на своей версии, можно поставить 3600
RUNE_LEAD_SECONDS = 15.0
RUNE_NAMES = {
    "bounty": "Баунти",
    "power": "Пауэр",
    "arcane": "Аркейн",
}

# ----------------------------------------------------------------- день/ночь
NIGHT_START = 5 * 60              # ночь начинается на 5:00
NIGHT_END = 10 * 60               # рассвет на 10:00
DAYNIGHT_LEAD_SECONDS = 15.0
NIGHT_LINGER = 6.0                 # сколько секунд висит плашка "Ночь" после её начала
SHOW_WHOLE_NIGHT = False           # True = держать плашку "Ночь" всю ночь до рассвета

# ----------------------------------------------------------------- кемпы
CAMP_FIRST = 0
CAMP_PERIOD = 90                  # спавн нейтралов каждые 1:30 от начала игры
CAMP_LEAD_SECONDS = 10.0

# ----------------------------------------------------------------- закуп
# Имена предметов в GSI приходят с префиксом "item_" (item_tpscroll -> tpscroll)
TP_ITEM_NAME = "tpscroll"
WARD_ITEM_NAMES = (("observer", "Обсерверы"), ("sentry", "Сентри"))
# Способности ищем по имени, а не по индексу: у героев набор разный
TELEPORT_ABILITY_NEEDLE = "teleport"
COURIER_ABILITY_NEEDLE = "courier"
SHOPPING_MIN_COOLDOWN = 5.0   # не показывать кулдаун меньше N секунд

# ----------------------------------------------------------------- отладка
LOG_DIR = Path(__file__).resolve().parent / "logs"
DUMP_GSI = True                   # писать последний пакет GSI в logs/gsi_last.json


def cfg_path(dota_dir: Path | str) -> Path:
    """Полный путь к нашему cfg-файлу внутри папки Dota."""
    return Path(dota_dir) / GSI_CFG_DIR_NAME / GSI_CFG_FILE_NAME