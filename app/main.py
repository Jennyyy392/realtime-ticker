"""Точка входа приложения RealTimeTicker."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.config import settings
from app.core.exceptions import global_exception_handler
from app.core.logger import logger, setup_logging
from app.redis_client import redis_client


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

    yield  # Здесь работает приложение

    # Код, который выполняется при ОСТАНОВКЕ приложения
    await redis_client.close()
    logger.info("Приложение остановлено")


# Создание приложения FastAPI
app = FastAPI(title="RealTimeTicker", debug=settings.DEBUG, lifespan=lifespan)

# Регистрация глобального обработчика всех необработанных исключений
app.add_exception_handler(Exception, global_exception_handler)

# Подключение маршрутов v1 с префиксом из настроек
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)
