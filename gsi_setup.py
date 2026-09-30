"""Поиск папки Dota 2 (через Steam) и создание/обновление cfg-файла для GSI.

Модуль не запускает сервер и ничего не знает про таймеры.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import settings

LOGGER = logging.getLogger("dota.gsi")


# ------------------------------------------------------------------ поиск Dota
def _steam_roots_from_registry() -> list[Path]:
    try:
        import winreg
    except ImportError:
        return []

    roots: list[Path] = []
    for hive_name, (sub_key, value_name) in (
        ("HKEY_CURRENT_USER", settings.STEAM_REGISTRY[0]),
        ("HKEY_LOCAL_MACHINE", settings.STEAM_REGISTRY[1]),
    ):
        hive = getattr(winreg, hive_name)
        try:
            with winreg.OpenKey(hive, sub_key) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
        except OSError:
            continue
        if value:
            roots.append(Path(value))
    return roots


def _steam_libraries(steam_root: Path) -> list[Path]:
    vdf = steam_root / settings.STEAM_LIBRARIES_FILE
    if not vdf.is_file():
        return [steam_root / "steamapps"]
    try:
        text = vdf.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [steam_root / "steamapps"]
    found = re.findall(r'"path"\s*"([^"]+)"', text)
    return [Path(item) / "steamapps" for item in found] or [steam_root / "steamapps"]


def find_dota_dir() -> Path | None:
    """Вернуть папку Dota 2 или None. Порядок: настройка -> реестр -> типовые пути."""
    candidates: list[Path] = []

    if settings.DOTA_DIR:
        candidates.append(Path(settings.DOTA_DIR))

    for steam_root in _steam_roots_from_registry():
        candidates.extend(_steam_libraries(steam_root))

    for steam_root in (Path("C:/Program Files (x86)/Steam"),
                       Path("C:/Program Files/Steam")):
        candidates.extend(_steam_libraries(steam_root))

    for library in candidates:
        for name in settings.DOTA_DIR_NAMES:
            game = library / "common" / name
            if game.is_dir():
                return game

    LOGGER.error("папку Dota 2 не нашёл. Укажи её в settings.DOTA_DIR или в переменной DOTA_DIR")
    return None


# ------------------------------------------------------------------ cfg-файл
def build_cfg_text(steam_id: str = "") -> str:
    host_part = f"{settings.HOST}:{settings.PORT}"
    uri = f"http://{host_part}" if settings.GSI_CFG_URI_WITH_SCHEME else host_part
    if settings.GSI_KEY:
        uri = f"{uri}/?key={settings.GSI_KEY}"

    lines = [
        "// auto-generated for dota-overlay (main.py). safe to edit.",
        '"dota 2"',
        "{",
        f'\t"uri"\t\t"{uri}"',
        f'\t"timeout"\t"{settings.GSI_CFG_TIMEOUT}"',
        f'\t"buffer"\t"{settings.GSI_CFG_BUFFER}"',
        f'\t"throttle"\t"{settings.GSI_CFG_THROTTLE}"',
        f'\t"heartbeat"\t"{settings.GSI_CFG_HEARTBEAT}"',
        '\t"data"',
        "\t{",
    ]
    for key in settings.GSI_DATA_KEYS:
        lines.append(f'\t\t"{key}"\t\t"1"')
    if steam_id:
        lines.append(f'\t\t"provider.steamid"\t"{steam_id}"')
    lines += ["\t}", "}", ""]
    return "\n".join(lines)


def read_steamid(path: Path) -> str:
    try:
        match = re.search(r'"provider\.steamid"\s*"([^"]+)"', path.read_text(encoding="utf-8"))
    except OSError:
        return ""
    return match.group(1) if match else ""


def ensure_config(dota_dir: Path | str | None = None,
                  force: bool = False) -> Path | None:
    """Создать/обновить cfg. Вернуть путь к файлу или None, если Dota не найдена."""
    game_dir = Path(dota_dir) if dota_dir else find_dota_dir()
    if game_dir is None:
        return None

    target = settings.cfg_path(game_dir)
    target.parent.mkdir(parents=True, exist_ok=True)

    wanted = build_cfg_text(read_steamid(target))
    try:
        current = target.read_text(encoding="utf-8")
    except OSError:
        current = None

    if force or current != wanted:
        if current is not None:
            backup = target.with_suffix(".cfg.bak")
            backup.write_text(current, encoding="utf-8")
        target.write_text(wanted, encoding="utf-8")
        LOGGER.info("cfg записан: %s", target)
    else:
        LOGGER.info("cfg уже актуален: %s", target)
    return target


def update_steamid(steam_id: str) -> bool:
    """Дописать provider.steamid, когда Gota его сообщила. Необязательно."""
    if not steam_id:
        return False
    game_dir = find_dota_dir()
    if game_dir is None:
        return False

    target = settings.cfg_path(game_dir)
    if not target.is_file():
        return ensure_config(game_dir) is not None

    if read_steamid(target) == steam_id:
        return True

    text = target.read_text(encoding="utf-8")
    if re.search(r'"provider\.steamid"', text):
        text = re.sub(r'("provider\.steamid"\s*)"[^"]*"',
                      rf'\g<1>"{steam_id}"', text)
    else:
        text = re.sub(r'(\n(\t\t"provider"\s+"1"\n))',
                      rf'\g<1>\t\t"provider.steamid"\t"{steam_id}"\n',
                      text, count=1)
    target.write_text(text, encoding="utf-8")
    LOGGER.info("в cfg добавлен provider.steamid=%s", steam_id)
    return True