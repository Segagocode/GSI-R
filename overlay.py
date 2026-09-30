"""Окно подсказок: рамки нет, поверх всех, полупрозрачное, клики проходят в игру.

Модуль только рисует. Он берёт готовый список подсказок из state и не знает,
откуда они взялись и что за таймер их создал.
"""

from __future__ import annotations

import ctypes
import logging
import time
import tkinter as tk
from typing import Any, Callable

import settings

LOGGER = logging.getLogger("dota.overlay")

# Win32: делаем окно некликабельным, поверх всего и не активируем его
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010

_STARTED = time.monotonic()


def _long_ptr_funcs(user32: Any) -> tuple[Any, Any]:
    """На 64-битной Windows нужен Get/SetWindowLongPtrW, иначе стиль обрежется."""
    if hasattr(user32, "SetWindowLongPtrW"):
        get_long, set_long = user32.GetWindowLongPtrW, user32.SetWindowLongPtrW
        long_ptr = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
    else:  # 32-бит
        get_long, set_long = user32.GetWindowLongW, user32.SetWindowLongW
        long_ptr = ctypes.c_long
    get_long.argtypes = (ctypes.c_void_p, ctypes.c_int)
    get_long.restype = long_ptr
    set_long.argtypes = (ctypes.c_void_p, ctypes.c_int, long_ptr)
    set_long.restype = long_ptr
    return get_long, set_long


def hwnd_of(root: tk.Tk) -> int:
    """Настоящий HWND окна (у Tk это дочернее окно внутри обёртки)."""
    user32 = ctypes.windll.user32
    return user32.GetParent(root.winfo_id()) or root.winfo_id()


def make_click_through(root: tk.Tk) -> None:
    """WS_EX_TRANSPARENT: клики проходят сквозь окно в игру."""
    if not settings.CLICK_THROUGH:
        return
    try:
        user32 = ctypes.windll.user32
        hwnd = hwnd_of(root)
        get_long, set_long = _long_ptr_funcs(user32)
        style = get_long(hwnd, GWL_EXSTYLE)
        set_long(hwnd, GWL_EXSTYLE,
                 style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    except OSError:
        LOGGER.exception("не удалось сделать окно click-through")


def _make_window() -> tk.Tk:
    root = tk.Tk()
    root.title("dota overlay")
    root.overrideredirect(True)                       # окно без рамки
    root.attributes("-topmost", True)
    root.attributes("-alpha", settings.WINDOW_ALPHA)  # полупрозрачно
    root.configure(bg=settings.BG_COLOR)
    root.resizable(False, False)
    root.geometry(f"{settings.WINDOW_WIDTH}x{settings.WINDOW_HEIGHT}"
                  f"+{settings.WINDOW_X}+{settings.WINDOW_Y}")
    root.update_idletasks()
    make_click_through(root)
    return root


def _debug_lines(game_state: Any) -> str:
    hero = game_state.hero()
    daytime = game_state.is_daytime()
    return (f"clock {int(game_state.clock() // 60)}:{int(game_state.clock() % 60):02d}"
            f"  {game_state.clock_source()}"
            f"  день={daytime if daytime is not None else '?'}"
            f"  герой={hero['name']} lv{hero['level']}"
            f"  золото={hero['gold']}"
            f"  пакет={game_state.last_packet_age():.1f}с назад")


def _draw(cv: tk.Canvas, alerts: list[dict[str, Any]], debug_text: str) -> None:
    cv.delete("all")
    font = (settings.FONT_FAMILY, settings.FONT_SIZE, "bold")
    line_h = settings.FONT_SIZE * 1.3
    gap = settings.FONT_SIZE * 0.35

    if debug_text:
        cv.create_text(8, 8, anchor="nw", text=debug_text,
                       font=(settings.FONT_FAMILY, max(10, settings.FONT_SIZE // 3)),
                       fill="#7fd4ff", justify="left")

    heights = [line_h * (alert["text"].count("\n") + 1) for alert in alerts]
    total = sum(heights) + gap * max(0, len(alerts) - 1)
    y = (settings.WINDOW_HEIGHT - total) / 2
    center_x = settings.WINDOW_WIDTH / 2

    for alert, height in zip(alerts, heights):
        color = settings.URGENT_COLOR if alert["urgent"] else settings.TEXT_COLOR
        dim = "gray50" if alert["remaining"] <= 1.0 else None  # гаснет перед исчезновением
        center_y = y + height / 2
        text = alert["text"]
        # тень под текстом = читаемость на любом фоне игры
        cv.create_text(center_x + settings.SHADOW_OFFSET, center_y + settings.SHADOW_OFFSET,
                       text=text, font=font, fill=settings.SHADOW_COLOR,
                       justify="center", stipple=dim)
        cv.create_text(center_x, center_y, text=text, font=font, fill=color,
                       justify="center", stipple=dim)
        y += height + gap


def run(game_state: Any, on_tick: Callable[[], None] | None = None,
        tick_interval: float | None = None) -> None:
    """Запустить окно. on_tick вызывается каждый тик - это цикл таймеров из main."""
    interval = settings.TICK_INTERVAL if tick_interval is None else tick_interval
    root = _make_window()
    canvas = tk.Canvas(root, highlightthickness=0, borderwidth=0, bg=settings.BG_COLOR)
    canvas.pack(fill="both", expand=True)
    shown = False

    def loop() -> None:
        nonlocal shown
        try:
            if on_tick is not None:
                on_tick()
            alerts = game_state.active_alerts()
            visible = bool(alerts) or settings.DEBUG
            if not visible and settings.HIDE_WHEN_NOT_IN_GAME:
                if shown:                      # прячем окно, когда подсказок нет
                    root.withdraw()
                    shown = False
            elif not shown:
                root.deiconify()
                shown = True
            _draw(canvas, alerts, _debug_lines(game_state) if settings.DEBUG else "")
        except Exception:                      # noqa: BLE001 - оверлей не должен умирать
            LOGGER.exception("ошибка в цикле отрисовки")
        root.after(int(interval * 1000), loop)

    root.after(10, loop)
    LOGGER.info("оверлей запущен, обновление каждые %.2f с", interval)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        LOGGER.info("остановлено пользователем")
    finally:
        LOGGER.info("время работы: %.1f с", time.monotonic() - _STARTED)
        root.destroy()