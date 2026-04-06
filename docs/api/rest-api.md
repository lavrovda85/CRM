# Справочник REST API

Бэкенд SPEC CRM/ERP предоставляет RESTful API, построенный на FastAPI. Интерактивная документация доступна по адресу `/api/docs` (Swagger UI) и `/api/openapi.json` (спецификация OpenAPI 3.1) при запущенном бэкенде.

## Базовый URL

```
http://localhost:8000/api/v1
```

В продакшене запросы проходят через обратный прокси Nginx на порту 80.

## Аутентификация

Все эндпоинты (кроме `/health`) требуют Bearer-токен, выданный Keycloak.

**Заголовки:**

```
Authorization: Bearer <keycloak_jwt_token>
```

**Получение токена:**

```bash
# Грант по паролю (для пользователей)
curl -X POST http://localhost:8080/realms/hvac/protocol/openid-connect/token \
  -d "grant_type=password" \
  -d "client_id=hvac-frontend" \
  -d "username=user@example.com" \
  -d "password=secret"

# Грант по клиентским учётным данным (для сервисных аккаунтов)
curl -X POST http://localhost:8080/realms/hvac/protocol/openid-connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=hvac-backend" \
  -d "client_secret=YOUR_SECRET"
```

JWT-токен содержит роли realm Keycloak, используемые для RBAC:
- `admin` — полный доступ к платформе
- `manager` — CRM, сделки, тендеры, управление задачами
- `engineer` — выполнение задач, учёт времени, чек-листы
- `warehouse_manager` — складской учёт
- `accountant` — аналитика, зарплатные отчёты

## Пагинация

Все эндпоинты-списки возвращают пагинированные ответы:

```json
{
  "items": [ ... ],
  "total": 142,
  "offset": 0,
  "limit": 50
}
```

**Параметры запроса:**

| Параметр  | Тип   | По умолчанию | Описание                          |
|-----------|-------|--------------|-----------------------------------|
| `offset`  | `int` | 0            | Количество пропускаемых элементов |
| `limit`   | `int` | 50           | Размер страницы (макс: 200)       |

## Формат ответа с ошибкой

Все ошибки следуют стандартизированному формату:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Task with id '...' not found",
    "details": {
      "entity": "Task",
      "entity_id": "uuid-..."
    }
  }
}
```

**Коды ошибок:**

| Код                         | HTTP | Описание                                     |
|-----------------------------|------|----------------------------------------------|
| `AUTH_REQUIRED`             | 401  | Отсутствует или недействительна аутентификация |
| `INVALID_TOKEN`             | 401  | Ошибка валидации JWT                         |
| `AUTHORIZATION_ERROR`       | 403  | У пользователя нет требуемой роли            |
| `NOT_FOUND`                 | 404  | Сущность не найдена                          |
| `VALIDATION_ERROR`          | 422  | Ошибка валидации входных данных              |
| `WORKFLOW_TRANSITION_DENIED`| 409  | Переход по воркфлоу не разрешён              |
| `TENDER_TRANSITION_DENIED` | 409  | Переход статуса тендера не разрешён (пайплайн) |
| `INSUFFICIENT_STOCK`        | 409  | Недостаточно складских остатков              |
| `DUPLICATE_ENTITY`          | 409  | Обнаружена дублирующаяся сущность            |
| `EXTERNAL_SERVICE_ERROR`    | 502  | Ошибка вызова внешнего сервиса               |
| `INTERNAL_ERROR`            | 500  | Необработанная ошибка сервера                |

## WebSocket-подключение

Обновления в реальном времени доступны через WebSocket:

```
ws://localhost:8000/ws?token=<jwt_token>
```

События отправляются как JSON-сообщения:

```json
{
  "event": "task_status_changed",
  "data": {
    "task_id": "uuid-...",
    "from_status": "in_progress",
    "to_status": "review",
    "changed_by": "uuid-..."
  }
}
```

---

## Группы эндпоинтов

### Система

| Метод  | Путь      | Описание                               |
|--------|-----------|----------------------------------------|
| GET    | `/health` | Проверка работоспособности (без авторизации) |

**Ответ:** `{"status": "healthy", "version": "0.1.0"}`

---

### Задачи

| Метод  | Путь                                                          | Описание                            |
|--------|---------------------------------------------------------------|-------------------------------------|
| POST   | `/api/v1/tasks/`                                              | Создать новую задачу                |
| GET    | `/api/v1/tasks/`                                              | Список задач (с пагинацией и фильтрами) |
| GET    | `/api/v1/tasks/deleted`                                       | Корзина: мягко удалённые задачи (admin, manager) |
| GET    | `/api/v1/tasks/{task_id}`                                     | Получить задачу со связями          |
| PATCH  | `/api/v1/tasks/{task_id}`                                     | Обновить поля задачи                |
| DELETE | `/api/v1/tasks/{task_id}`                                     | Мягкое удаление (строка остаётся, скрыта из списков и аналитики) |
| POST   | `/api/v1/tasks/{task_id}/restore`                             | Восстановить из корзины (admin, manager) |
| POST   | `/api/v1/tasks/{task_id}/transition`                          | Переход статуса по воркфлоу         |
| POST   | `/api/v1/tasks/{task_id}/checklists/{cl_id}/items/{item_id}/toggle` | Переключить элемент чек-листа |

**Фильтры списка:** `status`, `assigned_to`, `client_id`, `board_id`, `priority`

**Тело запроса на создание:**

```json
{
  "title": "Монтаж кондиционера",
  "template_id": "uuid | null",
  "board_id": "uuid | null",
  "client_id": "uuid | null",
  "deal_id": "uuid | null",
  "tender_id": "uuid | null",
  "assigned_to": "uuid | null",
  "description": "string | null",
  "priority": "low | medium | high | critical",
  "custom_fields": {},
  "due_date": "2026-04-15T18:00:00Z | null"
}
```

**PATCH** `/tasks/{id}`: те же логические поля частично; дополнительно можно править даты **`started_at`**, **`completed_at`**, **`sla_deadline`** (ISO 8601 или `null` для очистки). Статус меняется через `POST .../transition`, не через PATCH.

**Тело запроса на переход:**

```json
{
  "to_status": "in_progress",
  "reason": "Начало работ",
  "checklist_data": {}
}
```

---

### Шаблоны

| Метод  | Путь                                       | Описание                                |
|--------|--------------------------------------------|-----------------------------------------|
| POST   | `/api/v1/templates/`                       | Создать новый шаблон задачи             |
| GET    | `/api/v1/templates/`                       | Список шаблонов                         |
| GET    | `/api/v1/templates/{template_id}`          | Получить детали шаблона                 |
| PATCH  | `/api/v1/templates/{template_id}`          | Обновить шаблон                         |
| POST   | `/api/v1/templates/{template_id}/instantiate` | Создать задачу из шаблона           |

---

### Доски

| Метод  | Путь                            | Описание                      |
|--------|---------------------------------|-------------------------------|
| POST   | `/api/v1/boards/`               | Создать новую доску           |
| GET    | `/api/v1/boards/`               | Список досок                  |
| GET    | `/api/v1/boards/{board_id}`     | Получить доску с задачами     |
| PATCH  | `/api/v1/boards/{board_id}`     | Обновить доску                |
| DELETE | `/api/v1/boards/{board_id}`     | Удалить / архивировать доску  |

---

### Клиенты

| Метод  | Путь                                         | Описание                       |
|--------|----------------------------------------------|--------------------------------|
| POST   | `/api/v1/clients/`                           | Создать нового клиента         |
| GET    | `/api/v1/clients/`                           | Список клиентов (с пагинацией) |
| GET    | `/api/v1/clients/{client_id}`                | Получить детали клиента        |
| PATCH  | `/api/v1/clients/{client_id}`                | Обновить клиента               |
| DELETE | `/api/v1/clients/{client_id}`                | Удалить клиента                |
| POST   | `/api/v1/clients/{client_id}/contacts`       | Добавить контактное лицо       |
| PATCH  | `/api/v1/clients/{client_id}/contacts/{id}`  | Обновить контакт               |
| DELETE | `/api/v1/clients/{client_id}/contacts/{id}`  | Удалить контакт                |

---

### Сделки

| Метод  | Путь                              | Описание                            |
|--------|-----------------------------------|-------------------------------------|
| POST   | `/api/v1/deals/`                  | Создать новую сделку                |
| GET    | `/api/v1/deals/`                  | Список сделок (с пагинацией и фильтрами) |
| GET    | `/api/v1/deals/{deal_id}`         | Получить детали сделки              |
| PATCH  | `/api/v1/deals/{deal_id}`         | Обновить сделку                     |
| POST   | `/api/v1/deals/{deal_id}/move`    | Переместить сделку на другую стадию |
| GET    | `/api/v1/deals/stages`            | Список стадий воронки               |

---

### Тендеры

| Метод  | Путь                                      | Описание                             |
|--------|-------------------------------------------|--------------------------------------|
| POST   | `/api/v1/tenders/`                        | Создать новый тендер                 |
| GET    | `/api/v1/tenders/`                        | Список тендеров (с пагинацией и фильтрами) |
| GET    | `/api/v1/tenders/{tender_id}`             | Получить детали тендера              |
| PATCH  | `/api/v1/tenders/{tender_id}`             | Обновить тендер (в т.ч. `status` с проверкой пайплайна) |
| POST   | `/api/v1/tenders/{tender_id}/transition`  | Перевести тендер в следующий статус пайплайна (`TenderTransitionRequest`) |
| POST   | `/api/v1/tenders/{tender_id}/link-tasks`  | Привязать задачи к тендеру; **все** `task_ids` должны существовать (иначе 422) |

---

### Учёт рабочего времени

| Метод  | Путь                                     | Описание                        |
|--------|------------------------------------------|---------------------------------|
| POST   | `/api/v1/time/entries`                   | Создать запись времени          |
| GET    | `/api/v1/time/entries`                   | Список записей (с фильтрами)   |
| PATCH  | `/api/v1/time/entries/{entry_id}`        | Обновить запись времени         |
| DELETE | `/api/v1/time/entries/{entry_id}`        | Удалить запись времени          |
| POST   | `/api/v1/time/entries/{entry_id}/start`  | Запустить таймер                |
| POST   | `/api/v1/time/entries/{entry_id}/stop`   | Остановить таймер               |

**Фильтры:** `task_id`, `user_id`, `is_billable`, `date_from`, `date_to`

---

### Склад

| Метод  | Путь                                              | Описание                             |
|--------|---------------------------------------------------|--------------------------------------|
| POST   | `/api/v1/warehouse/items`                         | Создать складскую позицию            |
| GET    | `/api/v1/warehouse/items`                         | Список позиций (с пагинацией и фильтрами) |
| GET    | `/api/v1/warehouse/items/{item_id}`               | Получить детали позиции              |
| PATCH  | `/api/v1/warehouse/items/{item_id}`               | Обновить позицию                     |
| POST   | `/api/v1/warehouse/movements`                     | Зафиксировать движение               |
| GET    | `/api/v1/warehouse/movements`                     | Список движений (с фильтрами)       |
| POST   | `/api/v1/warehouse/reservations`                  | Создать резервирование               |
| GET    | `/api/v1/warehouse/reservations`                  | Список резервирований                |
| PATCH  | `/api/v1/warehouse/reservations/{reservation_id}` | Обновить статус резервирования       |
| GET    | `/api/v1/warehouse/low-stock`                     | Позиции ниже min_quantity            |

**Фильтры позиций:** `category`, `search` (имя/SKU)

---

### Амортизация

| Метод  | Путь                                      | Описание                                |
|--------|-------------------------------------------|-----------------------------------------|
| GET    | `/api/v1/depreciation/equipment`          | Список оборудования с амортизацией      |
| GET    | `/api/v1/depreciation/equipment/{eq_id}`  | Детали амортизации оборудования         |
| POST   | `/api/v1/depreciation/calculate`          | Выполнить расчёт амортизации            |
| GET    | `/api/v1/depreciation/report`             | Получить отчёт по амортизации           |

---

### Документы

| Метод  | Путь                                         | Описание                             |
|--------|----------------------------------------------|--------------------------------------|
| POST   | `/api/v1/documents/upload`                   | Загрузить документ (multipart)       |
| GET    | `/api/v1/documents/`                         | Список документов (с фильтрами)     |
| GET    | `/api/v1/documents/{document_id}`            | Получить метаданные документа        |
| GET    | `/api/v1/documents/{document_id}/download`   | Скачать файл документа               |
| POST   | `/api/v1/documents/{document_id}/version`    | Загрузить новую версию               |
| DELETE | `/api/v1/documents/{document_id}`            | Удалить документ                     |

**Фильтры:** `task_id`, `doc_type`, `uploaded_by`

---

### Справочники

| Метод  | Путь                                             | Описание                            |
|--------|--------------------------------------------------|-------------------------------------|
| POST   | `/api/v1/references/`                            | Создать справочник                  |
| GET    | `/api/v1/references/`                            | Список справочников                 |
| GET    | `/api/v1/references/{code}`                      | Получить справочник по коду         |
| PATCH  | `/api/v1/references/{code}`                      | Обновить справочник                 |
| POST   | `/api/v1/references/{code}/items`                | Добавить элемент в справочник       |
| PATCH  | `/api/v1/references/{code}/items/{item_id}`      | Обновить элемент справочника        |
| DELETE | `/api/v1/references/{code}/items/{item_id}`      | Удалить элемент справочника         |

---

### Аналитика

| Метод  | Путь                                      | Описание                                 |
|--------|-------------------------------------------|------------------------------------------|
| GET    | `/api/v1/analytics/dashboard`             | Статистика дашборда                      |
| GET    | `/api/v1/analytics/performance/{user_id}` | Показатели эффективности сотрудника      |
| GET    | `/api/v1/analytics/salary/{user_id}`      | Расчёт заработной платы                  |
| GET    | `/api/v1/analytics/tenders`               | Аналитика по тендерам                    |

**Параметры запроса:** `period_days`, `year`, `month`
