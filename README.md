# RealTimeTicker

Сервис для отслеживания цен криптовалют в реальном времени.

Стек: **FastAPI** + **Redis** + **Docker Compose**. Всё, что связано с вводом-выводом,
реализовано асинхронно (`async/await`), включая работу с Redis через `redis.asyncio`.

## Структура проекта

```
realtime-ticker/
├── app/
│   ├── __init__.py
│   ├── main.py                  # Точка входа FastAPI, lifespan с подключением к Redis
│   ├── config.py                # Настройки (pydantic-settings)
│   ├── redis_client.py          # Асинхронный клиент Redis и dependency get_redis
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py            # Сборка маршрутов v1
│   │       ├── dependencies.py      # Rate limiting WebSocket-подключений
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── health.py        # GET /api/v1/health
│   │           ├── prices.py        # GET /api/v1/prices/{symbol}
│   │           └── websocket.py     # WS /api/v1/ws/prices
│   ├── core/
│   │   ├── __init__.py
│   │   ├── logger.py            # structlog-логирование
│   │   └── exceptions.py        # Глобальный обработчик исключений
│   └── services/
│       ├── __init__.py
│       ├── price_service.py     # Сервисный слой для работы с ценами
│       ├── price_worker.py      # Фоновый воркер: генерация цен, запись и публикация в Redis
│       └── broadcaster.py       # Одна подписка Redis Pub/Sub на процесс, рассылка в очереди клиентов
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── tests/
│   ├── __init__.py
│   ├── test_price_worker.py     # Тесты фонового воркера цен
│   └── test_websocket.py        # Тесты health и WebSocket-эндпоинта
├── requirements.txt
├── .env
├── .gitignore
├── pytest.ini
└── README.md
```

## Запуск

### Через Docker Compose (рекомендуется)

```bash
docker compose -f docker/docker-compose.yml up --build
```

После запуска:
- API: http://localhost:8001
- Swagger UI: http://localhost:8001/docs
- Проверка: http://localhost:8001/api/v1/health
- WebSocket: ws://localhost:8001/api/v1/ws/prices
- Redis доступен на `localhost:6379`

### Локально (без Docker)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# Отдельно запустить Redis (например, через Docker)
docker run -p 6379:6379 redis:7-alpine

uvicorn app.main:app --reload
```

## API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/v1/health` | Проверка работоспособности API и Redis |
| GET | `/api/v1/prices/{symbol}` | Текущая цена монеты из кэша Redis |
| WS | `/api/v1/ws/prices` | Поток обновлений цен в реальном времени |

Примеры запросов (порт `8001` — внешний порт из `docker/docker-compose.yml`):

```bash
curl http://localhost:8001/api/v1/health
curl http://localhost:8001/api/v1/prices/BTC
```

Swagger UI: http://localhost:8001/docs

### WebSocket: `ws://localhost:8001/api/v1/ws/prices`

Эндпоинт не создаёт отдельную подписку Redis на каждого клиента: все соединения
обслуживает один процесс-`PriceBroadcaster`, который читает канал `price_updates`
и раскладывает сообщения в индивидуальные `asyncio.Queue`. Медленный клиент
не тормозит остальных — переполняется только его собственная очередь.

Подключение ограничено rate limit'ом (по умолчанию 10 подключений за 60 секунд
с одного IP; настраивается через `WS_RATE_LIMIT_MAX` и `WS_RATE_LIMIT_WINDOW`).
При превышении лимита соединение отклоняется с кодом 1008 (Policy Violation).

В канал публикуются JSON-сообщения вида:

```json
{"symbol": "BTC", "price": 65432.1}
```

Пример подключения:

```python
import asyncio
import json

import websockets


async def main() -> None:
    async with websockets.connect("ws://localhost:8001/api/v1/ws/prices") as ws:
        async for raw in ws:
            print(json.loads(raw))


asyncio.run(main())
```

## Переменные окружения (.env)

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `APP_NAME` | `RealTimeTicker` | Название сервиса |
| `DEBUG` | `True` | Режим отладки (влияет на формат логов и debug-режим FastAPI) |
| `API_V1_PREFIX` | `/api/v1` | Префикс маршрутов v1 |
| `REDIS_HOST` | `localhost` | Хост Redis |
| `REDIS_PORT` | `6379` | Порт Redis |
| `REDIS_DB` | `0` | Номер базы Redis |
| `PRICE_UPDATE_INTERVAL` | `3.0` | Интервал обновления цен воркером, секунды |
| `TRACKED_SYMBOLS` | `["BTC", "ETH", "SOL", "TON"]` | Список отслеживаемых символов (JSON-массив) |
| `PRICE_UPDATES_CHANNEL` | `price_updates` | Канал Redis Pub/Sub с обновлениями цен |
| `PRICE_KEY_TEMPLATE` | `price:{symbol}` | Шаблон ключа Redis для цены |
| `WS_RATE_LIMIT_MAX` | `10` | Максимум WebSocket-подключений за окно |
| `WS_RATE_LIMIT_WINDOW` | `60` | Длительность окна rate limit, секунды |

## Тесты

```bash
pytest
```

## Линтинг

```bash
ruff check .
```
