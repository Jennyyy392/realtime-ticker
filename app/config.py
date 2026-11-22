"""Настройки приложения RealTimeTicker.

Значения читаются из переменных окружения, а также из файла .env
(если он существует в корне проекта).
"""

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


# Единый объект настроек для всего приложения
settings = Settings()
