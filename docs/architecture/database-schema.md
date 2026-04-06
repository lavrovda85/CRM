# Схема базы данных

PostgreSQL 16 является основным хранилищем данных. Все таблицы имеют общий паттерн: UUID первичный ключ (`id`), временные метки `created_at` и `updated_at`, предоставляемые миксином `BaseModel`.

## Обзор связей между сущностями

```
┌────────────────┐       ┌───────────────────┐       ┌────────────────┐
│     Users      │       │   TaskTemplates    │       │    Clients     │
│                │       │                   │       │                │
│ keycloak_id    │       │ workflow_definition│       │ client_type    │
│ email          │       │ required_fields    │       │ address        │
│ role           │       │ sla_config         │       │ phone, email   │
│ salary_config  │       │ auto_warehouse     │       │ inn            │
└───────┬────────┘       └────────┬──────────┘       └───────┬────────┘
        │                         │                          │
        │  ┌──────────────────────┼──────────────────────────┘
        │  │                      │
        ▼  ▼                      ▼
┌────────────────────────────────────────┐
│                 Tasks                  │
│                                        │
│ template_id → TaskTemplates            │
│ client_id   → Clients                  │
│ deal_id     → Deals                    │
│ tender_id   → Tenders                  │
│ board_id    → Boards                   │
│ assigned_to → Users                    │
│ created_by  → Users                    │
│ status, priority, custom_fields (JSONB)│
└──┬──────┬──────┬──────┬──────┬─────────┘
   │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼
Checklists TimeEntries Documents Comments WarehouseReservations
```

## Сущности

### users

| Колонка           | Тип          | Nullable | Описание                                     |
|-------------------|-------------|----------|----------------------------------------------|
| `id`              | UUID PK     | Нет      | Автоматически сгенерированный UUID           |
| `keycloak_id`     | VARCHAR(255)| Нет      | Идентификатор субъекта Keycloak (уникальный, индексированный) |
| `email`           | VARCHAR(255)| Нет      | Уникальный, индексированный                  |
| `full_name`       | VARCHAR(255)| Нет      | Отображаемое имя                             |
| `phone`           | VARCHAR(50) | Да       | Номер телефона                               |
| `role`            | VARCHAR(50) | Нет      | Основная роль (admin, manager, engineer и др.) |
| `position`        | VARCHAR(255)| Да       | Должность                                    |
| `telegram_chat_id`| VARCHAR(100)| Да       | ID чата Telegram для уведомлений             |
| `salary_config`   | JSONB       | Нет      | Параметры расчёта заработной платы (см. ниже) |
| `is_active`       | BOOLEAN     | Нет      | Флаг мягкого удаления                        |
| `notes`           | TEXT        | Да       | Внутренние заметки                           |
| `created_at`      | TIMESTAMPTZ | Нет      | server_default: now()                        |
| `updated_at`      | TIMESTAMPTZ | Нет      | server_default: now(), onupdate: now()       |

**Индексы:** `keycloak_id` (уникальный), `email` (уникальный)

**Связи:** → assigned_tasks (Task), → time_entries (TimeEntry), → comments (Comment)

---

### clients

| Колонка        | Тип          | Nullable | Описание                                 |
|----------------|-------------|----------|------------------------------------------|
| `id`           | UUID PK     | Нет      | Автоматически сгенерированный UUID       |
| `name`         | VARCHAR(500)| Нет      | Имя клиента / название организации (индексировано) |
| `client_type`  | VARCHAR(50) | Нет      | `individual` или `organization`          |
| `address`      | TEXT        | Да       | Основной адрес                           |
| `coordinates`  | JSONB       | Да       | GPS-координаты `{lat, lng}`              |
| `phone`        | VARCHAR(50) | Да       | Основной телефон                         |
| `email`        | VARCHAR(255)| Да       | Адрес электронной почты                  |
| `inn`          | VARCHAR(20) | Да       | ИНН (для организаций)                    |
| `metadata`     | JSONB       | Нет      | Расширяемые метаданные                   |
| `notes`        | TEXT        | Да       | Заметки менеджера                        |
| `created_at`   | TIMESTAMPTZ | Нет      |                                          |
| `updated_at`   | TIMESTAMPTZ | Нет      |                                          |

**Индексы:** `name`

**Связи:** → contacts (ClientContact), → deals (Deal), → tasks (Task)

---

### client_contacts

| Колонка       | Тип          | Nullable | Описание                           |
|--------------|-------------|----------|------------------------------------|
| `id`          | UUID PK     | Нет      |                                    |
| `client_id`   | UUID FK     | Нет      | → clients.id (CASCADE)            |
| `full_name`   | VARCHAR(255)| Нет      | ФИО контактного лица               |
| `position`    | VARCHAR(255)| Да       | Должность                          |
| `phone`       | VARCHAR(50) | Да       |                                    |
| `email`       | VARCHAR(255)| Да       |                                    |
| `is_primary`  | BOOLEAN     | Нет      | Флаг основного контакта            |
| `created_at`  | TIMESTAMPTZ | Нет      |                                    |
| `updated_at`  | TIMESTAMPTZ | Нет      |                                    |

**Индексы:** `client_id`

---

### deal_stages

| Колонка     | Тип          | Nullable | Описание                              |
|-------------|-------------|----------|---------------------------------------|
| `id`        | UUID PK     | Нет      |                                       |
| `name`      | VARCHAR(100)| Нет      | Название стадии                       |
| `order`     | INTEGER     | Нет      | Позиция в воронке                     |
| `color`     | VARCHAR(7)  | Нет      | HEX-цвет для UI (по умолчанию `#6366f1`) |
| `is_won`    | BOOLEAN     | Нет      | Отмечает стадию «выиграно»            |
| `is_lost`   | BOOLEAN     | Нет      | Отмечает стадию «проиграно»           |
| `created_at`| TIMESTAMPTZ | Нет      |                                       |
| `updated_at`| TIMESTAMPTZ | Нет      |                                       |

---

### deals

| Колонка          | Тип          | Nullable | Описание                            |
|------------------|-------------|----------|-------------------------------------|
| `id`             | UUID PK     | Нет      |                                     |
| `client_id`      | UUID FK     | Нет      | → clients.id (индексировано)       |
| `title`          | VARCHAR(500)| Нет      | Название сделки                     |
| `description`    | TEXT        | Да       |                                     |
| `amount`         | NUMERIC(15,2)| Нет     | Сумма сделки                        |
| `stage_id`       | UUID FK     | Нет      | → deal_stages.id (индексировано)   |
| `assigned_to`    | UUID FK     | Да       | → users.id (индексировано)         |
| `expected_close` | DATE        | Да       | Ожидаемая дата закрытия             |
| `source`         | VARCHAR(100)| Да       | Источник лида                       |
| `created_at`     | TIMESTAMPTZ | Нет      |                                     |
| `updated_at`     | TIMESTAMPTZ | Нет      |                                     |

**Индексы:** `client_id`, `stage_id`, `assigned_to`

---

### tenders

| Колонка              | Тип          | Nullable | Описание                                 |
|----------------------|-------------|----------|------------------------------------------|
| `id`                 | UUID PK     | Нет      |                                          |
| `title`              | VARCHAR(500)| Нет      | Название тендера (индексировано)         |
| `description`        | TEXT        | Да       |                                          |
| `source`             | VARCHAR(255)| Да       | Площадка-источник / заказчик             |
| `budget`             | NUMERIC(15,2)| Да     | Бюджет тендера                           |
| `our_price`          | NUMERIC(15,2)| Да     | Наша ценовая заявка                      |
| `status`             | VARCHAR(50) | Нет      | Состояние жизненного цикла (индексировано) |
| `deadline`           | DATE        | Да       | Крайний срок подачи заявки               |
| `execution_deadline` | DATE        | Да       | Крайний срок исполнения                  |
| `assigned_to`        | UUID FK     | Да       | → users.id (индексировано)              |
| `requirements`       | JSONB       | Нет      | Требования тендера                       |
| `documents_url`      | VARCHAR(1000)| Да     | Ссылка на внешние документы              |
| `notes`              | TEXT        | Да       |                                          |
| `created_at`         | TIMESTAMPTZ | Нет      |                                          |
| `updated_at`         | TIMESTAMPTZ | Нет      |                                          |

**Допустимые значения status:** `search`, `participation`, `won`, `lost`, `execution`, `completed`

**Индексы:** `title`, `status`, `assigned_to`

---

### task_templates

| Колонка                | Тип          | Nullable | Описание                                        |
|------------------------|-------------|----------|-------------------------------------------------|
| `id`                   | UUID PK     | Нет      |                                                 |
| `name`                 | VARCHAR(255)| Нет      | Название шаблона (индексировано)                |
| `category`             | VARCHAR(100)| Нет      | Категория (индексировано)                       |
| `description`          | TEXT        | Да       |                                                 |
| `workflow_definition`  | JSONB       | Нет      | Определение конечного автомата (см. раздел JSONB ниже) |
| `required_fields`      | JSONB       | Нет      | Определения полей                               |
| `sla_config`           | JSONB       | Нет      | Параметры SLA                                   |
| `auto_warehouse`       | JSONB       | Нет      | Правила автоматического списания                |
| `required_documents`   | JSONB       | Нет      | Требования к документам по стадиям              |
| `is_active`            | BOOLEAN     | Нет      | Флаг активности шаблона                         |
| `created_at`           | TIMESTAMPTZ | Нет      |                                                 |
| `updated_at`           | TIMESTAMPTZ | Нет      |                                                 |

**Допустимые значения category:** `installation`, `maintenance`, `repair`, `inspection`, `general`

**Индексы:** `name`, `category`

**Связи:** → stages (TemplateStage), → checklists (TemplateChecklist), → fields (TemplateField), → tasks (Task)

---

### template_stages

| Колонка        | Тип          | Nullable | Описание                              |
|----------------|-------------|----------|---------------------------------------|
| `id`           | UUID PK     | Нет      |                                       |
| `template_id`  | UUID FK     | Нет      | → task_templates.id (CASCADE)        |
| `name`         | VARCHAR(255)| Нет      | Отображаемое название стадии          |
| `status_id`    | VARCHAR(100)| Нет      | Соответствует состоянию в workflow_definition |
| `order`        | INTEGER     | Нет      | Порядок отображения                   |
| `description`  | TEXT        | Да       |                                       |

**Индексы:** `template_id`

---

### template_checklists

| Колонка           | Тип          | Nullable | Описание                                      |
|-------------------|-------------|----------|-----------------------------------------------|
| `id`              | UUID PK     | Нет      |                                               |
| `template_id`     | UUID FK     | Нет      | → task_templates.id (CASCADE)                |
| `checklist_id`    | VARCHAR(100)| Нет      | Уникальный ключ внутри шаблона               |
| `title`           | VARCHAR(255)| Нет      | Отображаемое название чек-листа              |
| `gate_transition` | VARCHAR(200)| Да       | Блокируемый переход (`from->to`)             |
| `items`           | JSONB       | Нет      | Массив определений элементов                 |

**Индексы:** `template_id`

---

### template_fields

| Колонка         | Тип          | Nullable | Описание                                        |
|----------------|-------------|----------|-------------------------------------------------|
| `id`            | UUID PK     | Нет      |                                                 |
| `template_id`   | UUID FK     | Нет      | → task_templates.id (CASCADE)                  |
| `key`           | VARCHAR(100)| Нет      | Машиночитаемое имя поля                        |
| `label`         | VARCHAR(255)| Нет      | Человекочитаемая метка                         |
| `field_type`    | VARCHAR(50) | Нет      | string, integer, decimal, enum, reference, address, date |
| `is_required`   | BOOLEAN     | Нет      | Флаг обязательности                            |
| `options`       | JSONB       | Да       | Варианты для типа enum                         |
| `ref_table`     | VARCHAR(100)| Да       | Справочная таблица для типа reference          |
| `default_value` | VARCHAR(500)| Да       | Значение по умолчанию                          |
| `order`         | INTEGER     | Нет      | Порядок отображения                            |

**Индексы:** `template_id`

---

### tasks

| Колонка         | Тип          | Nullable | Описание                                 |
|----------------|-------------|----------|------------------------------------------|
| `id`            | UUID PK     | Нет      |                                          |
| `template_id`   | UUID FK     | Да       | → task_templates.id (индексировано)     |
| `board_id`      | UUID FK     | Да       | → boards.id (индексировано)             |
| `client_id`     | UUID FK     | Да       | → clients.id (индексировано)            |
| `deal_id`       | UUID FK     | Да       | → deals.id (индексировано)              |
| `tender_id`     | UUID FK     | Да       | → tenders.id (индексировано)            |
| `assigned_to`   | UUID FK     | Да       | → users.id (индексировано)              |
| `created_by`    | UUID FK     | Да       | → users.id                              |
| `title`         | VARCHAR(500)| Нет      | Название задачи (индексировано)          |
| `description`   | TEXT        | Да       |                                          |
| `status`        | VARCHAR(100)| Нет      | Текущее состояние воркфлоу (индексировано) |
| `priority`      | VARCHAR(20) | Нет      | low, medium, high, critical (индексировано) |
| `custom_fields` | JSONB       | Нет      | Значения полей шаблона (см. ниже)        |
| `due_date`      | TIMESTAMPTZ | Да       | Крайний срок                             |
| `started_at`    | TIMESTAMPTZ | Да       | Фактическое время начала                 |
| `completed_at`  | TIMESTAMPTZ | Да       | Фактическое время завершения             |
| `sla_deadline`  | TIMESTAMPTZ | Да       | Крайний срок SLA (рассчитывается автоматически) |
| `created_at`    | TIMESTAMPTZ | Нет      |                                          |
| `updated_at`    | TIMESTAMPTZ | Нет      |                                          |

**Индексы:** `template_id`, `board_id`, `client_id`, `deal_id`, `tender_id`, `assigned_to`, `title`, `status`, `priority`

**Связи:** → status_history, checklists, time_entries, documents, comments, reservations, equipment_usage

---

### task_status_history

| Колонка           | Тип          | Nullable | Описание                                 |
|-------------------|-------------|----------|------------------------------------------|
| `id`              | UUID PK     | Нет      |                                          |
| `task_id`         | UUID FK     | Нет      | → tasks.id (CASCADE, индексировано)     |
| `from_status`     | VARCHAR(100)| Нет      | Предыдущий статус                        |
| `to_status`       | VARCHAR(100)| Нет      | Новый статус                             |
| `changed_by`      | UUID FK     | Нет      | → users.id                              |
| `reason`          | TEXT        | Да       | Комментарий к переходу                   |
| `transition_data` | JSONB       | Нет      | Дополнительные метаданные перехода       |
| `created_at`      | TIMESTAMPTZ | Нет      |                                          |
| `updated_at`      | TIMESTAMPTZ | Нет      |                                          |

**Индексы:** `task_id`

---

### boards

| Колонка        | Тип          | Nullable | Описание                              |
|----------------|-------------|----------|---------------------------------------|
| `id`           | UUID PK     | Нет      |                                       |
| `name`         | VARCHAR(255)| Нет      | Название доски                        |
| `description`  | TEXT        | Да       |                                       |
| `board_type`   | VARCHAR(50) | Нет      | kanban, scrum, tender                 |
| `owner_id`     | UUID FK     | Да       | → users.id                           |
| `columns`      | JSONB       | Нет      | Определения колонок (маппинг статусов) |
| `is_archived`  | BOOLEAN     | Нет      | Флаг архивации                        |
| `created_at`   | TIMESTAMPTZ | Нет      |                                       |
| `updated_at`   | TIMESTAMPTZ | Нет      |                                       |

---

### checklists

| Колонка           | Тип          | Nullable | Описание                                      |
|-------------------|-------------|----------|-----------------------------------------------|
| `id`              | UUID PK     | Нет      |                                               |
| `task_id`         | UUID FK     | Нет      | → tasks.id (CASCADE, индексировано)          |
| `title`           | VARCHAR(255)| Нет      | Название чек-листа                            |
| `gate_transition` | VARCHAR(200)| Да       | Ключ блокируемого перехода (`from->to`)       |
| `is_completed`    | BOOLEAN     | Нет      | Все элементы выполнены                        |
| `created_at`      | TIMESTAMPTZ | Нет      |                                               |
| `updated_at`      | TIMESTAMPTZ | Нет      |                                               |

**Индексы:** `task_id`

---

### checklist_items

| Колонка         | Тип          | Nullable | Описание                             |
|----------------|-------------|----------|--------------------------------------|
| `id`            | UUID PK     | Нет      |                                      |
| `checklist_id`  | UUID FK     | Нет      | → checklists.id (CASCADE, индексировано) |
| `title`         | VARCHAR(500)| Нет      | Текст элемента                       |
| `is_completed`  | BOOLEAN     | Нет      | Флаг выполнения                      |
| `completed_by`  | UUID FK     | Да       | → users.id                          |
| `completed_at`  | TIMESTAMPTZ | Да       | Временная метка выполнения           |
| `order`         | INTEGER     | Нет      | Порядок отображения                  |
| `created_at`    | TIMESTAMPTZ | Нет      |                                      |
| `updated_at`    | TIMESTAMPTZ | Нет      |                                      |

**Индексы:** `checklist_id`

---

### time_entries

| Колонка            | Тип          | Nullable | Описание                            |
|--------------------|-------------|----------|-------------------------------------|
| `id`               | UUID PK     | Нет      |                                     |
| `task_id`          | UUID FK     | Нет      | → tasks.id (CASCADE, индексировано) |
| `user_id`          | UUID FK     | Нет      | → users.id (индексировано)         |
| `started_at`       | TIMESTAMPTZ | Да       | Начало таймера                      |
| `ended_at`         | TIMESTAMPTZ | Да       | Конец таймера                       |
| `duration_minutes` | INTEGER     | Нет      | Длительность (рассчитанная или введённая вручную) |
| `entry_type`       | VARCHAR(20) | Нет      | `timer` или `manual`                |
| `is_billable`      | BOOLEAN     | Нет      | Флаг оплачиваемости (по умолчанию true) |
| `notes`            | TEXT        | Да       |                                     |
| `created_at`       | TIMESTAMPTZ | Нет      |                                     |
| `updated_at`       | TIMESTAMPTZ | Нет      |                                     |

**Индексы:** `task_id`, `user_id`

---

### warehouse_items

| Колонка              | Тип          | Nullable | Описание                                 |
|---------------------|-------------|----------|------------------------------------------|
| `id`                 | UUID PK     | Нет      |                                          |
| `name`               | VARCHAR(500)| Нет      | Название позиции (индексировано)         |
| `sku`                | VARCHAR(100)| Нет      | Код SKU (уникальный, индексированный)    |
| `category`           | VARCHAR(100)| Нет      | materials, tools, consumables, equipment (индексировано) |
| `unit`               | VARCHAR(20) | Нет      | Единица измерения (шт, м, кг, л)        |
| `quantity`           | NUMERIC(15,3)| Нет    | Текущий остаток на складе                |
| `reserved_quantity`  | NUMERIC(15,3)| Нет    | Зарезервировано под задачи               |
| `min_quantity`       | NUMERIC(15,3)| Нет    | Порог оповещения о низком остатке        |
| `price`              | NUMERIC(15,2)| Нет    | Цена за единицу                          |
| `description`        | TEXT        | Да       |                                          |
| `location`           | VARCHAR(255)| Да       | Место хранения                           |
| `created_at`         | TIMESTAMPTZ | Нет      |                                          |
| `updated_at`         | TIMESTAMPTZ | Нет      |                                          |

**Индексы:** `name`, `sku` (уникальный), `category`

---

### warehouse_movements

| Колонка         | Тип          | Nullable | Описание                                     |
|----------------|-------------|----------|----------------------------------------------|
| `id`            | UUID PK     | Нет      |                                              |
| `item_id`       | UUID FK     | Нет      | → warehouse_items.id (индексировано)        |
| `task_id`       | UUID FK     | Да       | → tasks.id (индексировано)                  |
| `user_id`       | UUID FK     | Нет      | → users.id                                  |
| `movement_type` | VARCHAR(50) | Нет      | intake, consumption, write_off, transfer, return (индексировано) |
| `quantity`      | NUMERIC(15,3)| Нет    | Количество движения (всегда положительное)   |
| `unit_price`    | NUMERIC(15,2)| Да     | Цена на момент движения                      |
| `reason`        | TEXT        | Да       | Комментарий / причина                        |
| `destination`   | VARCHAR(255)| Да       | Пункт назначения перемещения                 |
| `created_at`    | TIMESTAMPTZ | Нет      |                                              |
| `updated_at`    | TIMESTAMPTZ | Нет      |                                              |

**Индексы:** `item_id`, `task_id`, `movement_type`

---

### warehouse_reservations

| Колонка     | Тип          | Nullable | Описание                                  |
|------------|-------------|----------|-------------------------------------------|
| `id`        | UUID PK     | Нет      |                                           |
| `item_id`   | UUID FK     | Нет      | → warehouse_items.id (индексировано)     |
| `task_id`   | UUID FK     | Нет      | → tasks.id (индексировано)               |
| `quantity`  | NUMERIC(15,3)| Нет    | Зарезервированное количество              |
| `status`    | VARCHAR(50) | Нет      | reserved, consumed, cancelled             |
| `created_at`| TIMESTAMPTZ | Нет      |                                           |
| `updated_at`| TIMESTAMPTZ | Нет      |                                           |

**Индексы:** `item_id`, `task_id`

---

### equipment

| Колонка               | Тип          | Nullable | Описание                                 |
|----------------------|-------------|----------|------------------------------------------|
| `id`                  | UUID PK     | Нет      |                                          |
| `name`                | VARCHAR(500)| Нет      | Название оборудования (индексировано)    |
| `serial_number`       | VARCHAR(200)| Нет      | Серийный номер (уникальный, индексированный) |
| `category`            | VARCHAR(100)| Нет      | power_tool, measuring, hand_tool, safety, vehicle (индексировано) |
| `purchase_price`      | NUMERIC(15,2)| Нет    | Закупочная стоимость                     |
| `purchase_date`       | DATE        | Нет      |                                          |
| `service_life_months` | INTEGER     | Нет      | Ожидаемый срок эксплуатации              |
| `current_value`       | NUMERIC(15,2)| Нет    | Текущая балансовая стоимость             |
| `status`              | VARCHAR(50) | Нет      | active, maintenance, written_off, lost (индексировано) |
| `assigned_to`         | UUID FK     | Да       | → users.id                              |
| `location`            | VARCHAR(255)| Да       |                                          |
| `notes`               | TEXT        | Да       |                                          |
| `created_at`          | TIMESTAMPTZ | Нет      |                                          |
| `updated_at`          | TIMESTAMPTZ | Нет      |                                          |

**Индексы:** `name`, `serial_number` (уникальный), `category`, `status`

---

### equipment_usage

| Колонка        | Тип          | Nullable | Описание                        |
|---------------|-------------|----------|---------------------------------|
| `id`           | UUID PK     | Нет      |                                 |
| `equipment_id` | UUID FK     | Нет      | → equipment.id (индексировано) |
| `task_id`      | UUID FK     | Нет      | → tasks.id (индексировано)     |
| `user_id`      | UUID FK     | Нет      | → users.id                     |
| `hours_used`   | NUMERIC(8,2)| Нет     | Длительность использования в часах |
| `notes`        | TEXT        | Да       |                                 |
| `created_at`   | TIMESTAMPTZ | Нет      |                                 |
| `updated_at`   | TIMESTAMPTZ | Нет      |                                 |

**Индексы:** `equipment_id`, `task_id`

---

### depreciation_records

| Колонка           | Тип          | Nullable | Описание                               |
|-------------------|-------------|----------|-----------------------------------------|
| `id`              | UUID PK     | Нет      |                                         |
| `equipment_id`    | UUID FK     | Нет      | → equipment.id (CASCADE, индексировано) |
| `period_date`     | DATE        | Нет      | Первый день месяца                      |
| `amount`          | NUMERIC(15,2)| Нет    | Амортизация за период                   |
| `accumulated`     | NUMERIC(15,2)| Нет    | Итого накопленная амортизация           |
| `remaining_value` | NUMERIC(15,2)| Нет    | Балансовая стоимость после периода      |
| `method`          | VARCHAR(50) | Нет      | straight_line, declining_balance        |
| `notes`           | TEXT        | Да       |                                         |
| `created_at`      | TIMESTAMPTZ | Нет      |                                         |
| `updated_at`      | TIMESTAMPTZ | Нет      |                                         |

**Индексы:** `equipment_id`

---

### documents

| Колонка        | Тип          | Nullable | Описание                                      |
|---------------|-------------|----------|-----------------------------------------------|
| `id`           | UUID PK     | Нет      |                                               |
| `task_id`      | UUID FK     | Да       | → tasks.id (SET NULL, индексировано)         |
| `uploaded_by`  | UUID FK     | Нет      | → users.id                                   |
| `doc_type`     | VARCHAR(50) | Нет      | photo, signed_act, invoice, report, other (индексировано) |
| `label`        | VARCHAR(200)| Да       | Семантическая метка (напр. indoor_unit_installed) |
| `filename`     | VARCHAR(500)| Нет      | Оригинальное имя файла                        |
| `storage_path` | VARCHAR(1000)| Нет    | Путь в MinIO (bucket/key)                     |
| `mime_type`    | VARCHAR(100)| Нет      | MIME-тип                                      |
| `file_size`    | BIGINT      | Нет      | Размер в байтах                               |
| `version`      | INTEGER     | Нет      | Номер текущей версии                          |
| `metadata`     | JSONB       | Нет      | EXIF, GPS, подписи и пр.                      |
| `description`  | TEXT        | Да       |                                               |
| `created_at`   | TIMESTAMPTZ | Нет      |                                               |
| `updated_at`   | TIMESTAMPTZ | Нет      |                                               |

**Индексы:** `task_id`, `doc_type`

---

### document_versions

| Колонка        | Тип          | Nullable | Описание                               |
|---------------|-------------|----------|-----------------------------------------|
| `id`           | UUID PK     | Нет      |                                         |
| `document_id`  | UUID FK     | Нет      | → documents.id (CASCADE, индексировано) |
| `version`      | INTEGER     | Нет      | Номер версии                            |
| `storage_path` | VARCHAR(1000)| Нет    | Путь в MinIO для этой версии            |
| `file_size`    | BIGINT      | Нет      | Размер в байтах                         |
| `uploaded_by`  | UUID FK     | Нет      | → users.id                             |
| `created_at`   | TIMESTAMPTZ | Нет      |                                         |
| `updated_at`   | TIMESTAMPTZ | Нет      |                                         |

**Индексы:** `document_id`

---

### comments

| Колонка        | Тип          | Nullable | Описание                                 |
|---------------|-------------|----------|------------------------------------------|
| `id`           | UUID PK     | Нет      |                                          |
| `task_id`      | UUID FK     | Нет      | → tasks.id (CASCADE, индексировано)     |
| `author_id`    | UUID FK     | Нет      | → users.id                              |
| `body`         | TEXT        | Нет      | Текст комментария (поддержка Markdown)   |
| `mentions`     | JSONB       | Нет      | Массив UUID упомянутых пользователей     |
| `attachments`  | JSONB       | Нет      | Массив UUID прикреплённых документов     |
| `created_at`   | TIMESTAMPTZ | Нет      |                                          |
| `updated_at`   | TIMESTAMPTZ | Нет      |                                          |

**Индексы:** `task_id`

---

### notifications

| Колонка        | Тип          | Nullable | Описание                                     |
|---------------|-------------|----------|----------------------------------------------|
| `id`           | UUID PK     | Нет      |                                              |
| `user_id`      | UUID FK     | Нет      | → users.id (индексировано)                  |
| `channel`      | VARCHAR(50) | Нет      | telegram, web_push, email                    |
| `event_type`   | VARCHAR(100)| Нет      | task_assigned, status_changed и др. (индексировано) |
| `title`        | VARCHAR(500)| Нет      | Заголовок уведомления                        |
| `body`         | TEXT        | Нет      | Тело уведомления                             |
| `data`         | JSONB       | Нет      | Структурированные данные события             |
| `is_read`      | BOOLEAN     | Нет      | Флаг прочтения                               |
| `is_delivered`  | BOOLEAN    | Нет      | Подтверждение доставки                       |
| `created_at`   | TIMESTAMPTZ | Нет      |                                              |
| `updated_at`   | TIMESTAMPTZ | Нет      |                                              |

**Индексы:** `user_id`, `event_type`

---

### references

| Колонка       | Тип          | Nullable | Описание                                 |
|--------------|-------------|----------|------------------------------------------|
| `id`          | UUID PK     | Нет      |                                          |
| `code`        | VARCHAR(100)| Нет      | Код справочника (уникальный, индексированный) |
| `name`        | VARCHAR(255)| Нет      | Отображаемое название                    |
| `description` | VARCHAR(1000)| Да     |                                          |
| `is_system`   | BOOLEAN     | Нет      | Системный справочник (нельзя удалить)    |
| `created_at`  | TIMESTAMPTZ | Нет      |                                          |
| `updated_at`  | TIMESTAMPTZ | Нет      |                                          |

**Индексы:** `code` (уникальный)

---

### reference_items

| Колонка        | Тип          | Nullable | Описание                            |
|---------------|-------------|----------|-------------------------------------|
| `id`           | UUID PK     | Нет      |                                     |
| `reference_id` | UUID FK     | Нет      | → references.id (CASCADE, индексировано) |
| `code`         | VARCHAR(100)| Нет      | Код элемента                        |
| `name`         | VARCHAR(500)| Нет      | Отображаемое название               |
| `metadata`     | JSONB       | Нет      | Дополнительные атрибуты (ед. изм., цена) |
| `order`        | INTEGER     | Нет      | Порядок сортировки                  |
| `is_active`    | BOOLEAN     | Нет      | Флаг активности                     |
| `created_at`   | TIMESTAMPTZ | Нет      |                                     |
| `updated_at`   | TIMESTAMPTZ | Нет      |                                     |

**Индексы:** `reference_id`

---

## Структуры JSONB-полей

### workflow_definition (task_templates)

Основное определение конечного автомата, хранимое как JSONB:

```json
{
  "initial_state": "new",
  "states": [
    {"id": "new",           "type": "initial"},
    {"id": "site_survey",   "type": "intermediate"},
    {"id": "in_progress",   "type": "intermediate"},
    {"id": "review",        "type": "intermediate"},
    {"id": "completed",     "type": "final"},
    {"id": "cancelled",     "type": "terminal"}
  ],
  "transitions": [
    {
      "from": "new",
      "to": "site_survey",
      "required_roles": ["engineer", "manager"],
      "required_fields": [],
      "required_checklists": [],
      "required_documents": [],
      "auto_actions": []
    },
    {
      "from": "site_survey",
      "to": "in_progress",
      "required_roles": ["engineer"],
      "required_fields": ["area_sqm", "equipment_model"],
      "required_checklists": ["site_survey_checklist"],
      "required_documents": [
        {"type": "photo", "min_count": 2}
      ],
      "auto_actions": []
    },
    {
      "from": "in_progress",
      "to": "review",
      "required_roles": ["engineer"],
      "required_checklists": ["installation_checklist"],
      "auto_actions": [
        {"type": "deduct_warehouse", "from_field": "materials_used"},
        {"type": "complete_time_entry"}
      ]
    },
    {
      "from": "review",
      "to": "completed",
      "required_roles": ["manager"],
      "required_documents": [
        {"type": "signed_act", "min_count": 1}
      ],
      "auto_actions": [
        {"type": "notify", "channel": "telegram", "template": "task_completed"}
      ]
    }
  ]
}
```

Подробную семантику см. в [документации движка воркфлоу](workflow-engine.md).

### custom_fields (tasks)

Поля, определённые шаблоном и заполняемые на уровне задачи:

```json
{
  "area_sqm": 45.0,
  "equipment_model": "Daikin FTXB35C",
  "floor": 7,
  "address": "Москва, ул. Ленина 15, кв. 42",
  "materials_used": [
    {"item_id": "uuid-copper-tube", "quantity": 10.0},
    {"item_id": "uuid-bracket", "quantity": 2.0}
  ],
  "customer_signature": true,
  "installation_notes": "Настенный монтаж, восточная сторона"
}
```

### salary_config (users)

Параметры расчёта заработной платы для каждого сотрудника:

```json
{
  "type": "mixed",
  "base_monthly": 50000.0,
  "per_task_bonus": {
    "installation": 3000.0,
    "maintenance": 1500.0,
    "repair": 2000.0,
    "inspection": 800.0
  },
  "overtime_rate": 1.5,
  "standard_hours_monthly": 160,
  "deductions": {
    "equipment_damage_rate": 0.0,
    "advance_deduction": 0.0
  }
}
```
