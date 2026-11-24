"""Broadcaster: одна подписка на Redis Pub/Sub на весь процесс.

Единственный фоновый подписчик читает канал ``price_updates`` и раскладывает
сообщения в индивидуальные ``asyncio.Queue`` активных WebSocket-клиентов.
Так Redis держит одно соединение независимо от числа клиентов, а медленный
клиент не тормозит остальных (у него переполняется только своя очередь).
"""

import asyncio

import redis.asyncio as redis

from app.core.logger import logger
from app.config import settings
from app.redis_client import redis_client

# Таймаут ожидания сообщения из Redis (секунды).
MESSAGE_TIMEOUT = 1.0

# Максимальный размер очереди одного клиента. При переполнении
# отбрасывается самое старое сообщение — клиенту нужны свежие цены.
QUEUE_MAXSIZE = 100

# Пауза перед переподключением к Redis после ошибки (секунды).
RECONNECT_DELAY = 1.0


class PriceBroadcaster:
    """Один подписчик Redis Pub/Sub, рассылающий сообщения через очереди."""

    def __init__(self, redis_client: redis.Redis, channel: str) -> None:
        self._redis = redis_client
        self._channel = channel
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Запускает фоновую задачу-подписчик."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._listen(), name="price-broadcaster")
            logger.info("Broadcaster запущен", channel=self._channel)

    async def stop(self) -> None:
        """Отменяет задачу-подписчик и дожидается её завершения."""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            logger.info("Broadcaster остановлен")
        self._task = None

    def subscribe(self) -> asyncio.Queue[str]:
        """Регистрирует нового клиента и возвращает его очередь."""
        if len(self._subscribers) >= settings.MAX_WS_CONNECTIONS:
            raise RuntimeError("Max WebSocket connections reached")
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        """Удаляет очередь клиента из рассылки."""
        self._subscribers.discard(queue)

    async def _listen(self) -> None:
        """Читает Redis-канал и рассылает сообщения подписчикам."""
        while True:
            pubsub = self._redis.pubsub()
            try:
                await pubsub.subscribe(self._channel)
                while True:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=MESSAGE_TIMEOUT,
                    )
                    if message is not None and message["type"] == "message":
                        self._dispatch(message["data"])
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Ошибка подписки Broadcaster", error=str(e))
                await asyncio.sleep(RECONNECT_DELAY)
            finally:
                # Закрываем сломанную подписку перед следующей попыткой
                try:
                    await pubsub.unsubscribe(self._channel)
                    await asyncio.wait_for(pubsub.aclose(), timeout=1.0)
                except Exception:
                    pass

    def _dispatch(self, data: str | bytes) -> None:
        """Кладёт сообщение в очередь каждому клиенту без блокировки."""
        text = data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else data
        for queue in tuple(self._subscribers):
            try:
                queue.put_nowait(text)
            except asyncio.QueueFull:
                # Клиент не успевает читать — выбрасываем самое старое
                try:
                    queue.get_nowait()
                    queue.put_nowait(text)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass


# Единственный Broadcaster на процесс. Канал совпадает с каналом воркера.
broadcaster = PriceBroadcaster(redis_client, settings.PRICE_UPDATES_CHANNEL)