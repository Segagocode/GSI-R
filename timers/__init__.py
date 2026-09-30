"""Реестр таймеров.

Новый таймер = новый файл в этой папке с функцией `tick(state)`.
Ни __init__.py, ни другие таймеры править не нужно: файлы находятся
автоматически, каждый таймер работает в своём try/except.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from types import ModuleType
from typing import Any

LOGGER = logging.getLogger("dota.timers")

_MODULES: list[ModuleType] | None = None


def _discover() -> list[ModuleType]:
    found: list[ModuleType] = []
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda i: i.name):
        if info.name.startswith("_"):        # _util и прочее служебное
            continue
        try:
            module = importlib.import_module(f"{__name__}.{info.name}")
        except Exception:                    # noqa: BLE001 - сломанный таймер не должен ронять всё
            LOGGER.exception("таймер %s не импортировался", info.name)
            continue
        if not callable(getattr(module, "tick", None)):
            LOGGER.warning("в таймере %s нет функции tick(state)", info.name)
            continue
        found.append(module)
    return found


def modules() -> list[ModuleType]:
    global _MODULES
    if _MODULES is None:
        _MODULES = _discover()
        LOGGER.info("таймеры: %s", ", ".join(m.__name__.rsplit(".", 1)[-1] for m in _MODULES))
    return _MODULES


def tick_all(state: Any) -> None:
    for module in modules():
        try:
            module.tick(state)
        except Exception:                    # noqa: BLE001
            LOGGER.exception("таймер %s упал", module.__name__)