# Презентация и проверка MCP / пайплайнов

Краткий чеклист перед демо: REST и MCP используют общие сервисы (`tender_service`, `warehouse_operations`, `analytics_read`, `tender_pipeline`).

## Переменные окружения

- **`DATABASE_URL`** — async PostgreSQL (`postgresql+asyncpg://...`). Обязательна для бэкенда и интеграционных тестов.
- **`SKIP_DB_INTEGRATION=1`** — пропустить интеграционный smoke-тест к БД (только локальные unit-тесты).

## Запуск тестов (backend)

Из каталога `backend/`:

```bash
# Все быстрые тесты + интеграция (интеграция skip, если БД недоступна)
python -m pytest tests/ -v

# Только unit (без маркера integration)
python -m pytest tests/ -v -m "not integration"

# Только интеграция с БД
python -m pytest tests/ -v -m integration
```

По умолчанию `tests/conftest.py` подставляет `DATABASE_URL` для импорта настроек; для реальной проверки укажите свой URL.

## MCP-сервер

```bash
# из backend, с тем же .env что и API
python -m app.mcp
```

Инструменты (основные группы):

| Область | Инструменты |
|--------|----------------|
| Задачи | `create_task`, `update_task`, `transition_task`, `list_tasks`, `get_task_detail` |
| Шаблоны / доски | шаблоны в `template_tools`; доски: `list_boards`, `create_board`, `get_board` |
| Тендеры | `create_tender`, `update_tender_status`, `link_tasks_to_tender`, `list_tenders` |
| Склад | `check_stock`, `reserve_materials`, `record_movement` |
| CRM | `create_client`, `search_clients`, `create_deal`, `move_deal` |
| Чат | `list_chat_rooms`, `list_chat_messages`, `send_chat_message` |
| Аналитика | `get_dashboard_stats`, `get_employee_performance`, `calculate_salary`, `get_tender_analytics` |

Сообщения чата от имени MCP идут от пользователя с id **`DEV_USER_ID`** (`00000000-0000-0000-0000-000000000001`); запись должна существовать в `users` (в debug API она создаётся автоматически).

## Ручной сценарий демо (ИИ)

1. `list_boards` → `create_board` → `create_task` (при необходимости указать `board_id`).
2. `create_tender` → `update_tender_status` с допустимым переходом (`search` → `participation`).
3. `check_stock` → `record_movement` (`intake` / `consumption`) при наличии позиций в БД.
4. `list_chat_rooms` → `send_chat_message` → `list_chat_messages`.
5. `get_dashboard_stats` для сводки.

При ошибках домена смотрите коды `TENDER_TRANSITION_DENIED`, `VALIDATION_ERROR`, `NOT_FOUND`, `INSUFFICIENT_STOCK` в ответах API / обработчике MCP.

## Отчёт о тестах

Актуальный прогон pytest и бэклог исправлений: **[TEST_REPORT.md](TEST_REPORT.md)** (сырой лог: [`_pytest_last_run.txt`](_pytest_last_run.txt)).

**CI:** GitHub Actions — [`.github/workflows/backend-tests.yml`](../../.github/workflows/backend-tests.yml), описание — [`docs/development/ci-backend.md`](../development/ci-backend.md).
