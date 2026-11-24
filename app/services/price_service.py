"""Сервисный слой для работы с ценами криптовалют в Redis.

Инкапсулирует ключи и операции с кэшем, чтобы эндпоинты не работали
с Redis напрямую и не зависели от форматов ключей.
"""

import redis.asyncio as redis
from fastapi import Depends
from redis.asyncio import Redis

from app.config import settings
from app.core.exceptions import SymbolNotFoundError
from app.core.logger import logger
from app.redis_client import get_redis


class PriceService:
    """Бизнес-логика работы с ценами в Redis."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def get_price(self, symbol: str) -> dict:
        """Получает цену из Redis или возвращает 404."""
        symbol_upper = symbol.upper()
        price = await self.redis.get(
            settings.PRICE_KEY_TEMPLATE.format(symbol=symbol_upper)
        )
        if price is None:
            raise SymbolNotFoundError(symbol_upper)
        return {"symbol": symbol_upper, "price": float(price)}

    async def set_price(self, symbol: str, price: float) -> None:
        """Сохраняет цену в Redis."""
        key = settings.PRICE_KEY_TEMPLATE.format(symbol=symbol.upper())
        await self.redis.set(key, price)
        logger.info("Цена обновлена", symbol=symbol.upper(), price=price)


async def get_price_service(redis_client: Redis = Depends(get_redis)) -> PriceService:
    """Dependency для получения экземпляра PriceService."""
    return PriceService(redis_client)
