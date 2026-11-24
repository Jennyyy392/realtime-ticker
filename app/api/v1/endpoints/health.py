"""Эндпоинт проверки работоспособности."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.core.logger import logger
from app.redis_client import get_redis

router = APIRouter()


@router.get("/health")
async def health_check(redis: Redis = Depends(get_redis)):
    """Проверка работоспособности API и Redis."""
    try:
        await redis.ping()
        return {"status": "ok", "redis": "connected"}
    except Exception as e:
        logger.error("healthcheck_redis_failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={"status": "error", "redis": "unavailable"},
        )
