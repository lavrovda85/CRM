# SPEC CRM/ERP Платформа

Отраслевая CRM/ERP система для компаний в сфере HVAC (вентиляции, кондиционирования и отопления) — покрывает полный цикл от заявки до завершённого монтажа. Включает встроенный движок рабочих процессов, складской учёт, учёт рабочего времени, управление тендерами, расчёт заработной платы и интеграцию с AI-агентами через Model Context Protocol (MCP).

## Технологический стек

| Слой              | Технология                       | Версия   |
|-------------------|----------------------------------|----------|
| Backend API       | FastAPI + Uvicorn                | 0.115+   |
| ORM / Миграции    | SQLAlchemy 2 (async) + Alembic  | 2.0.36+  |
| База данных       | PostgreSQL                       | 16       |
| Кеш / Брокер      | Redis                            | 7        |
| Очередь задач     | Celery (worker + beat)           | 5.4+     |
| Объектное хранилище| MinIO (S3-совместимый)           | latest   |
| Аутентификация / SSO | Keycloak (OIDC)               | 25.0     |
| MCP-сервер        | FastMCP (streamable HTTP)        | 3.1+     |
| Фронтенд          | Next.js + React + TypeScript     | 15       |
| Обратный прокси   | Nginx                            | alpine   |
| Сериализация      | orjson, Pydantic v2              | —        |
| Логирование       | structlog                        | 24.4+    |
| Языки             | Python 3.12, TypeScript 5        | —        |

## Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone <repo-url> && cd CRM

# 2. Скопировать и настроить переменные окружения
cp .env.example .env
# Отредактируйте .env — задайте пароли, секреты и client secret для Keycloak

# 3. Запустить все сервисы
docker compose up -d

# 4. Схема БД
#    Пока нет Alembic revision-файлов, dev поднимает таблицы через BACKEND_DEBUG; для пустого прода задайте
#    SCHEMA_BOOTSTRAP_ON_STARTUP=true один раз (см. .env.example), затем false.
#    Когда появятся миграции: docker compose exec backend alembic upgrade head

# 5. Открыть приложение
#    Фронтенд:        http://localhost:3000
#    Backend API:      http://localhost:8000/api/docs
#    Keycloak:         http://localhost:8080
#    MinIO-консоль:    http://localhost:9001
#    MCP-сервер:       http://localhost:8001/mcp
```

## Обзор архитектуры

Платформа построена на контейнеризированной архитектуре в стиле микросервисов, оркестрируемой через Docker Compose. Бэкенд предоставляет одновременно REST API (порт 8000) и MCP-сервер (порт 8001) из единой кодовой базы. Celery worker обрабатывает фоновые задачи (уведомления, амортизация, отчёты, мониторинг SLA), а Celery Beat управляет периодическими расписаниями.

Полное описание архитектуры в формате C4 см. в [docs/architecture/system-overview.md](docs/architecture/system-overview.md).

## Модули

| Модуль            | Описание                                                                  |
|-------------------|---------------------------------------------------------------------------|
| **Задачи**        | Управление задачами с движком рабочих процессов на основе шаблонов и чек-листами |
| **Шаблоны**       | Переиспользуемые шаблоны задач с настраиваемым воркфлоу, полями и SLA     |
| **Доски**         | Kanban/Scrum-доски для визуализации задач                                 |
| **Клиенты**       | Управление клиентами (физ. и юр. лица) с контактами                      |
| **Сделки**        | Воронка продаж с настраиваемыми стадиями                                 |
| **Тендеры**       | Отслеживание жизненного цикла тендеров/конкурсов с привязкой к задачам   |
| **Склад**         | Складской учёт: остатки, резервирование, движения, оповещения о низких остатках |
| **Оборудование**  | Учёт инструментов и оборудования с расчётом амортизации                  |
| **Учёт времени**  | Логирование рабочих часов (таймер и ручной ввод), разделение на оплачиваемые/неоплачиваемые |
| **Документы**     | Управление файлами с версионированием, хранение в MinIO                  |
| **Аналитика**     | Статистика дашборда, эффективность сотрудников, расчёт ЗП, аналитика тендеров |
| **Справочники**   | Динамические справочники (материалы, услуги, виды работ)                  |
| **Уведомления**   | Многоканальная доставка: Telegram, web push, email                       |

## MCP-сервер (интеграция с AI-агентами)

Платформа включает выделенный [Model Context Protocol](https://modelcontextprotocol.io/) сервер, который предоставляет все основные операции как MCP-инструменты. AI-агенты (Cursor, Claude Desktop, пользовательские агенты) могут подключаться и программно управлять платформой.

**Подключение:**

```json
{
  "mcpServers": {
    "spec-crm": {
      "url": "http://localhost:8001/mcp",
      "transport": "streamable-http"
    }
  }
}
```

**Доступные группы инструментов:** Управление задачами, Управление шаблонами, CRM (клиенты и сделки), Тендеры, Склад, Аналитика.

Полная документация MCP API: [docs/api/mcp-server.md](docs/api/mcp-server.md).

## Настройка окружения для разработки

### Предварительные требования

- Docker и Docker Compose v2
- Python 3.12+ (для локальной разработки бэкенда)
- Node.js 20+ (для локальной разработки фронтенда)

### Бэкенд (локально)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # или .venv\Scripts\activate на Windows
pip install -e ".[dev]"

# Запустить инфраструктурные сервисы
docker compose up -d postgres redis minio keycloak

# Выполнить миграции
alembic upgrade head

# Запустить API-сервер
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Запустить MCP-сервер (в отдельном терминале)
python -m app.mcp.server

# Запустить Celery worker (в отдельном терминале)
celery -A app.workers.celery_app worker --loglevel=info

# Запустить тесты
pytest --cov=app
```

### Фронтенд (локально)

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

### Линтинг и проверка типов

```bash
cd backend
ruff check .
mypy app/
```

## Переменные окружения

| Переменная                       | Описание                                    | Значение по умолчанию / Пример                     |
|----------------------------------|---------------------------------------------|---------------------------------------------------|
| `POSTGRES_DB`                    | Имя базы данных PostgreSQL                  | `hvac_crm`                                        |
| `POSTGRES_USER`                  | Пользователь PostgreSQL                     | `hvac_admin`                                      |
| `POSTGRES_PASSWORD`              | Пароль PostgreSQL                           | —                                                 |
| `DATABASE_URL`                   | Строка подключения (asyncpg)                | `postgresql+asyncpg://user:pass@postgres:5432/db` |
| `DATABASE_URL_SYNC`              | Синхронная строка подключения (для Alembic)  | `postgresql://user:pass@postgres:5432/db`         |
| `REDIS_URL`                      | URL подключения к Redis                     | `redis://redis:6379/0`                            |
| `CELERY_BROKER_URL`              | URL брокера Celery                          | `redis://redis:6379/1`                            |
| `CELERY_RESULT_BACKEND`          | URL хранилища результатов Celery            | `redis://redis:6379/2`                            |
| `MINIO_ENDPOINT`                 | S3-эндпоинт MinIO                           | `http://minio:9000`                               |
| `MINIO_ACCESS_KEY`               | Ключ доступа MinIO                          | `minioadmin`                                      |
| `MINIO_SECRET_KEY`               | Секретный ключ MinIO                        | —                                                 |
| `MINIO_BUCKET`                   | Бакет MinIO для документов                  | `hvac-documents`                                  |
| `KEYCLOAK_URL`                   | Базовый URL Keycloak                        | `http://keycloak:8080`                            |
| `KEYCLOAK_REALM`                 | Название realm в Keycloak                   | `hvac`                                            |
| `KEYCLOAK_CLIENT_ID`             | ID клиента бэкенда в Keycloak               | `hvac-backend`                                    |
| `KEYCLOAK_CLIENT_SECRET`         | Секрет клиента бэкенда                      | —                                                 |
| `SECRET_KEY`                     | Секретный ключ приложения                   | —                                                 |
| `CORS_ORIGINS`                   | Разрешённые CORS-источники (JSON-массив)    | `["http://localhost:3000"]`                       |
| `MCP_HOST`                       | Хост для привязки MCP-сервера               | `0.0.0.0`                                         |
| `MCP_PORT`                       | Порт MCP-сервера                            | `8001`                                            |
| `BACKEND_DEBUG`                  | Включить режим отладки                      | `false`                                           |
| `TELEGRAM_BOT_TOKEN`             | Токен Telegram-бота для уведомлений         | —                                                 |
| `NEXT_PUBLIC_API_URL`            | URL бэкенда для фронтенда                   | `http://localhost:8000/api/v1`                    |
| `NEXT_PUBLIC_WS_URL`             | URL WebSocket для фронтенда                 | `ws://localhost:8000/ws`                          |
| `NEXT_PUBLIC_KEYCLOAK_URL`       | URL Keycloak для фронтенда                  | `http://localhost:8080`                           |
| `NEXT_PUBLIC_KEYCLOAK_REALM`     | Realm Keycloak для фронтенда                | `hvac`                                            |
| `NEXT_PUBLIC_KEYCLOAK_CLIENT_ID` | ID клиента Keycloak для фронтенда           | `hvac-frontend`                                   |
| `NEXTAUTH_URL`                   | URL обратного вызова NextAuth               | `http://localhost:3000`                           |
| `NEXTAUTH_SECRET`                | Секретный ключ NextAuth                     | —                                                 |

Полный шаблон см. в [`.env.example`](.env.example).

## Структура проекта

```
CRM/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/              # Обработчики REST API маршрутов
│   │   │       ├── tasks.py
│   │   │       ├── templates.py
│   │   │       ├── boards.py
│   │   │       ├── clients.py
│   │   │       ├── deals.py
│   │   │       ├── tenders.py
│   │   │       ├── time_tracking.py
│   │   │       ├── warehouse.py
│   │   │       ├── depreciation.py
│   │   │       ├── documents.py
│   │   │       ├── references.py
│   │   │       └── analytics.py
│   │   ├── core/                # Конфигурация фреймворка
│   │   │   ├── config.py        # pydantic-settings
│   │   │   ├── database.py      # Фабрика AsyncSession
│   │   │   ├── dependencies.py  # FastAPI DI
│   │   │   ├── exceptions.py    # Иерархия пользовательских исключений
│   │   │   ├── pagination.py    # PaginatedResponse
│   │   │   └── security.py      # Keycloak JWT + RBAC
│   │   ├── mcp/                 # MCP-сервер (Model Context Protocol)
│   │   │   ├── server.py        # Экземпляр FastMCP
│   │   │   ├── tools/           # Определения MCP-инструментов
│   │   │   │   ├── task_tools.py
│   │   │   │   ├── template_tools.py
│   │   │   │   ├── crm_tools.py
│   │   │   │   ├── tender_tools.py
│   │   │   │   ├── warehouse_tools.py
│   │   │   │   └── analytics_tools.py
│   │   │   ├── prompts/         # Шаблоны промптов MCP
│   │   │   └── resources/       # Определения ресурсов MCP
│   │   ├── models/              # ORM-модели SQLAlchemy
│   │   │   ├── base.py          # BaseModel (UUID + временные метки)
│   │   │   ├── user.py
│   │   │   ├── client.py
│   │   │   ├── deal.py
│   │   │   ├── tender.py
│   │   │   ├── task_template.py
│   │   │   ├── task.py
│   │   │   ├── task_status.py
│   │   │   ├── board.py
│   │   │   ├── checklist.py
│   │   │   ├── time_entry.py
│   │   │   ├── warehouse_item.py
│   │   │   ├── warehouse_movement.py
│   │   │   ├── equipment.py
│   │   │   ├── depreciation_record.py
│   │   │   ├── document.py
│   │   │   ├── comment.py
│   │   │   ├── notification.py
│   │   │   └── reference.py
│   │   ├── schemas/             # Pydantic-схемы запросов/ответов
│   │   ├── services/            # Слой бизнес-логики
│   │   │   ├── workflow_engine.py
│   │   │   ├── task_service.py
│   │   │   ├── template_service.py
│   │   │   └── document_service.py
│   │   ├── workers/             # Асинхронные задачи Celery
│   │   │   ├── celery_app.py
│   │   │   ├── notifications.py
│   │   │   ├── depreciation_calc.py
│   │   │   ├── reports.py
│   │   │   └── sla_monitor.py
│   │   └── main.py              # Фабрика приложения FastAPI
│   ├── migrations/              # Миграции Alembic
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── Dockerfile               # Multi-stage: api, mcp, worker, beat
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/                 # Страницы Next.js App Router
│   │   ├── components/          # React-компоненты
│   │   ├── lib/                 # API-клиент, WebSocket, утилиты
│   │   ├── stores/              # Управление состоянием
│   │   └── types/               # TypeScript-определения типов
│   └── package.json
├── docker/
│   ├── keycloak/
│   │   └── hvac-realm.json      # Предварительно настроенный realm Keycloak
│   └── nginx/
│       └── nginx.conf           # Конфигурация обратного прокси
├── docs/
│   ├── architecture/
│   │   ├── system-overview.md
│   │   ├── database-schema.md
│   │   └── workflow-engine.md
│   ├── api/
│   │   ├── mcp-server.md
│   │   └── rest-api.md
│   └── adr/
│       └── 001-custom-task-engine.md
├── helm/                        # Helm-чарты для Kubernetes
├── docker-compose.yml
├── .env.example
└── .gitignore
```

## Лицензия

MIT
