"""Окно подсказок: рамки нет, поверх всех, полупрозрачное, клики проходят в игру.

Модуль только рисует. Он берёт готовый список подсказок из state и не знает,
откуда они взялись и что за таймер их создал.

Рендер — PyQt6 (кроссплатформенно: Windows / Linux / macOS). Прозрачность окна
обеспечивается атрибутом WA_TranslucentBackground (без setWindowOpacity!),
карточки рисуются в paintEvent через QPainter.

Click-through сделан платформенно:
  * Windows: WS_EX_TRANSPARENT | WS_EX_NOACTIVATE через ctypes;
  * Linux/X11: WA_TransparentForMouseEvents + тип Tool/BypassWM;
  * macOS: TODO — NSWindow.ignoresMouseEvents через pyobjc при реальном порте.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any, Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

import settings

LOGGER = logging.getLogger("dota.overlay")

_STARTED = time.monotonic()


# ------------------------------------------------------------------ click-through
def _make_click_through_win(hwnd: int) -> None:
    """Windows: WS_EX_TRANSPARENT + NOACTIVATE + TOOLWINDOW, чтобы клики шли в игру."""
    import ctypes

    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_LAYERED = 0x00080000
    WS_EX_NOACTIVATE = 0x08000000
    HWND_TOPMOST = -1
    SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x0002, 0x0001, 0x0010

    user32 = ctypes.windll.user32
    if hasattr(user32, "SetWindowLongPtrW"):
        get_long, set_long = user32.GetWindowLongPtrW, user32.SetWindowLongPtrW
        long_ptr = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
    else:  # 32-битная Windows
        get_long, set_long = user32.GetWindowLongW, user32.SetWindowLongW
        long_ptr = ctypes.c_long
    get_long.argtypes = (ctypes.c_void_p, ctypes.c_int)
    get_long.restype = long_ptr
    set_long.argtypes = (ctypes.c_void_p, ctypes.c_int, long_ptr)
    set_long.restype = long_ptr

    style = get_long(hwnd, GWL_EXSTYLE)
    set_long(hwnd, GWL_EXSTYLE,
             style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def _apply_click_through(widget: QWidget) -> None:
    """Платформенный click-through; на неизвестной платформе — тихий no-op."""
    if not settings.CLICK_THROUGH:
        return
    try:
        if sys.platform == "win32":
            _make_click_through_win(int(widget.winId()))
        elif sys.platform.startswith("linux"):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        # macOS: TODO — NSWindow.ignoresMouseEvents через pyobjc при реальном порте.
    except Exception:                       # noqa: BLE001 — оверлей не должен умирать
        LOGGER.exception("не удалось включить click-through")


# ------------------------------------------------------------------ формат
def _fmt_remaining(seconds: float) -> str:
    """'7с' / '1:23' — компактный обратный отсчёт в углу карточки."""
    whole = max(0, int(round(seconds)))
    if whole < 60:
        return f"{whole}с"
    return f"{whole // 60}:{whole % 60:02d}"


def _debug_lines(game_state: Any) -> str:
    hero = game_state.hero()
    daytime = game_state.is_daytime()
    return (f"clock {int(game_state.clock() // 60)}:{int(game_state.clock() % 60):02d}"
            f"  {game_state.clock_source()}"
            f"  день={daytime if daytime is not None else '?'}"
            f"  герой={hero['name']} lv{hero['level']}"
            f"  золото={hero['gold']}"
            f"  пакет={game_state.last_packet_age():.1f}с назад")


# ------------------------------------------------------------------ виджет
class OverlayWidget(QWidget):
    """Прозрачное окно-плашка строго справа. paintEvent рисует карточки подсказок."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("dota overlay")
        flags = (Qt.WindowType.FramelessWindowHint
                 | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.Tool)
        if sys.platform.startswith("linux"):
            flags |= Qt.WindowType.BypassWindowManagerHint
        self.setWindowFlags(flags)
        # ВАЖНО: НЕ вызывать setWindowOpacity — фон уже прозрачный
        # за счёт WA_TranslucentBackground; opacity удвоила бы полупрозрачность.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT)
        self._place_right()
        self.alerts: list[dict[str, Any]] = []
        self.debug_text = ""
        self._font_title = QFont(settings.FONT_FAMILY, settings.FONT_SIZE, QFont.Weight.Bold)
        self._font_small = QFont(settings.FONT_FAMILY, max(9, settings.FONT_SIZE - 8))

    def _place_right(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        x = max(0, screen.width() - settings.WINDOW_WIDTH - settings.WINDOW_MARGIN)
        self.move(x, settings.WINDOW_Y)

    def paintEvent(self, event) -> None:                      # noqa: N802 — Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pad = settings.PANEL_PAD
        right = settings.WINDOW_WIDTH - pad
        line_h = QFontMetrics(self._font_title).height()
        alerts = self.alerts

        def card_height(a: dict[str, Any]) -> int:
            return line_h * (a["text"].count("\n") + 1) + pad

        total = sum(card_height(a) for a in alerts) + pad * max(0, len(alerts) - 1)
        y = max(28 if self.debug_text else pad,
                (settings.WINDOW_HEIGHT - total) / 2)

        base_alpha = int(255 * settings.WINDOW_ALPHA)
        # окно живёт и когда подсказок нет (DEBUG/HIDE_WHEN_NOT_IN_GAME=False)
        if not alerts and not self.debug_text:
            return

        if self.debug_text:
            dbg = QColor("#7fd4ff")
            dbg.setAlpha(base_alpha)
            painter.setFont(self._font_small)
            painter.setPen(dbg)
            painter.drawText(self.rect().adjusted(0, 4, -pad, 0),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
                             self.debug_text)

        for alert in alerts:
            urgent = alert["urgent"]
            fading = alert["remaining"] <= 1.0
            alpha = 90 if fading else base_alpha
            accent = QColor(settings.ACCENT_URGENT if urgent else settings.ACCENT_NORMAL)
            accent.setAlpha(alpha)
            height = card_height(alert)

            bg = QColor(settings.BG_COLOR)
            bg.setAlpha(alpha)
            painter.fillRect(pad, int(y), right - pad, height, bg)
            painter.setPen(QPen(accent, 1))
            painter.drawRect(pad, int(y), right - pad - 1, height - 1)
            painter.fillRect(pad, int(y), 4, height, accent)   # акцентная полоса слева

            lines = alert["text"].split("\n")
            ty = y + pad // 2 + line_h
            for i, line in enumerate(lines):
                if i == 0:
                    painter.setFont(self._font_title)
                    color = settings.URGENT_COLOR if urgent else settings.TEXT_COLOR
                else:
                    painter.setFont(self._font_small)
                    color = settings.URGENT_COLOR if urgent else "#b9b9c2"
                text_color = QColor(color)
                text_color.setAlpha(alpha)
                shadow = QColor(settings.SHADOW_COLOR)
                shadow.setAlpha(alpha)
                off = settings.SHADOW_OFFSET
                painter.setPen(shadow)                          # тень = читаемость на фоне игры
                painter.drawText(pad + 14 + off, int(ty + off), line)
                painter.setPen(text_color)
                painter.drawText(pad + 14, int(ty), line)
                ty += line_h

            painter.setFont(self._font_small)
            painter.setPen(accent)
            painter.drawText(pad, int(y), right - pad - 8, height,
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             _fmt_remaining(alert["remaining"]))
            y += height + pad


# ------------------------------------------------------------------ точка входа
def run(game_state: Any, on_tick: Callable[[], None] | None = None,
        tick_interval: float | None = None) -> None:
    """Запустить окно. on_tick вызывается каждый тик — это цикл таймеров из main."""
    interval = settings.TICK_INTERVAL if tick_interval is None else tick_interval
    app = QApplication.instance() or QApplication(sys.argv[:1])
    widget = OverlayWidget()
    shown = False

    def loop() -> None:
        nonlocal shown
        alerts: list[dict[str, Any]] = []
        try:
            if on_tick is not None:
                on_tick()                     # упал тик — не показываем устаревшее
            alerts = game_state.active_alerts()
        except Exception:                   # noqa: BLE001 — оверлей не должен умирать
            LOGGER.exception("ошибка в цикле отрисовки")
        visible = bool(alerts) or settings.DEBUG
        try:
            if not visible and settings.HIDE_WHEN_NOT_IN_GAME:
                if shown:
                    widget.hide()
                    shown = False
            elif not shown:
                widget.show()
                _apply_click_through(widget)     # winId доступен после show()
                shown = True
            widget.alerts = alerts
            widget.debug_text = _debug_lines(game_state) if settings.DEBUG else ""
            widget.update()
        except Exception:                   # noqa: BLE001
            LOGGER.exception("ошибка показа окна")

    timer = QTimer(widget)
    timer.timeout.connect(loop)
    timer.start(int(interval * 1000))
    LOGGER.info("оверлей запущен (PyQt6), обновление каждые %.2f с", interval)
    try:
        app.exec()
    except KeyboardInterrupt:
        LOGGER.info("остановлено пользователем")
    finally:
        LOGGER.info("время работы: %.1f с", time.monotonic() - _STARTED)
