"""Тесты для WebSocket эндпоинта и базовой работы приложения."""

import asyncio
import json
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi import WebSocketException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.api.v1.dependencies import check_rate_limit
from app.services.broadcaster import broadcaster


def _stub_broadcaster(monkeypatch, seed: tuple = ()) -> None:
    """Подменяем методы broadcaster, чтобы не было реального Redis PubSub."""

    def fake_get_queue(*args, **kwargs):
        # Очередь создаётся внутри event loop TestClient, а не в синхронном теле теста.
        queue: asyncio.Queue = asyncio.Queue()
        for item in seed:
            queue.put_nowait(item)
        return queue

    def fake_noop(*args, **kwargs):
        return None

    for name in ("connect", "subscribe"):
        if hasattr(broadcaster, name):
            monkeypatch.setattr(broadcaster, name, fake_get_queue)

    for name in ("disconnect", "unsubscribe"):
        if hasattr(broadcaster, name):
            monkeypatch.setattr(broadcaster, name, fake_noop)


@pytest.fixture(autouse=True)
def mock_dependencies(monkeypatch):
    """Изоляция от Redis и подмена зависимости rate limit."""
    pipe = MagicMock()
    pipe.execute = AsyncMock()
    pipeline_cm = MagicMock()
    pipeline_cm.__aenter__ = AsyncMock(return_value=pipe)
    pipeline_cm.__aexit__ = AsyncMock(return_value=False)

    fake_redis = AsyncMock()
    fake_redis.ping = AsyncMock(return_value=True)
    fake_redis.pipeline = MagicMock(return_value=pipeline_cm)

    monkeypatch.setattr(broadcaster, "_redis", fake_redis)
    monkeypatch.setattr(broadcaster, "start", AsyncMock())
    monkeypatch.setattr(broadcaster, "stop", AsyncMock())

    with patch("app.main.redis_client", fake_redis), \
            patch("app.redis_client.redis_client", fake_redis):
        app.dependency_overrides[check_rate_limit] = lambda: None
        try:
            yield
        finally:
            app.dependency_overrides.clear()


def test_health_endpoint_works(mock_dependencies):
    """Проверяем, что health endpoint работает и возвращает статус ok."""
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"


def test_websocket_route_exists(mock_dependencies, monkeypatch):
    """WebSocket эндпоинт принимает соединение без реального Redis."""
    _stub_broadcaster(monkeypatch)

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/prices") as websocket:
            assert websocket is not None
            websocket.close()


def test_websocket_receives_price_update_and_closes(mock_dependencies, monkeypatch):
    """Заранее положенное в очередь сообщение приходит клиенту как JSON."""
    payload = {"symbol": "BTC", "price": 65000.0}
    _stub_broadcaster(monkeypatch, seed=(json.dumps(payload),))

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/prices") as websocket:
            data = websocket.receive_json()
            assert data["symbol"] == "BTC"
            websocket.close()


def test_websocket_rate_limit_exceeded(mock_dependencies):
    """При отказе check_rate_limit соединение не устанавливается."""

    def deny_connection() -> None:
        raise WebSocketException(code=1008, reason="rate limit exceeded")

    app.dependency_overrides[check_rate_limit] = deny_connection

    with TestClient(app) as client:
        with pytest.raises((WebSocketDisconnect, WebSocketException)):
            with client.websocket_connect("/api/v1/ws/prices"):
                pass