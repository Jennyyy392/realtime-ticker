"""Маршруты API версии v1."""

from fastapi import APIRouter

from app.api.v1.endpoints import health, prices

# Основной роутер для версии v1
router = APIRouter()

# Подключаем эндпоинт проверки работоспособности
router.include_router(health.router, tags=["health"])
# Подключаем эндпоинты цен с префиксом /prices
router.include_router(prices.router, prefix="/prices", tags=["prices"])
