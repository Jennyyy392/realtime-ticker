"""Переиспользуемые зависимости FastAPI для API v1.

Сейчас здесь реализовано ограничение частоты WebSocket-подключений
(rate limiting) на базе асинхронного Redis-клиента приложения.
"""

from fastapi import Depends, WebSocket, WebSocketException

from app.core.logger import logger
from app.redis_client import get_redis

# Максимальное число подключений с одного IP-адреса за окно в секундах.
RATE_LIMIT_MAX_CONNECTIONS = 10

# Длительность окна ограничения (в секундах).
RATE_LIMIT_WINDOW_SECONDS = 60

# Префикс ключа в Redis: rate_limit:ws:{client_ip}.
RATE_LIMIT_KEY_PREFIX = "rate_limit:ws"


async def check_rate_limit(
    websocket: WebSocket,
    redis=Depends(get_redis),
) -> None:
    """Проверяет лимит подключений с одного IP-адреса.

    Использует счётчик Redis: ``INCR`` увеличивает значение атомарно,
    а ``EXPIRE`` задаёт время жизни ключа при первом запросе. Это
    позволяет реализовать скользящее окно без гонок данных.

    При превышении лимита выбрасывается ``WebSocketException`` с кодом
    1008 (Policy Violation), поэтому соединение не принимается.
    """
    # Определяем IP-адрес клиента. websocket.client может быть None,
    # например при тестировании или отсутствии данных о соединении.
    client_ip = websocket.client.host if websocket.client else "unknown"

    # Формируем ключ вида rate_limit:ws:{client_ip}
    key = f"{RATE_LIMIT_KEY_PREFIX}:{client_ip}"

    # Атомарно увеличиваем счётчик и получаем новое значение.
    current = await redis.incr(key)

    # Если это первое подключение в окне (счётчик стал равен 1),
    # задаём TTL — по истечении которого ключ удалится сам.
    # EXPIRE ставим ровно один раз, чтобы окно не продлевалось
    # при каждом новом подключении.
    if current == 1:
        await redis.expire(key, RATE_LIMIT_WINDOW_SECONDS)

    # Превышение лимита — отклоняем подключение (код 1008: Policy Violation).
    if current > RATE_LIMIT_MAX_CONNECTIONS:
        logger.warning(
            "Превышен лимит подключений",
            client_ip=client_ip,
            current=current,
            limit=RATE_LIMIT_MAX_CONNECTIONS,
        )
        raise WebSocketException(
            code=1008,
            reason="Rate limit exceeded. Try again later.",
        )

    logger.info(
        "Rate limit проверен",
        client_ip=client_ip,
        current=current,
        limit=RATE_LIMIT_MAX_CONNECTIONS,
    )
