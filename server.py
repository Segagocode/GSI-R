"""HTTP-приёмник POST-ов от Dota GSI.

Модуль делает ровно две вещи: принимает JSON и передаёт его в state.
Никаких таймингов, никакого tkinter, никаких решений.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import settings

LOGGER = logging.getLogger("dota.server")


def _dump(payload: Any) -> None:
    """Положить последний пакет в logs/gsi_last.json - чтобы проверить реальные ключи GSI."""
    if not settings.DUMP_GSI:
        return
    try:
        settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
        target = settings.LOG_DIR / "gsi_last.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        LOGGER.debug("не смог записать дамп GSI", exc_info=True)


def create_app(game_state: Any) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.post("/")
    async def receive(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
        except Exception:  # noqa: BLE001 - Dota шлёт мусор при выходе из игры
            return JSONResponse({"ok": False}, status_code=400)

        if settings.GSI_KEY:
            sent = request.query_params.get("key") or (
                payload.get("key") if isinstance(payload, dict) else None
            )
            if sent != settings.GSI_KEY:
                LOGGER.warning("POST с чужим ключом - отклонён")
                return JSONResponse({"ok": False}, status_code=403)

        game_state.update(payload)
        _dump(payload)
        return JSONResponse({"ok": True})

    @app.get("/")
    async def ping() -> JSONResponse:
        """Проверка руками: открыть http://127.0.0.1:31337/ в браузере."""
        return JSONResponse({
            "ok": True,
            "in_game": game_state.in_game(),
            "game_state": game_state.game_state(),
            "game_time": round(game_state.clock(), 1),
            "daytime": game_state.is_daytime(),
            "player_id": game_state.player_id(),
            "last_packet_age": round(game_state.last_packet_age(), 2),
        })

    return app


def port_available(port: int | None = None) -> bool:
    """Свободен ли порт. Проверяем до старта, чтобы не ловить трейсбек от uvicorn."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((settings.HOST, settings.PORT if port is None else port))
        except OSError:
            return False
    return True


def serve(game_state: Any) -> None:
    """Блокирующий запуск сервера (его зовёт отдельный поток)."""
    config = uvicorn.Config(
        create_app(game_state),
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.SERVER_LOG_LEVEL,
    )
    LOGGER.info("GSI слушает http://%s:%s", settings.HOST, settings.PORT)
    uvicorn.Server(config).run()


def start_in_thread(game_state: Any) -> threading.Thread:
    thread = threading.Thread(target=serve, args=(game_state,),
                              name="gsi-server", daemon=True)
    thread.start()
    return thread