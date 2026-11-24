"""Фоновый воркер, имитирующий получение цен и публикующий их в Redis Pub/Sub.

Воркер полностью асинхронный: между обновлениями он отдаёт управление
другим задачам через ``asyncio.sleep`` и не блокирует event loop FastAPI.
Помимо публикации события в канал, воркер сохраняет актуальную цену
в Redis обычным ключом ``price:{symbol}`` — её читают HTTP-эндпоинты.
"""

import asyncio
import json
import random

import redis.asyncio as redis

from app.config import settings
from app.core.logger import logger

# Базовые (референсные) цены для имитации рыночных колебаний
BASE_PRICES = {
    "BTC": 65000.0,
    "ETH": 3500.0,
    "SOL": 150.0,
    "TON": 7.0,
}


async def price_update_worker(redis_client: redis.Redis) -> None:
    """Бесконечный цикл имитации цен с публикацией в Redis.

    Для каждого символа генерируется цена в диапазоне ±5% от базовой,
    затем она сохраняется в Redis (для HTTP-эндпоинтов) и публикуется
    в канал ``price_updates`` (для WebSocket-подписчиков).
    """
    logger.info("Фоновый воркер цен запущен", symbols=settings.TRACKED_SYMBOLS)

    try:
        while True:
            try:
                async with redis_client.pipeline(transaction=False) as pipe:
                    for symbol in settings.TRACKED_SYMBOLS:
                        base_price = BASE_PRICES.get(symbol, 100.0)
                        # Имитируем рыночное колебание: базовая цена * случайный коэффициент 0.95..1.05
                        price = round(base_price * random.uniform(0.95, 1.05), 2)

                        # Сохраняем актуальную цену для HTTP-эндпоинтов
                        pipe.set(settings.PRICE_KEY_TEMPLATE.format(symbol=symbol), price)

                        # Публикуем событие в канал для WebSocket-подписчиков
                        pipe.publish(
                            settings.PRICE_UPDATES_CHANNEL,
                            json.dumps({"symbol": symbol, "price": price}),
                        )

                    # Отправляем все команды одной пачкой за один round-trip к Redis
                    await pipe.execute()

                # Пауза между обновлениями: отдаём управление event loop
                await asyncio.sleep(settings.PRICE_UPDATE_INTERVAL)
            except Exception as e:
                # Логируем любую непредвиденную ошибку, чтобы воркер не падал молча
                logger.error("Ошибка в фоновом воркере цен", error=str(e))
                # Пауза перед повторной попыткой, чтобы не спамить при сбое Redis
                await asyncio.sleep(5)
    except asyncio.CancelledError:
        # Штатная остановка воркера при завершении приложения
        logger.info("Фоновый воркер цен остановлен (задача отменена)")
        raise
