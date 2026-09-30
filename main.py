"""Точка входа: связывает модули и запускает всё.

Настройки -> cfg для GSI -> HTTP-сервер (поток) -> окно (главный поток).
Таймеры крутятся в callback'е окна, поэтому им не нужен свой поток.
"""

from __future__ import annotations

import argparse
import logging
import threading
import time

import gsi_setup
import overlay
import server
import settings
import state
import timers
import opendota

LOGGER = logging.getLogger("dota")


def _watch_first_packet(game_state: state.GameState, done: dict) -> None:
    """Раз увидели пакет от GSI - пишем в cfg steamid и рапортуем, что всё живо."""
    while True:
        try:
            if game_state.last_packet_age() >= 0:
                if not done.get("announced"):
                    hero = game_state.hero()
                    LOGGER.info("GSI: первый пакет | игрок=%s герой=%s ур=%s состояние=%s "
                                "время=%.1f (%s) день=%s",
                                hero["name_player"] or "?", hero["name"] or "?",
                                hero["level"], game_state.game_state() or "?",
                                game_state.clock(), game_state.clock_source(),
                                game_state.is_daytime())
                    LOGGER.info("GSI: способности = %s",
                                ", ".join(f"{a['name']}(кд {a['cooldown']:.0f})"
                                          for a in game_state.abilities()))
                    if settings.DUMP_GSI:
                        LOGGER.info("GSI: полный пакет -> %s",
                                    settings.LOG_DIR / "gsi_last.json")
                    done["announced"] = True

                player_id = game_state.player_id()
                if player_id and not done.get("steamid"):
                    done["steamid"] = gsi_setup.update_steamid(player_id)
            time.sleep(1.0)
        except Exception:                      # noqa: BLE001
            LOGGER.exception("поток наблюдения упал")
            return


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Оверлей-шпаргалка по данным GSI")
    parser.add_argument("--cfg-only", action="store_true",
                        help="только создать/обновить cfg и выйти")
    parser.add_argument("--no-cfg", action="store_true", help="не трогать cfg совсем")
    parser.add_argument("--force-cfg", action="store_true", help="перезаписать cfg принудительно")
    parser.add_argument("--debug", action="store_true", help="часы и данные GSI поверх окна")
    parser.add_argument("--log-level", default="info",
                        choices=("debug", "info", "warning", "error"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)-7s %(name)-16s %(message)s",
    )
    settings.DEBUG = args.debug

    game_state = state.GameState()

    if not args.no_cfg:
        cfg = gsi_setup.ensure_config(force=args.force_cfg)
        if cfg is None:
            LOGGER.warning("cfg не создан. Пока не записан cfg - Dota не будет слать данные")
    if args.cfg_only:
        return 0

    if not server.port_available():
        LOGGER.error("порт %s уже занят. Закрой прошлое окно приложения "
                     "или поменяй PORT в settings.py", settings.PORT)
        return 1

    server.start_in_thread(game_state)
    opendota.start_background(game_state)
    threading.Thread(target=_watch_first_packet, args=(game_state, {}),
                     name="first-packet", daemon=True).start()

    LOGGER.info("ждём GSI от Dota на http://%s:%s", settings.HOST, settings.PORT)
    LOGGER.info("в игре окно должно быть в режиме «окно без рамки»")

    overlay.run(game_state, on_tick=lambda: timers.tick_all(game_state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
