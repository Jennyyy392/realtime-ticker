"""WebSocket-эндпоинт для трансляции цен в реальном времени.

Эндпоинт подписывается на Redis-канал ``price_updates`` и пересылает
приходящие события подключённому клиенту. Один pubsub-объект создаётся
на каждое клиентское соединение и обязательно закрывается в ``finally``.
"""

import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, WebSocketException

from app.api.v1.dependencies import check_rate_limit
from app.core.logger import logger
from app.redis_client import redis_client

router = APIRouter()

# Канал Redis Pub/Sub, из которого читаем обновления цен.
# Должен совпадать с каналом, в который публикует воркер.
PRICE_UPDATES_CHANNEL = "price_updates"

# Таймаут ожидания сообщения из Redis (секунды).
# Небольшое значение позволяет регулярно проверять состояние клиента.
MESSAGE_TIMEOUT = 1.0


@router.websocket("/ws/prices")
async def websocket_prices(
    websocket: WebSocket,
    rate_limit: None = Depends(check_rate_limit),
) -> None:
    """Транслирует обновления цен клиенту через WebSocket."""
    await websocket.accept()
    logger.info("WebSocket клиент подключён", channel=PRICE_UPDATES_CHANNEL)

    # Отдельная подписка на клиента: свой pubsub и свой набор соединений
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(PRICE_UPDATES_CHANNEL)

    try:
        while True:
            # timeout=1.0 не даёт циклу заблокироваться навсегда:
            # если сообщений нет, вернётся None и мы проверим состояние клиента.
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=MESSAGE_TIMEOUT,
            )

            if message is None:
                # Новых сообщений нет — проверяем, не отключился ли клиент.
                # Короткий poll через receive() перехватывает событие disconnect.
                try:
                    client_message = await asyncio.wait_for(
                        websocket.receive(), timeout=0.01
                    )
                except asyncio.TimeoutError:
                    # Клиент жив, но ничего не прислал — продолжаем ждать обновления
                    continue
                if client_message.get("type") == "websocket.disconnect":
                    logger.info("WebSocket клиент отключён")
                    break
                continue

            if message["type"] == "message":
                data = message["data"]
                # redis.asyncio создан с decode_responses=True, поэтому data может
                # быть уже строкой; на случай bytes — декодируем в UTF-8.
                text = (
                    data.decode("utf-8")
                    if isinstance(data, (bytes, bytearray))
                    else data
                )
                await websocket.send_text(text)
    except WebSocketDisconnect:
        # Клиент отключился в момент отправки
        logger.info("WebSocket клиент отключён")
    finally:
        # Обязательно отписываемся и закрываем pubsub, иначе соединение
        # останется висеть в Redis и приведёт к утечке ресурсов
        await pubsub.unsubscribe(PRICE_UPDATES_CHANNEL)
        await pubsub.close()
        logger.info("PubSub подписка закрыта")
