"""WebSocket-эндпоинт для трансляции цен в реальном времени.

Эндпоинт не создаёт собственную подписку Redis: он регистрирует
индивидуальную ``asyncio.Queue`` в общем процессе-``PriceBroadcaster``,
который держит единственное соединение с Redis Pub/Sub на всех клиентов.
"""

import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.v1.dependencies import check_rate_limit
from app.config import settings
from app.core.logger import logger
from app.services.broadcaster import broadcaster

router = APIRouter()


@router.websocket("/ws/prices")
async def websocket_prices(
    websocket: WebSocket,
    rate_limit: None = Depends(check_rate_limit),
) -> None:
    """Транслирует обновления цен клиенту через WebSocket."""
    await websocket.accept()
    logger.info(
        "WebSocket клиент подключён", channel=settings.PRICE_UPDATES_CHANNEL
    )

    try:
        queue = broadcaster.subscribe()
    except RuntimeError:
        await websocket.close(code=1013, reason="Server busy")
        return

    async def receive_loop() -> None:
        """Ждёт сообщений от клиента и завершается при отключении."""
        while True:
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                logger.info("WebSocket клиент отключён")
                return
            if message.get("type") == "websocket.disconnect":
                logger.info("WebSocket клиент отключён")
                return

    async def send_loop() -> None:
        """Отправляет клиенту сообщения из очереди Broadcaster."""
        while True:
            text = await queue.get()
            try:
                await websocket.send_text(text)
            except WebSocketDisconnect:
                logger.info("WebSocket клиент отключён при отправке")
                return

    receive_task = asyncio.create_task(receive_loop(), name="ws-receive")
    send_task = asyncio.create_task(send_loop(), name="ws-send")

    try:
        await asyncio.wait(
            [receive_task, send_task], return_when=asyncio.FIRST_COMPLETED
        )
    except asyncio.CancelledError:
        pass
    finally:
        pending = [receive_task, send_task]
        for task in pending:
            if not task.done():
                task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        broadcaster.unsubscribe(queue)
        logger.info("Подписка клиента на рассылку закрыта")