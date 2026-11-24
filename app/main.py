"""Точка входа приложения RealTimeTicker."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.config import settings
from app.core.exceptions import SymbolNotFoundError, global_exception_handler, symbol_not_found_handler
from app.core.logger import logger, setup_logging
from app.redis_client import redis_client
from app.services.broadcaster import broadcaster
from app.services.price_worker import price_update_worker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Жизненный цикл приложения: подключение к Redis при старте/остановке."""
    # Настраиваем логирование в самом начале запуска приложения
    setup_logging()
    logger.info("Приложение запускается", debug_mode=settings.DEBUG)

    # Проверяем подключение к Redis при ЗАПУСКЕ приложения
    try:
        await redis_client.ping()
        logger.info("Подключение к Redis успешно")
    except Exception as e:
        logger.error("Ошибка подключения к Redis", error=str(e))
        raise

    # Запускаем фоновый воркер цен как фоновую задачу, чтобы он не блокировал
    # обработку запросов и корректно останавливался вместе с приложением
    worker_task = asyncio.create_task(price_update_worker(redis_client))
    logger.info("Фоновый воркер цен запущен как задача")

    # Единственная на процесс подписка на Redis Pub/Sub: рассылает
    # сообщения активным WebSocket-клиентам через их asyncio.Queue
    await broadcaster.start()

    yield  # Здесь работает приложение

    # Код, который выполняется при ОСТАНОВКЕ приложения
    await broadcaster.stop()

    # Отменяем фоновую задачу и дожидаемся её завершения
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        logger.info("Фоновая задача воркера цен отменена")

    # Закрываем пул соединений Redis
    await redis_client.aclose()

# Создание приложения FastAPI
app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

# Регистрация обработчиков исключений
app.add_exception_handler(SymbolNotFoundError, symbol_not_found_handler)
app.add_exception_handler(Exception, global_exception_handler)

# Подключение маршрутов v1 с префиксом из настроек
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)