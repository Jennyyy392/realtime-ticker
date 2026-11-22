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

from app.core.logger import logger

# Список отслеживаемых монет
SYMBOLS = ["BTC", "ETH", "SOL", "TON"]

# Базовые (референсные) цены для имитации рыночных колебаний
BASE_PRICES = {
    "BTC": 65000.0,
    "ETH": 3500.0,
    "SOL": 150.0,
    "TON": 7.0,
}

# Канал Redis Pub/Sub, в который публикуются обновления цен.
# Должен совпадать с каналом, на который подписывается WebSocket-эндпоинт.
PRICE_UPDATES_CHANNEL = "price_updates"

# Интервал между обновлениями цен в секундах
UPDATE_INTERVAL = 3


async def price_update_worker(redis_client: redis.Redis) -> None:
    """Бесконечный цикл имитации цен с публикацией в Redis.

    Для каждого символа генерируется цена в диапазоне ±5% от базовой,
    затем она сохраняется в Redis (для HTTP-эндпоинтов) и публикуется
    в канал ``price_updates`` (для WebSocket-подписчиков).
    """
    logger.info("Фоновый воркер цен запущен", symbols=SYMBOLS)

    try:
        while True:
            for symbol in SYMBOLS:
                base_price = BASE_PRICES[symbol]
                # Имитируем рыночное колебание: базовая цена * случайный коэффициент 0.95..1.05
                price = round(base_price * random.uniform(0.95, 1.05), 2)

                # Сохраняем актуальную цену для HTTP-эндпоинтов
                await redis_client.set(f"price:{symbol}", price)

                # Публикуем событие в канал для WebSocket-подписчиков
                await redis_client.publish(
                    PRICE_UPDATES_CHANNEL,
                    json.dumps({"symbol": symbol, "price": price}),
                )

                # Пауза между обновлениями: отдаём управление event loop
                await asyncio.sleep(UPDATE_INTERVAL)
    except asyncio.CancelledError:
        # Штатная остановка воркера при завершении приложения
        logger.info("Фоновый воркер цен остановлен (задача отменена)")
        raise
    except Exception as e:
        # Логируем любую непредвиденную ошибку, чтобы воркер не падал молча
        logger.error("Ошибка в фоновом воркере цен", error=str(e))
