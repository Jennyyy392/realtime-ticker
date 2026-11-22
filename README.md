# RealTimeTicker

Сервис для отслеживания цен криптовалют в реальном времени.

Стек: **FastAPI** + **Redis** + **Docker Compose**. Всё, что связано с вводом-выводом,
реализовано асинхронно (`async/await`), включая работу с Redis через `redis.asyncio`.

## Структура проекта

```
realtime-ticker/
├── app/
│   ├── main.py                  # Точка входа FastAPI, lifespan с подключением к Redis
│   ├── config.py                # Настройки (pydantic-settings)
│   ├── redis_client.py          # Асинхронный клиент Redis и dependency get_redis
│   ├── api/v1/
│   │   ├── router.py            # Сборка маршрутов v1
│   │   └── endpoints/
│   │       ├── health.py        # GET /api/v1/health
│   │       └── prices.py        # GET /api/v1/prices/{symbol}
│   ├── core/
│   │   ├── logger.py            # structlog-логирование
│   │   └── exceptions.py        # Глобальный обработчик исключений
│   └── services/
│       └── price_service.py     # Сервисный слой для работы с ценами
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── tests/
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
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Проверка: http://localhost:8000/api/v1/health
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

## Переменные окружения (.env)

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `REDIS_HOST` | `localhost` | Хост Redis |
| `REDIS_PORT` | `6379` | Порт Redis |
| `REDIS_DB` | `0` | Номер базы Redis |
| `DEBUG` | `True` | Режим отладки (влияет на формат логов) |

## Тесты

```bash
pytest
```

## Линтинг

```bash
ruff check .
```
