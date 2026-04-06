# Документация MCP-сервера

Платформа SPEC CRM/ERP предоставляет сервер [Model Context Protocol](https://modelcontextprotocol.io/) (MCP), позволяющий AI-агентам программно управлять платформой — создавать задачи, проверять складские остатки, формировать отчёты и многое другое.

## Архитектура

MCP-сервер построен на [FastMCP](https://github.com/jlowin/fastmcp) v3.1+ и запускается как отдельный контейнер от REST API, разделяя общую кодовую базу Python, ORM-модели и бизнес-логику.

```
┌──────────────────┐         ┌──────────────────┐
│   AI-агент       │         │   MCP-сервер     │
│  (Cursor, Claude │◄─MCP──►│   :8001          │
│   Desktop и др.) │  HTTP   │  FastMCP 3.1+    │
└──────────────────┘         └──────┬───────────┘
                                    │
                         ┌──────────┼──────────┐
                         ▼          ▼          ▼
                    PostgreSQL    Redis      MinIO
```

**Транспорт:** Streamable HTTP (двунаправленный, сессионный)
**Порт:** 8001 (настраивается через переменную окружения `MCP_PORT`)
**Эндпоинт:** `http://<host>:8001/mcp`

## Инструкции по подключению

### Cursor IDE

Добавьте в конфигурацию MCP-серверов (`.cursor/mcp.json` или настройки Cursor):

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

### Claude Desktop

Добавьте в `claude_desktop_config.json`:

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

### Программное подключение (Python)

```python
from fastmcp import Client

async with Client("http://localhost:8001/mcp") as client:
    result = await client.call_tool("list_tasks", {"status": "in_progress"})
    print(result)
```

## Аутентификация

MCP-сервер валидирует JWT-токены Keycloak, передаваемые в метаданных вызова инструмента. AI-агенты должны получить валидный токен от Keycloak перед вызовом инструментов, требующих аутентификации.

**Получение токена:**

```bash
curl -X POST http://localhost:8080/realms/hvac/protocol/openid-connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=hvac-backend" \
  -d "client_secret=YOUR_CLIENT_SECRET"
```

Токен передаётся в метаданных вызова инструмента как `authorization: Bearer <token>`.

---

## Справочник инструментов

### Управление задачами

#### `create_task`

Создать новую задачу в системе SPEC CRM/ERP.

**Аргументы:**

| Имя            | Тип         | Обязательный | Описание                                                |
|----------------|-------------|-------------|----------------------------------------------------------|
| `title`        | `str`       | Да          | Название задачи                                          |
| `template_id`  | `str\|null` | Нет         | UUID шаблона задачи (наследует воркфлоу и чек-листы)    |
| `client_id`    | `str\|null` | Нет         | UUID клиента                                             |
| `assigned_to`  | `str\|null` | Нет         | UUID назначенного инженера                               |
| `custom_fields`| `dict\|null`| Нет         | Значения полей шаблона `{key: value}`                    |
| `priority`     | `str`       | Нет         | `low`, `medium` (по умолчанию), `high`, `critical`      |
| `due_date`     | `str\|null` | Нет         | Дата/время в формате ISO 8601 (напр. `2026-04-15T18:00:00Z`) |

**Возвращает:** `dict` — созданная задача с полями `id`, `title`, `status`, `priority`, `template_id`, `client_id`, `assigned_to`, `custom_fields`, `due_date`, `created_at`.

**Пример:**

```json
// Запрос
{
  "tool": "create_task",
  "arguments": {
    "title": "Монтаж кондиционера — Daikin FTXB35C",
    "template_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "client_id": "e5f6a7b8-c9d0-1234-abcd-ef5678901234",
    "assigned_to": "c9d0e1f2-a3b4-5678-abcd-ef9012345678",
    "priority": "high",
    "due_date": "2026-04-15T18:00:00Z"
  }
}

// Ответ
{
  "id": "f1234567-89ab-cdef-0123-456789abcdef",
  "title": "Монтаж кондиционера — Daikin FTXB35C",
  "status": "new",
  "priority": "high",
  "template_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "client_id": "e5f6a7b8-c9d0-1234-abcd-ef5678901234",
  "assigned_to": "c9d0e1f2-a3b4-5678-abcd-ef9012345678",
  "custom_fields": {},
  "due_date": "2026-04-15T18:00:00Z",
  "created_at": "2026-03-18T10:30:00Z"
}
```

---

#### `update_task`

Обновить поля существующей задачи. Нельзя изменить статус — используйте `transition_task`.

**Аргументы:**

| Имя      | Тип    | Обязательный | Описание                                                       |
|----------|--------|-------------|----------------------------------------------------------------|
| `task_id`| `str`  | Да          | UUID обновляемой задачи                                        |
| `fields` | `dict` | Да          | Обновляемые поля: `title`, `description`, `priority`, `assigned_to`, `due_date`, `custom_fields` |

**Возвращает:** `dict` — обновлённая задача с полями `id`, `updated_fields`, `updated_at` и значениями изменённых полей.

**Пример:**

```json
// Запрос
{
  "tool": "update_task",
  "arguments": {
    "task_id": "f1234567-89ab-cdef-0123-456789abcdef",
    "fields": {
      "priority": "critical",
      "assigned_to": "new-engineer-uuid"
    }
  }
}

// Ответ
{
  "id": "f1234567-89ab-cdef-0123-456789abcdef",
  "updated_fields": ["priority", "assigned_to"],
  "priority": "critical",
  "assigned_to": "new-engineer-uuid",
  "updated_at": "2026-03-18T11:00:00Z"
}
```

---

#### `transition_task`

Перевести задачу в новый статус воркфлоу. Проверяет переход на соответствие определению воркфлоу из шаблона и проверяет шлюзовые чек-листы.

**Аргументы:**

| Имя         | Тип   | Обязательный | Описание                                                      |
|-------------|-------|-------------|---------------------------------------------------------------|
| `task_id`   | `str` | Да          | UUID задачи                                                   |
| `to_status` | `str` | Да          | Целевой статус (должен быть допустимым переходом из текущего) |
| `reason`    | `str` | Нет         | Причина перехода для аудита (по умолчанию: `""`)              |

**Возвращает:** `dict` — `id`, `from_status`, `to_status`, `transitioned_at`, `reason`.

**Пример:**

```json
// Запрос
{
  "tool": "transition_task",
  "arguments": {
    "task_id": "f1234567-89ab-cdef-0123-456789abcdef",
    "to_status": "completed",
    "reason": "Все работы выполнены, подписанный акт загружен"
  }
}

// Ответ
{
  "id": "f1234567-89ab-cdef-0123-456789abcdef",
  "from_status": "review",
  "to_status": "completed",
  "transitioned_at": "2026-03-18T16:00:00Z",
  "reason": "Все работы выполнены, подписанный акт загружен"
}
```

---

#### `list_tasks`

Получить список задач с опциональными фильтрами. Результаты отсортированы по дате создания (по убыванию).

**Аргументы:**

| Имя           | Тип         | Обязательный | Описание                                |
|---------------|-------------|-------------|------------------------------------------|
| `status`      | `str\|null` | Нет         | Фильтр по статусу                       |
| `assigned_to` | `str\|null` | Нет         | Фильтр по UUID исполнителя              |
| `client_id`   | `str\|null` | Нет         | Фильтр по UUID клиента                  |
| `limit`       | `int`       | Нет         | Макс. результатов (по умолчанию: 50, макс: 200) |

**Возвращает:** `list[dict]` — список задач, каждая с полями `id`, `title`, `status`, `priority`, `assigned_to`, `client_id`, `due_date`, `created_at`.

---

#### `get_task_detail`

Получить полные сведения о конкретной задаче, включая связи (шаблон, клиент, исполнитель, чек-листы, документы, история статусов).

**Аргументы:**

| Имя       | Тип   | Обязательный | Описание       |
|-----------|-------|-------------|-----------------|
| `task_id` | `str` | Да          | UUID задачи     |

**Возвращает:** `dict` — полные данные задачи с вложенными объектами `template`, `client`, `assignee`, `checklists`, `documents`, `status_history`, `custom_fields`.

---

### Управление шаблонами

#### `list_templates`

Получить список доступных активных шаблонов задач с опциональной фильтрацией по категории.

**Аргументы:**

| Имя       | Тип         | Обязательный | Описание                                                          |
|-----------|-------------|-------------|-------------------------------------------------------------------|
| `category`| `str\|null` | Нет         | `installation`, `maintenance`, `repair`, `inspection`, `general`  |

**Возвращает:** `list[dict]` — список шаблонов с полями `id`, `name`, `category`, `description`, `required_fields`, `sla_config`, `is_active`.

---

#### `create_template`

Создать новый шаблон задачи с определениями воркфлоу и полей.

**Аргументы:**

| Имя                   | Тип              | Обязательный | Описание                                  |
|-----------------------|------------------|-------------|-------------------------------------------|
| `name`                | `str`            | Да          | Название шаблона                          |
| `category`            | `str`            | Да          | Категория шаблона                         |
| `workflow_definition` | `dict`           | Да          | Определение КА (`states` + `transitions`) |
| `required_fields`     | `list[dict]\|null`| Нет        | Определения полей                         |
| `sla_config`          | `dict\|null`     | Нет         | Параметры SLA                             |

**Возвращает:** `dict` — созданный шаблон с полями `id`, `name`, `category`, `workflow_definition`, `required_fields`, `sla_config`, `created_at`.

**Пример:**

```json
// Запрос
{
  "tool": "create_template",
  "arguments": {
    "name": "Техобслуживание кондиционера",
    "category": "maintenance",
    "workflow_definition": {
      "states": ["new", "scheduled", "in_progress", "completed"],
      "transitions": [
        {"from": "new", "to": "scheduled"},
        {"from": "scheduled", "to": "in_progress"},
        {"from": "in_progress", "to": "completed"}
      ]
    },
    "sla_config": {"max_duration_hours": 24, "warning_at_percent": 75}
  }
}

// Ответ
{
  "id": "tmpl-uuid-...",
  "name": "Техобслуживание кондиционера",
  "category": "maintenance",
  "workflow_definition": { ... },
  "required_fields": [],
  "sla_config": {"max_duration_hours": 24, "warning_at_percent": 75},
  "is_active": true,
  "created_at": "2026-03-18T10:00:00Z"
}
```

---

#### `instantiate_template`

Создать задачу из шаблона с наследованием воркфлоу, чек-листов и SLA.

**Аргументы:**

| Имя             | Тип         | Обязательный | Описание                                          |
|-----------------|-------------|-------------|---------------------------------------------------|
| `template_id`   | `str`       | Да          | UUID шаблона                                      |
| `client_id`     | `str`       | Да          | UUID клиента                                      |
| `title`         | `str`       | Да          | Название задачи                                   |
| `assigned_to`   | `str\|null` | Нет         | UUID назначенного инженера                        |
| `custom_fields` | `dict\|null`| Нет         | Значения полей шаблона (напр. `{area_sqm: 45}`)  |

**Возвращает:** `dict` — созданная задача с полями `id`, `title`, `status`, `template_id`, `client_id`, `assigned_to`, `custom_fields`, `checklists_created`, `sla_deadline`, `created_at`.

---

### CRM (Клиенты и сделки)

Создание клиентов, поиск и сделки выполняются в PostgreSQL (как REST `/api/v1/clients`, `/api/v1/deals`). Для `create_deal` без `stage_id` берётся первая стадия воронки по полю `order`.

#### `create_client`

Создать нового клиента (физическое или юридическое лицо).

**Аргументы:**

| Имя          | Тип         | Обязательный | Описание                                      |
|--------------|-------------|-------------|-----------------------------------------------|
| `name`       | `str`       | Да          | Имя клиента / название организации            |
| `client_type`| `str`       | Нет         | `individual` (по умолчанию) или `organization` |
| `address`    | `str\|null` | Нет         | Адрес                                         |
| `phone`      | `str\|null` | Нет         | Номер телефона                                |
| `email`      | `str\|null` | Нет         | Адрес электронной почты                       |

**Возвращает:** `dict` — `id`, `name`, `client_type`, `address`, `phone`, `email`, `created_at`.

---

#### `search_clients`

Поиск клиентов по имени, телефону, email или адресу (без учёта регистра).

**Аргументы:**

| Имя    | Тип   | Обязательный | Описание                   |
|--------|-------|-------------|----------------------------|
| `query`| `str` | Да          | Строка поискового запроса  |
| `limit`| `int` | Нет         | Макс. результатов (по умолчанию: 20) |

**Возвращает:** `list[dict]` — найденные клиенты с полями `id`, `name`, `client_type`, `phone`, `email`, `address`.

---

#### `create_deal`

Создать новую сделку в воронке продаж CRM.

**Аргументы:**

| Имя        | Тип         | Обязательный | Описание                                 |
|------------|-------------|-------------|------------------------------------------|
| `client_id`| `str`       | Да          | UUID клиента                             |
| `title`    | `str`       | Да          | Название сделки                          |
| `amount`   | `float`     | Нет         | Сумма сделки (по умолчанию: 0.0)        |
| `stage_id` | `str\|null` | Нет         | UUID стадии воронки (авто: первая)       |

**Возвращает:** `dict` — `id`, `client_id`, `title`, `amount`, `stage_id`, `stage_name`, `created_at`.

---

#### `move_deal`

Переместить сделку на другую стадию воронки.

**Аргументы:**

| Имя       | Тип   | Обязательный | Описание                     |
|-----------|-------|-------------|------------------------------|
| `deal_id` | `str` | Да          | UUID сделки                  |
| `stage_id`| `str` | Да          | UUID целевой стадии          |

**Возвращает:** `dict` — `id`, `title`, `from_stage`, `to_stage`, `moved_at`.

---

### Доски задач (boards)

| Инструмент      | Описание |
|-----------------|----------|
| `list_boards`   | Список неархивных досок (как `GET /api/v1/boards/`) |
| `create_board`  | Создать доску (владелец — MCP-сервисный пользователь `DEV_USER_ID`) |
| `get_board`     | Доска и задачи, сгруппированные по статусу (`GET /api/v1/boards/{id}`) |

### Чат компании

| Инструмент            | Описание |
|-----------------------|----------|
| `list_chat_rooms`     | Комнаты; при пустой БД создаётся комната «Общий чат» / `company` |
| `list_chat_messages`  | История сообщений по коду комнаты (вложения без presigned URL) |
| `send_chat_message`   | Текстовое сообщение от пользователя `DEV_USER_ID` (должен быть в `users`) |

### Управление тендерами

Реализация опирается на те же модели БД и правила, что и REST: универсальный чеклист при создании, граф переходов `app.services.tender.tender_pipeline`, строгая проверка задач при привязке.

#### `create_tender`

Создать тендер в БД со статусом `search`, с **универсальным чеклистом** (как `POST /api/v1/tenders/`).

**Аргументы:**

| Имя          | Тип           | Обязательный | Описание                         |
|--------------|---------------|-------------|----------------------------------|
| `title`      | `str`         | Да          | Название тендера (непустая строка) |
| `source`     | `str\|null`   | Нет         | Площадка-источник или заказчик   |
| `budget`     | `float\|null` | Нет         | Бюджет тендера                   |
| `deadline`   | `str\|null`   | Нет         | `YYYY-MM-DD` или ISO 8601 (дата подачи) |
| `assigned_to`| `str\|null`   | Нет         | UUID ответственного менеджера    |

**Возвращает:** `dict` — полный объект тендера в формате схемы `TenderResponse` (как REST), сериализованный в JSON.

---

#### `update_tender_status`

Изменить статус тендера с проверкой **допустимых переходов** (как `POST /api/v1/tenders/{id}/transition`). Недопустимый переход — ошибка домена (код `TENDER_TRANSITION_DENIED`).

**Аргументы:**

| Имя         | Тип         | Обязательный | Описание                                                             |
|-------------|-------------|-------------|----------------------------------------------------------------------|
| `tender_id` | `str`       | Да          | UUID тендера                                                         |
| `status`    | `str`       | Да          | `search`, `participation`, `won`, `lost`, `execution`, `completed`   |
| `reason`    | `str\|null` | Нет         | Причина перехода (добавляется в `notes` тендера, как у REST)         |

**Возвращает:** `dict` — `id`, `title`, `from_status`, `to_status`, `updated_at`.

---

#### `link_tasks_to_tender`

Привязать задачи к тендеру (`tasks.tender_id`). **Каждый** указанный `task_id` должен существовать; иначе `VALIDATION_ERROR` (как у `POST /api/v1/tenders/{id}/link-tasks`).

**Аргументы:**

| Имя         | Тип         | Обязательный | Описание                       |
|-------------|-------------|-------------|--------------------------------|
| `tender_id` | `str`       | Да          | UUID тендера                   |
| `task_ids`  | `list[str]` | Да          | Список UUID привязываемых задач |

**Возвращает:** `dict` — `tender_id`, `linked_count`, `task_ids`, `linked_at`.

---

#### `list_tenders`

Список тендеров из БД с опциональным фильтром по статусу. Сортировка: **`created_at` по убыванию** (как список в REST).

**Аргументы:**

| Имя      | Тип         | Обязательный | Описание                                |
|----------|-------------|-------------|------------------------------------------|
| `status` | `str\|null` | Нет         | Фильтр по статусу тендера               |
| `limit`  | `int`       | Нет         | Макс. результатов (по умолчанию: 50, макс: 200) |

**Возвращает:** `list[dict]` — элементы в формате `TenderResponse` (JSON).

---

### Складской учёт

Инструменты работают с реальной БД через `app.services.warehouse_operations` (те же правила, что `POST /api/v1/warehouse/movements` и резервы).

#### `check_stock`

Проверить складские остатки. Запрос по конкретной позиции или фильтрация по категории.

**Аргументы:**

| Имя       | Тип         | Обязательный | Описание                                                |
|-----------|-------------|-------------|----------------------------------------------------------|
| `item_id` | `str\|null` | Нет         | UUID конкретной складской позиции                        |
| `category`| `str\|null` | Нет         | `materials`, `tools`, `consumables`, `equipment`         |

**Возвращает:** `list[dict]` — позиции с полями `id`, `name`, `sku`, `category`, `unit`, `quantity`, `reserved_quantity`, `available`, `min_quantity`, `price`.

---

#### `reserve_materials`

Зарезервировать материалы со склада под конкретную задачу.

**Аргументы:**

| Имя      | Тип         | Обязательный | Описание                                                    |
|----------|-------------|-------------|--------------------------------------------------------------|
| `task_id`| `str`       | Да          | UUID задачи                                                  |
| `items`  | `list[dict]`| Да          | Позиции для резервирования: `[{item_id: "uuid", quantity: 5.0}]` |

**Возвращает:** `dict` — `task_id`, `reserved_items` (список `{item_id, quantity, status}`), `total_cost`, `reserved_at`.

**Пример:**

```json
// Запрос
{
  "tool": "reserve_materials",
  "arguments": {
    "task_id": "task-uuid-...",
    "items": [
      {"item_id": "copper-tube-uuid", "quantity": 10.0},
      {"item_id": "bracket-uuid", "quantity": 2.0}
    ]
  }
}

// Ответ
{
  "task_id": "task-uuid-...",
  "reserved_items": [
    {"item_id": "copper-tube-uuid", "quantity": 10.0, "status": "reserved"},
    {"item_id": "bracket-uuid", "quantity": 2.0, "status": "reserved"}
  ],
  "total_cost": 6200.0,
  "reserved_at": "2026-03-18T12:00:00Z"
}
```

---

#### `record_movement`

Зафиксировать складское движение (приход, расход, списание, перемещение, возврат).

**Аргументы:**

| Имя             | Тип         | Обязательный | Описание                                                    |
|-----------------|-------------|-------------|--------------------------------------------------------------|
| `item_id`       | `str`       | Да          | UUID складской позиции                                       |
| `movement_type` | `str`       | Да          | `intake`, `consumption`, `write_off`, `transfer`, `return`   |
| `quantity`      | `float`     | Да          | Количество (всегда положительное)                            |
| `task_id`       | `str\|null` | Нет         | UUID связанной задачи (для расхода)                          |
| `reason`        | `str\|null` | Нет         | Комментарий / причина                                        |

**Возвращает:** `dict` — `id`, `item_id`, `movement_type`, `quantity`, `task_id`, `reason`, `new_quantity`, `recorded_at`.

---

### Аналитика и отчётность

Агрегаты совпадают с REST `/api/v1/analytics/*` через модуль `app.services.analytics_read` (дашборд, тендеры, производительность, зарплата). Дополнительно в `get_dashboard_stats` учитываются движения склада за `period_days`.

#### `get_dashboard_stats`

Получить агрегированную статистику дашборда платформы.

**Аргументы:**

| Имя           | Тип   | Обязательный | Описание                            |
|---------------|-------|-------------|--------------------------------------|
| `period_days` | `int` | Нет         | Период в днях (по умолчанию: 30)    |

**Возвращает:** `dict` с разделами:
- `tasks` — `{total, new, in_progress, completed, overdue}`
- `deals` — `{total, total_amount, won_count, won_amount, conversion_rate}`
- `tenders` — `{total, active, won, lost, win_rate}`
- `warehouse` — `{low_stock_items, movements_count, total_consumption_cost}`
- `period_days`, `generated_at`

---

#### `get_employee_performance`

Получить показатели эффективности конкретного сотрудника.

**Аргументы:**

| Имя           | Тип   | Обязательный | Описание                            |
|---------------|-------|-------------|--------------------------------------|
| `user_id`     | `str` | Да          | UUID сотрудника                     |
| `period_days` | `int` | Нет         | Период в днях (по умолчанию: 30)    |

**Возвращает:** `dict` — `user_id`, `user_name`, `tasks` (assigned, completed, in_progress, overdue, avg_completion_hours, sla_compliance_rate), `time_entries` (total_hours, billable_hours), `period_days`.

---

#### `calculate_salary`

Рассчитать заработную плату сотрудника на основе `salary_config`, завершённых задач и отработанных часов.

**Аргументы:**

| Имя      | Тип   | Обязательный | Описание                   |
|----------|-------|-------------|----------------------------|
| `user_id`| `str` | Да          | UUID сотрудника            |
| `year`   | `int` | Да          | Год (напр. 2026)           |
| `month`  | `int` | Да          | Месяц (1–12)               |

**Возвращает:** `dict` — `user_id`, `user_name`, `year`, `month`, `base_salary`, `task_bonus`, `overtime_bonus`, `deductions`, `total`, `breakdown` (список компонентов расчёта).

**Пример:**

```json
// Запрос
{
  "tool": "calculate_salary",
  "arguments": {
    "user_id": "user-uuid-ivanov",
    "year": 2026,
    "month": 3
  }
}

// Ответ
{
  "user_id": "user-uuid-ivanov",
  "user_name": "Иванов Сергей",
  "year": 2026,
  "month": 3,
  "base_salary": 50000.0,
  "task_bonus": 18000.0,
  "overtime_bonus": 4500.0,
  "deductions": 0.0,
  "total": 72500.0,
  "breakdown": [
    {"type": "base", "amount": 50000.0, "description": "Базовый оклад"},
    {"type": "task_bonus", "amount": 18000.0, "description": "6 монтажей × 3000"},
    {"type": "overtime", "amount": 4500.0, "description": "12 сверхурочных часов × 375"}
  ]
}
```

---

#### `get_tender_analytics`

Получить аналитику по участию в тендерах и показателям успешности.

**Аргументы:**

| Имя           | Тип   | Обязательный | Описание                            |
|---------------|-------|-------------|--------------------------------------|
| `period_days` | `int` | Нет         | Период в днях (по умолчанию: 90)    |

**Возвращает:** `dict` — `funnel` (search, participation, won, lost, execution, completed), `financials` (total_budget, total_won_budget, avg_margin), `by_source` (статистика по источникам), `timing` (avg_days_to_decision, avg_execution_days).

---

## Сценарии использования

### Сценарий 1: AI-агент создаёт задачу из шаблона

AI-агенту необходимо создать новую задачу на монтаж кондиционера для клиента.

```
Агент: "Создай задачу на монтаж кондиционера для клиента Петрова"

1. Агент вызывает list_templates(category="installation")
   → Получает шаблон "Монтаж кондиционера" с id "tmpl-uuid-123"

2. Агент вызывает search_clients(query="Петров")
   → Получает клиента "Петров Иван" с id "client-uuid-456"

3. Агент вызывает instantiate_template(
     template_id="tmpl-uuid-123",
     client_id="client-uuid-456",
     title="Монтаж кондиционера — кв. Петров",
     assigned_to="engineer-uuid-789",
     custom_fields={"area_sqm": 45, "equipment_model": "Daikin FTXB35C"}
   )
   → Задача создана с чек-листами, установлен дедлайн SLA, status="new"
```

### Сценарий 2: AI-агент проверяет остатки и резервирует материалы

Перед началом монтажа AI-агент проверяет наличие и резервирует нужные материалы.

```
Агент: "Проверь, достаточно ли медной трубки и кронштейнов для монтажа"

1. Агент вызывает check_stock(category="materials")
   → Получает все материалы с количествами и доступным остатком

2. Агент определяет:
   - Медная трубка 6.35мм: доступно=45м, нужно=10м ✓
   - Настенный кронштейн: доступно=12шт, нужно=2шт ✓

3. Агент вызывает reserve_materials(
     task_id="task-uuid-...",
     items=[
       {"item_id": "copper-tube-uuid", "quantity": 10.0},
       {"item_id": "bracket-uuid", "quantity": 2.0}
     ]
   )
   → Материалы зарезервированы, рассчитана общая стоимость

4. Если остатков недостаточно, агент уведомляет пользователя:
   "Недостаточно медной трубки — доступно только 3м, нужно 10м.
    Создать заявку на закупку?"
```

### Сценарий 3: AI-агент формирует зарплатный отчёт

Бухгалтер просит AI-агента подготовить расчёт зарплаты для команды.

```
Агент: "Рассчитай зарплату инженера Иванова за март 2026"

1. Агент вызывает calculate_salary(
     user_id="user-uuid-ivanov",
     year=2026,
     month=3
   )
   → Возвращает: оклад=50000, бонус за задачи=18000 (6 монтажей),
     переработка=4500 (12 доп. часов), итого=72500

2. Агент вызывает get_employee_performance(
     user_id="user-uuid-ivanov",
     period_days=31
   )
   → Возвращает: 8 задач завершено, среднее 4.2 часа, 95% соответствие SLA

3. Агент представляет отчёт:
   "Иванов С. — март 2026:
    Базовый оклад:      50 000 ₽
    Бонус за задачи:     18 000 ₽ (6 монтажей × 3 000 ₽)
    Переработка:          4 500 ₽ (12 часов × 375 ₽)
    Итого:               72 500 ₽
    Эффективность: 8 задач, 95% соответствие SLA"
```
