"""Тесты для фонового воркера обновления цен."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.services.price_worker import price_update_worker


@pytest.mark.asyncio
async def test_price_update_worker_publishes_to_redis(monkeypatch):
    """Проверяем, что воркер сохраняет цены в Redis и публикует в Pub/Sub."""
    # Уменьшаем интервал обновления, чтобы тест выполнялся мгновенно
    monkeypatch.setattr(settings, "PRICE_UPDATE_INTERVAL", 0.05)

    # Мок pipeline: async with ... as pipe -> pipe с async execute()
    pipe = MagicMock()
    pipe.execute = AsyncMock()

    pipeline_cm = MagicMock()
    pipeline_cm.__aenter__ = AsyncMock(return_value=pipe)
    pipeline_cm.__aexit__ = AsyncMock(return_value=False)

    mock_redis = AsyncMock()
    mock_redis.pipeline = MagicMock(return_value=pipeline_cm)

    # Запускаем воркер как фоновую задачу
    task = asyncio.create_task(price_update_worker(mock_redis))

    # Ждем 0.15 сек — этого достаточно для одного цикла при интервале 0.05
    await asyncio.sleep(0.15)

    # Отменяем задачу
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Проверяем, что Redis вызывался
    assert pipe.execute.called, "Метод pipeline.execute() должен был вызваться"
    assert pipe.set.called, "Метод redis.set() должен был вызваться"
    assert pipe.publish.called, "Метод redis.publish() должен был вызваться"

    # Проверяем, что публикация была в правильный канал
    publish_calls = pipe.publish.call_args_list
    assert len(publish_calls) > 0, "Должен быть хотя бы один вызов publish"

    # Первый аргумент вызова publish — это канал
    channel = publish_calls[0][0][0]
    assert channel == "price_updates", f"Ожидался канал 'price_updates', получен '{channel}'"