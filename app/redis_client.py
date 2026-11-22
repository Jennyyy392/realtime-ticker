"""Асинхронный клиент Redis для RealTimeTicker.

Используется redis.asyncio — асинхронная реализация клиента, чтобы
не блокировать event loop FastAPI во время операций ввода-вывода.
"""

import redis.asyncio as redis

from app.config import settings

# Единый асинхронный клиент Redis на всё приложение.
# Соединение устанавливается лениво (при первой команде), поэтому
# создание объекта здесь ничего не блокирует.
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True,
)


async def get_redis() -> redis.Redis:
    """Dependency для FastAPI."""
    return redis_client
