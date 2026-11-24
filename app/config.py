"""Настройки приложения RealTimeTicker.

Значения читаются из переменных окружения, а также из файла .env
(если он существует в корне проекта).
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация приложения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Название сервиса (используется в заголовке API и ответах)
    APP_NAME: str = "RealTimeTicker"
    # Режим отладки (влияет на формат логов и debug-режим FastAPI)
    DEBUG: bool = True
    # Префикс для маршрутов версии v1
    API_V1_PREFIX: str = "/api/v1"

    # Параметры подключения к Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Интервал обновления цен воркером (секунды)
    PRICE_UPDATE_INTERVAL: float = 3.0
    # Список отслеживаемых символов
    TRACKED_SYMBOLS: list[str] = ["BTC", "ETH", "SOL", "TON"]
    # Канал Redis Pub/Sub с обновлениями цен
    PRICE_UPDATES_CHANNEL: str = "price_updates"
    # Шаблон ключа Redis для цены, например: price:BTC
    PRICE_KEY_TEMPLATE: str = "price:{symbol}"
    # Rate limiting WebSocket: максимум подключений за окно
    WS_RATE_LIMIT_MAX: int = 10
    # Rate limiting WebSocket: длительность окна (секунды)
    WS_RATE_LIMIT_WINDOW: int = 60
    # Максимальное число одновременных WebSocket-подключений
    MAX_WS_CONNECTIONS: int = Field(default=1000, gt=0)
    # Доверять заголовку X-Forwarded-For (только за доверенным прокси)
    TRUST_PROXY_HEADERS: bool = False


# Единый объект настроек для всего приложения
settings = Settings()
