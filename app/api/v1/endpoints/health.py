"""Эндпоинт проверки работоспособности."""

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.redis_client import get_redis

router = APIRouter()


@router.get("/health")
async def health_check(redis: Redis = Depends(get_redis)):
    """Проверка работоспособности API и Redis."""
    try:
        await redis.ping()
        return {"status": "ok", "redis": "connected"}
    except Exception as e:
        return {"status": "error", "redis": str(e)}
