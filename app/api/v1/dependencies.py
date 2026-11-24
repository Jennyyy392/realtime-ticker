"""Переиспользуемые зависимости FastAPI для API v1.

Сейчас здесь реализовано ограничение частоты WebSocket-подключений
(rate limiting) на базе асинхронного Redis-клиента приложения.
"""

from fastapi import Depends, WebSocket, WebSocketException

from app.config import settings
from app.core.logger import logger
from app.redis_client import get_redis

# Префикс ключа в Redis: rate_limit:ws:{client_ip}.
RATE_LIMIT_KEY_PREFIX = "rate_limit:ws"


async def check_rate_limit(
    websocket: WebSocket,
    redis=Depends(get_redis),
) -> None:
    """Проверяет лимит подключений с одного IP-адреса.

    Использует счётчик Redis: ``INCR`` увеличивает значение атомарно,
    а ``EXPIRE ... NX`` задаёт время жизни ключа при первом запросе.
    Это позволяет реализовать фиксированное окно (fixed window) без
    гонок данных.

    При превышении лимита выбрасывается ``WebSocketException`` с кодом
    1008 (Policy Violation), поэтому соединение не принимается.
    """
    # Определяем IP-адрес клиента: заголовок X-Forwarded-For учитывается
    # только при доверии к прокси (settings.TRUST_PROXY_HEADERS).
    if settings.TRUST_PROXY_HEADERS:
        forwarded_for = websocket.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            # websocket.client может быть None, например при тестировании
            # или отсутствии данных о соединении.
            client_ip = (
                websocket.client.host if websocket.client else "unknown"
            )
    else:
        client_ip = websocket.client.host if websocket.client else "unknown"

    # Формируем ключ вида rate_limit:ws:{client_ip}
    key = f"{RATE_LIMIT_KEY_PREFIX}:{client_ip}"

    # Атомарно (в одной транзакции) увеличиваем счётчик и задаём TTL.
    # EXPIRE с nx=True выставляет срок жизни только при отсутствии TTL,
    # поэтому окно не продлевается при каждом новом подключении.
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, settings.WS_RATE_LIMIT_WINDOW, nx=True)
        current, _ = await pipe.execute()

    # Превышение лимита — отклоняем подключение (код 1008: Policy Violation).
    if current > settings.WS_RATE_LIMIT_MAX:
        logger.warning(
            "Превышен лимит подключений",
            client_ip=client_ip,
            current=current,
            limit=settings.WS_RATE_LIMIT_MAX,
        )
        raise WebSocketException(
            code=1008,
            reason="Rate limit exceeded. Try again later.",
        )

    logger.info(
        "Rate limit проверен",
        client_ip=client_ip,
        current=current,
        limit=settings.WS_RATE_LIMIT_MAX,
    )
