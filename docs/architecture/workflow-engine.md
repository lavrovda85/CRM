# Движок рабочих процессов

Движок рабочих процессов представляет собой конечный автомат (КА, FSM), управляющий переходами жизненного цикла задач. Он реализован в `backend/app/services/workflow_engine.py` как класс `WorkflowEngine` и является ядром слоя бизнес-логики платформы.

## Обзор

Каждая задача может быть связана с `TaskTemplate`, который определяет `workflow_definition` — JSONB-поле, описывающее состояния, через которые проходит задача, допустимые переходы между ними и условия, которые должны быть выполнены перед каждым переходом.

```
┌─────────┐   переход      ┌─────────────┐   переход      ┌───────────┐
│  new     │──────────────►│ in_progress  │──────────────►│ completed  │
│(начальный)│              │(промежуточный)│              │ (конечный) │
└─────────┘               └─────────────┘               └───────────┘
      │                                                       ▲
      │              переход                                  │
      └───────────────────────────────────────────────────────┘
                    (если нет промежуточных шагов)
```

## Определение воркфлоу (JSON-структура)

`workflow_definition` хранится как JSONB в таблице `task_templates`. Содержит два ключа верхнего уровня: `states` и `transitions`, а также индикатор `initial_state`.

```json
{
  "initial_state": "new",
  "states": [
    {"id": "new",         "type": "initial"},
    {"id": "site_survey", "type": "intermediate"},
    {"id": "in_progress", "type": "intermediate"},
    {"id": "review",      "type": "intermediate"},
    {"id": "completed",   "type": "final"},
    {"id": "cancelled",   "type": "terminal"}
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
    }
  ]
}
```

### Валидация через Pydantic

JSON-структура парсится и валидируется во время выполнения моделями Pydantic `WorkflowDefinition` и `WorkflowTransition` (см. `backend/app/schemas/template.py`).

## Типы состояний

| Тип            | Семантика                                                                    |
|----------------|-----------------------------------------------------------------------------|
| `initial`      | Точка входа. Задачи начинаются в этом состоянии при создании из шаблона. В воркфлоу допускается только одно начальное состояние. Движок читает `initial_state` для определения начального статуса при создании задачи. |
| `intermediate` | Рабочее состояние. Задачи находятся здесь, пока выполняются действия (осмотр, монтаж, проверка и т.д.). |
| `final`        | Успешное завершение. Когда задача достигает конечного состояния, устанавливается `completed_at`. Дальнейшие переходы не предполагаются. |
| `terminal`     | Тупиковое состояние без успешного завершения (отменена, отклонена). `completed_at` НЕ устанавливается. Дальнейшие переходы невозможны. |

Движок автоматически устанавливает временные метки жизненного цикла:
- `started_at` устанавливается при первом переходе из `initial` (если целевое состояние не `cancelled`)
- `completed_at` устанавливается при входе в `final`-состояние (`completed`, `done`, `closed`)

## Условия перехода

Каждый переход может содержать ноль или более условий. Все условия должны быть выполнены для разрешения перехода. Если хотя бы одно условие не выполнено, возбуждается `WorkflowTransitionError` (HTTP 409) с подробностями о невыполненных условиях.

### Обязательные роли

```json
{
  "from": "review",
  "to": "completed",
  "required_roles": ["manager"]
}
```

Пользователь, выполняющий переход, должен иметь **хотя бы одну** из перечисленных ролей (извлекаются из JWT Keycloak `realm_access.roles`). Если список пуст, переход может выполнить любой аутентифицированный пользователь.

### Обязательные поля

```json
{
  "from": "site_survey",
  "to": "in_progress",
  "required_fields": ["area_sqm", "equipment_model", "floor"]
}
```

Движок проверяет, что все перечисленные поля имеют непустые значения. Сначала проверяются стандартные ORM-колонки задачи, затем `custom_fields` JSONB. Поле считается пустым, если оно равно `null`, является пустой строкой или отсутствует в обоих источниках.

### Обязательные чек-листы

```json
{
  "from": "in_progress",
  "to": "review",
  "required_checklists": ["installation_checklist"]
}
```

Движок находит строки `Checklist`, прикреплённые к задаче, где `title` или `gate_transition` совпадает. Формат gate_transition — `"from->to"` (напр. `"in_progress->review"`). Все элементы совпадающих чек-листов должны быть отмечены как `is_completed = true`.

Чек-листы создаются автоматически при инстанцировании задачи из шаблона (копируются из строк `TemplateChecklist`). Каждый элемент чек-листа соответствует строке `ChecklistItem`, которую отдельные пользователи могут переключать.

### Обязательные документы

```json
{
  "from": "review",
  "to": "completed",
  "required_documents": [
    {"type": "signed_act", "min_count": 1},
    {"type": "photo", "min_count": 3}
  ]
}
```

Движок подсчитывает строки `Document`, прикреплённые к задаче, группируя по `doc_type`. Каждое требование указывает тип документа и минимальное количество загрузок. Переход блокируется до выполнения всех минимумов.

## Авто-действия

Переходы могут запускать автоматические побочные эффекты после фиксации изменения статуса. Они определяются в массиве `auto_actions` каждого перехода.

### `deduct_warehouse`

Автоматическое списание материалов со склада на основе `custom_fields` задачи.

```json
{
  "type": "deduct_warehouse",
  "from_field": "materials_used"
}
```

**Поведение:**

1. Читает `task.custom_fields[from_field]` (по умолчанию `"materials_used"`)
2. Ожидает массив `{"item_id": "uuid", "quantity": N}`
3. Для каждой позиции:
   - Проверяет `available = quantity - reserved_quantity >= requested`
   - Вычитает из `WarehouseItem.quantity`
   - Создаёт запись `WarehouseMovement` с `movement_type = "consumption"`
4. При недостаточном остатке возбуждает `WarehouseInsufficientStockError` (откатывает переход)

### `complete_time_entry`

Закрывает все открытые (запущенные) записи учёта времени по задаче.

```json
{
  "type": "complete_time_entry"
}
```

**Поведение:**

1. Находит все строки `TimeEntry`, где `task_id` совпадает и `ended_at IS NULL`
2. Устанавливает `ended_at = now()`
3. Рассчитывает `duration_minutes = (ended_at - started_at) / 60`

Обычно используется при переходе в `review` или `completed`, чтобы не оставлять запущенные таймеры.

### `notify`

Создаёт записи уведомлений и отправляет их через Celery.

```json
{
  "type": "notify",
  "channel": "telegram",
  "template": "task_completed"
}
```

**Поведение:**

1. Определяет получателей: исполнитель задачи + создатель задачи (если отличается)
2. Создаёт строку `Notification` для каждого получателя с `channel`, `event_type`, заголовком и телом
3. Отправляет Celery-задачу `send_task_notification` для асинхронной доставки

**Каналы:** `telegram`, `web_push`, `email`

## Создание пользовательских шаблонов воркфлоу

### Шаг 1: Определить состояния

Перечислите все значимые состояния вашего воркфлоу. Включите как минимум одно `initial` и одно `final` состояние.

```json
{
  "initial_state": "new",
  "states": [
    {"id": "new",              "type": "initial"},
    {"id": "diagnostics",      "type": "intermediate"},
    {"id": "awaiting_parts",   "type": "intermediate"},
    {"id": "repair",           "type": "intermediate"},
    {"id": "testing",          "type": "intermediate"},
    {"id": "completed",        "type": "final"},
    {"id": "cancelled",        "type": "terminal"}
  ]
}
```

### Шаг 2: Определить переходы

Для каждой пары состояний, которые должны быть связаны, создайте объект перехода с условиями и авто-действиями.

```json
{
  "transitions": [
    {
      "from": "new",
      "to": "diagnostics",
      "required_roles": ["engineer"],
      "required_fields": [],
      "required_checklists": [],
      "required_documents": [],
      "auto_actions": []
    },
    {
      "from": "diagnostics",
      "to": "awaiting_parts",
      "required_roles": ["engineer"],
      "required_fields": ["defect_description"],
      "required_checklists": ["diagnostics_checklist"],
      "required_documents": [{"type": "photo", "min_count": 1}],
      "auto_actions": [
        {"type": "notify", "channel": "web_push", "template": "parts_needed"}
      ]
    }
  ]
}
```

### Шаг 3: Создать чек-листы

Добавьте строки `TemplateChecklist` к шаблону, каждую с `gate_transition`, соответствующим блокируемому переходу:

```json
{
  "checklist_id": "diagnostics_checklist",
  "title": "Чек-лист диагностики",
  "gate_transition": "diagnostics->awaiting_parts",
  "items": [
    "Проверить электропитание",
    "Измерить давление хладагента",
    "Осмотреть компрессор",
    "Проверить конденсатоотвод",
    "Протестировать термостат"
  ]
}
```

### Шаг 4: Определить пользовательские поля

Добавьте строки `TemplateField` для данных, которые инженеры должны заполнить:

| key                 | label               | field_type | is_required |
|---------------------|---------------------|------------|-------------|
| `defect_description`| Описание дефекта    | string     | true        |
| `parts_needed`      | Необходимые запчасти| string     | false       |
| `equipment_model`   | Модель оборудования | reference  | true        |
| `repair_cost`       | Ориентировочная стоимость | decimal | false     |

### Шаг 5: Настроить SLA

Задайте дедлайны SLA и пороги предупреждений:

```json
{
  "max_duration_hours": 72,
  "warning_at_percent": 75
}
```

Celery Beat SLA-монитор (`sla_monitor.py`) периодически проверяет задачи на соответствие `sla_deadline` и отправляет предупреждения при достижении порога.

---

## Пример: воркфлоу монтажа кондиционера (пошагово)

Этот пример прослеживает полный путь задачи на монтаж кондиционера через воркфлоу.

### Определение шаблона

**Название шаблона:** Монтаж кондиционера
**Категория:** installation

**Состояния:**

| Состояние    | Тип            | Описание                                         |
|-------------|----------------|--------------------------------------------------|
| `new`        | initial        | Задача создана, работа ещё не начата              |
| `site_survey`| intermediate   | Инженер выезжает на объект для оценки условий     |
| `in_progress`| intermediate   | Активные монтажные работы                         |
| `review`     | intermediate   | Менеджер проверяет работу и документы             |
| `completed`  | final          | Монтаж принят заказчиком                          |
| `cancelled`  | terminal       | Задача отменена                                   |

### Пошаговый проход

#### 1. Создание задачи

Менеджер создаёт задачу из шаблона «Монтаж кондиционера» для клиента Петрова:

```
POST /api/v1/templates/{template_id}/instantiate
{
  "client_id": "client-uuid",
  "title": "Монтаж кондиционера — кв. Петров",
  "assigned_to": "engineer-uuid",
  "custom_fields": {"equipment_model": "Daikin FTXB35C", "floor": 7}
}
```

**Результат:**
- Задача создана с `status = "new"`
- Созданы 3 чек-листа из шаблона (Осмотр объекта, Монтаж, Итоговая проверка)
- Рассчитан `sla_deadline` из `sla_config.max_duration_hours`

#### 2. Начало осмотра объекта (`new` → `site_survey`)

Инженер начинает работу:

```
POST /api/v1/tasks/{task_id}/transition
{"to_status": "site_survey"}
```

**Проверяемые условия:**
- ✅ Обязательные роли: `["engineer", "manager"]` — у инженера есть роль
- Нет обязательных полей, чек-листов или документов

**Побочные эффекты:**
- Устанавливается `task.started_at` (первый переход из начального состояния)
- Записана запись в `TaskStatusHistory`

#### 3. Завершение осмотра (`site_survey` → `in_progress`)

После осмотра объекта инженер заполняет чек-лист и обязательные поля:

```
POST /api/v1/tasks/{task_id}/transition
{"to_status": "in_progress"}
```

**Проверяемые условия:**
- ✅ Обязательные роли: `["engineer"]`
- ✅ Обязательные поля: `area_sqm`, `equipment_model` — заполнены в custom_fields
- ✅ Обязательные чек-листы: `"site_survey_checklist"` — все пункты отмечены
- ✅ Обязательные документы: 2 фотографии загружены (`doc_type = "photo"`)

#### 4. Завершение монтажа (`in_progress` → `review`)

Инженер завершает монтаж и заполняет монтажный чек-лист:

```
POST /api/v1/tasks/{task_id}/transition
{"to_status": "review"}
```

**Проверяемые условия:**
- ✅ Обязательные чек-листы: `"installation_checklist"` — все пункты отмечены

**Выполненные авто-действия:**
1. **`deduct_warehouse`** — читает `custom_fields.materials_used`:
   - Списывает 10м медной трубки со склада
   - Списывает 2 настенных кронштейна со склада
   - Создаёт записи `WarehouseMovement`
2. **`complete_time_entry`** — закрывает запущенный таймер инженера

#### 5. Утверждение менеджером (`review` → `completed`)

Менеджер проверяет работу и подтверждает загрузку подписанного акта приёмки:

```
POST /api/v1/tasks/{task_id}/transition
{"to_status": "completed", "reason": "Заказчик подписал акт приёмки"}
```

**Проверяемые условия:**
- ✅ Обязательные роли: `["manager"]`
- ✅ Обязательные документы: 1 `signed_act` загружен

**Выполненные авто-действия:**
1. **`notify`** — отправляет Telegram-уведомление инженеру и менеджеру:
   > «Задача "Монтаж кондиционера — кв. Петров" завершена»

**Побочные эффекты:**
- Устанавливается `task.completed_at`
- Запись в `TaskStatusHistory` с указанием причины
- Задача отображается как «завершена» на Kanban-доске

### Диаграмма состояний

```
                    ┌──────────┐
                    │   new    │
                    │(начальный)│
                    └────┬─────┘
                         │ required_roles: [engineer, manager]
                         ▼
                    ┌───────────┐
                    │site_survey│
                    └────┬──────┘
                         │ required_fields: [area_sqm, equipment_model]
                         │ required_checklists: [site_survey_checklist]
                         │ required_documents: [{photo, min: 2}]
                         ▼
                    ┌────────────┐
                    │in_progress │
                    └────┬───────┘
                         │ required_checklists: [installation_checklist]
                         │ auto_actions: [deduct_warehouse, complete_time_entry]
                         ▼
                    ┌──────────┐
                    │  review  │
                    └────┬─────┘
                         │ required_roles: [manager]
                         │ required_documents: [{signed_act, min: 1}]
                         │ auto_actions: [notify]
                         ▼
                    ┌──────────┐
                    │completed │
                    │(конечный)│
                    └──────────┘

   Любое состояние ──────► cancelled (терминальный)
```
