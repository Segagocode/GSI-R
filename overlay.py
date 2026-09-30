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


def _window_geometry(root: tk.Tk) -> str:
    """Строго справа: X = ширина экрана - ширина окна - отступ.

    Экран берём у самого tkinter (winfo_screenwidth) - надёжнее константы в
    settings; WINDOW_RIGHT_EDGE остаётся запасным значением.
    """
    try:
        screen_w = root.winfo_screenwidth()
    except Exception:                        # noqa: BLE001 - до появления окна может не быть
        screen_w = settings.WINDOW_RIGHT_EDGE
    x = max(0, screen_w - settings.WINDOW_WIDTH - settings.WINDOW_MARGIN)
    return f"{settings.WINDOW_WIDTH}x{settings.WINDOW_HEIGHT}+{x}+{settings.WINDOW_Y}"


def _make_window() -> tk.Tk:
    root = tk.Tk()
    root.title("dota overlay")
    root.overrideredirect(True)                       # окно без рамки
    root.attributes("-topmost", True)
    root.attributes("-alpha", settings.WINDOW_ALPHA)  # полупрозрачно
    root.configure(bg=settings.BG_COLOR)
    root.resizable(False, False)
    root.geometry(_window_geometry(root))
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


def _fmt_remaining(seconds: float) -> str:
    """'7с' / '1:23' - компактный обратный отсчёт в углу карточки."""
    whole = max(0, int(round(seconds)))
    if whole < 60:
        return f"{whole}с"
    return f"{whole // 60}:{whole % 60:02d}"


def _draw(cv: tk.Canvas, alerts: list[dict[str, Any]], debug_text: str) -> None:
    """Карточки у правого края: акцентная полоса + заголовок/детали, отсчёт справа.

    Текст больше не скачет по центру: каждая подсказка - плашка фиксированной
    ширины, выровненная по правому краю окна.
    """
    cv.delete("all")
    pad = settings.PANEL_PAD
    font_title = (settings.FONT_FAMILY, settings.FONT_SIZE, "bold")
    font_small = (settings.FONT_FAMILY, max(9, settings.FONT_SIZE - 8), "")
    w = settings.WINDOW_WIDTH
    right = w - pad                      # внутренний правый край
    line_h = int(settings.FONT_SIZE * 1.25)

    if debug_text:
        cv.create_text(right, 6, anchor="ne", text=debug_text,
                       font=font_small, fill="#7fd4ff", justify="right")

    card_h = lambda a: line_h * (a["text"].count("\n") + 1) + pad
    total = sum(card_h(a) for a in alerts) + pad * max(0, len(alerts) - 1)
    y = max(28 if debug_text else pad, (settings.WINDOW_HEIGHT - total) / 2)

    for alert in alerts:
        urgent = alert["urgent"]
        height = card_h(alert)
        accent = settings.ACCENT_URGENT if urgent else settings.ACCENT_NORMAL
        dim = "gray50" if alert["remaining"] <= 1.0 else None  # гаснет перед исчезновением

        cv.create_rectangle(pad, y, right, y + height, fill=settings.BG_COLOR,
                            outline=accent, width=1, stipple=dim)
        cv.create_rectangle(pad, y, pad + 4, y + height, fill=accent,
                            outline="", stipple=dim)

        lines = alert["text"].split("\n")
        ty = y + pad // 2 + line_h // 2
        for i, line in enumerate(lines):
            size = font_title if i == 0 else font_small
            color = (settings.URGENT_COLOR if urgent else settings.TEXT_COLOR) \
                if i == 0 else ("#b9b9c2" if not urgent else settings.URGENT_COLOR)
            x_text = pad + 14
            # тень под текстом = читаемость на любом фоне игры
            cv.create_text(x_text + settings.SHADOW_OFFSET, ty + settings.SHADOW_OFFSET,
                           anchor="w", text=line, font=size, fill=settings.SHADOW_COLOR,
                           stipple=dim)
            cv.create_text(x_text, ty, anchor="w", text=line, font=size,
                           fill=color, stipple=dim)
            ty += line_h

        cv.create_text(right - 8, y + height // 2, anchor="e",
                       text=_fmt_remaining(alert["remaining"]),
                       font=font_small, fill=accent, stipple=dim)
        y += height + pad


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