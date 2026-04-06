# REST API Reference

The HVAC CRM/ERP backend exposes a RESTful API built with FastAPI. Interactive documentation is available at `/api/docs` (Swagger UI) and `/api/openapi.json` (OpenAPI 3.1 spec) when the backend is running.

## Base URL

```
http://localhost:8000/api/v1
```

In production, requests go through the Nginx reverse proxy on port 80.

## Authentication

All endpoints (except `/health`) require a Bearer token issued by Keycloak.

**Headers:**

```
Authorization: Bearer <keycloak_jwt_token>
```

**Token retrieval:**

```bash
# Password grant (for users)
curl -X POST http://localhost:8080/realms/hvac/protocol/openid-connect/token \
  -d "grant_type=password" \
  -d "client_id=hvac-frontend" \
  -d "username=user@example.com" \
  -d "password=secret"

# Client credentials grant (for service accounts)
curl -X POST http://localhost:8080/realms/hvac/protocol/openid-connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=hvac-backend" \
  -d "client_secret=YOUR_SECRET"
```

The JWT token contains Keycloak realm roles used for RBAC:
- `admin` — full platform access
- `manager` — CRM, deals, tenders, task management
- `engineer` — task execution, time tracking, checklists
- `warehouse_manager` — inventory management
- `accountant` — analytics, salary reports

## Pagination

All list endpoints return paginated responses:

```json
{
  "items": [ ... ],
  "total": 142,
  "offset": 0,
  "limit": 50
}
```

**Query parameters:**

| Parameter | Type  | Default | Description             |
|-----------|-------|---------|-------------------------|
| `offset`  | `int` | 0       | Number of items to skip |
| `limit`   | `int` | 50      | Page size (max: 200)    |

## Error Response Format

All errors follow a standardized envelope:

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

**Error codes:**

| Code                       | HTTP | Description                                  |
|----------------------------|------|----------------------------------------------|
| `AUTH_REQUIRED`            | 401  | Missing or invalid authentication            |
| `INVALID_TOKEN`            | 401  | JWT validation failed                        |
| `AUTHORIZATION_ERROR`      | 403  | User lacks required role                     |
| `NOT_FOUND`                | 404  | Entity not found                             |
| `VALIDATION_ERROR`         | 422  | Input validation failed                      |
| `WORKFLOW_TRANSITION_DENIED`| 409 | Workflow transition not allowed              |
| `INSUFFICIENT_STOCK`       | 409  | Not enough warehouse stock                   |
| `DUPLICATE_ENTITY`         | 409  | Duplicate entity detected                    |
| `EXTERNAL_SERVICE_ERROR`   | 502  | External service call failed                 |
| `INTERNAL_ERROR`           | 500  | Unhandled server error                       |

## WebSocket Connection

Real-time updates are available via WebSocket:

```
ws://localhost:8000/ws?token=<jwt_token>
```

Events are pushed as JSON messages:

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

## Endpoint Groups

### System

| Method | Path      | Description                     |
|--------|-----------|---------------------------------|
| GET    | `/health` | Health check (no auth required) |

**Response:** `{"status": "healthy", "version": "0.1.0"}`

---

### Tasks

| Method | Path                                                         | Description                     |
|--------|--------------------------------------------------------------|---------------------------------|
| POST   | `/api/v1/tasks/`                                             | Create a new task               |
| GET    | `/api/v1/tasks/`                                             | List tasks (paginated, filtered)|
| GET    | `/api/v1/tasks/{task_id}`                                    | Get task detail with relations  |
| PATCH  | `/api/v1/tasks/{task_id}`                                    | Update task fields              |
| DELETE | `/api/v1/tasks/{task_id}`                                    | Delete a task                   |
| POST   | `/api/v1/tasks/{task_id}/transition`                         | Workflow status transition      |
| POST   | `/api/v1/tasks/{task_id}/checklists/{cl_id}/items/{item_id}/toggle` | Toggle checklist item  |

**List filters:** `status`, `assigned_to`, `client_id`, `board_id`, `priority`

**Create body:**

```json
{
  "title": "AC Installation",
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

**Transition body:**

```json
{
  "to_status": "in_progress",
  "reason": "Starting work",
  "checklist_data": {}
}
```

---

### Templates

| Method | Path                                      | Description                              |
|--------|-------------------------------------------|------------------------------------------|
| POST   | `/api/v1/templates/`                      | Create a new task template               |
| GET    | `/api/v1/templates/`                      | List templates                           |
| GET    | `/api/v1/templates/{template_id}`         | Get template detail                      |
| PATCH  | `/api/v1/templates/{template_id}`         | Update template                          |
| POST   | `/api/v1/templates/{template_id}/instantiate` | Create task from template            |

---

### Boards

| Method | Path                           | Description                   |
|--------|--------------------------------|-------------------------------|
| POST   | `/api/v1/boards/`              | Create a new board            |
| GET    | `/api/v1/boards/`              | List boards                   |
| GET    | `/api/v1/boards/{board_id}`    | Get board with tasks          |
| PATCH  | `/api/v1/boards/{board_id}`    | Update board                  |
| DELETE | `/api/v1/boards/{board_id}`    | Delete / archive board        |

---

### Clients

| Method | Path                                        | Description                    |
|--------|---------------------------------------------|--------------------------------|
| POST   | `/api/v1/clients/`                          | Create a new client            |
| GET    | `/api/v1/clients/`                          | List clients (paginated)       |
| GET    | `/api/v1/clients/{client_id}`               | Get client detail              |
| PATCH  | `/api/v1/clients/{client_id}`               | Update client                  |
| DELETE | `/api/v1/clients/{client_id}`               | Delete client                  |
| POST   | `/api/v1/clients/{client_id}/contacts`      | Add contact person             |
| PATCH  | `/api/v1/clients/{client_id}/contacts/{id}` | Update contact                 |
| DELETE | `/api/v1/clients/{client_id}/contacts/{id}` | Delete contact                 |

---

### Deals

| Method | Path                             | Description                         |
|--------|----------------------------------|-------------------------------------|
| POST   | `/api/v1/deals/`                 | Create a new deal                   |
| GET    | `/api/v1/deals/`                 | List deals (paginated, filtered)    |
| GET    | `/api/v1/deals/{deal_id}`        | Get deal detail                     |
| PATCH  | `/api/v1/deals/{deal_id}`        | Update deal                         |
| POST   | `/api/v1/deals/{deal_id}/move`   | Move deal to a different stage      |
| GET    | `/api/v1/deals/stages`           | List pipeline stages                |

---

### Tenders

| Method | Path                                     | Description                       |
|--------|------------------------------------------|-----------------------------------|
| POST   | `/api/v1/tenders/`                       | Create a new tender               |
| GET    | `/api/v1/tenders/`                       | List tenders (paginated, filtered)|
| GET    | `/api/v1/tenders/{tender_id}`            | Get tender detail                 |
| PATCH  | `/api/v1/tenders/{tender_id}`            | Update tender                     |
| POST   | `/api/v1/tenders/{tender_id}/status`     | Update tender status              |
| POST   | `/api/v1/tenders/{tender_id}/link-tasks` | Link tasks to tender              |

---

### Time Tracking

| Method | Path                                    | Description                     |
|--------|-----------------------------------------|---------------------------------|
| POST   | `/api/v1/time/entries`                  | Create time entry               |
| GET    | `/api/v1/time/entries`                  | List time entries (filtered)    |
| PATCH  | `/api/v1/time/entries/{entry_id}`       | Update time entry               |
| DELETE | `/api/v1/time/entries/{entry_id}`       | Delete time entry               |
| POST   | `/api/v1/time/entries/{entry_id}/start` | Start timer                     |
| POST   | `/api/v1/time/entries/{entry_id}/stop`  | Stop timer                      |

**Filters:** `task_id`, `user_id`, `is_billable`, `date_from`, `date_to`

---

### Warehouse

| Method | Path                                             | Description                      |
|--------|--------------------------------------------------|----------------------------------|
| POST   | `/api/v1/warehouse/items`                        | Create warehouse item            |
| GET    | `/api/v1/warehouse/items`                        | List items (paginated, filtered) |
| GET    | `/api/v1/warehouse/items/{item_id}`              | Get item detail                  |
| PATCH  | `/api/v1/warehouse/items/{item_id}`              | Update item                      |
| POST   | `/api/v1/warehouse/movements`                    | Record movement                  |
| GET    | `/api/v1/warehouse/movements`                    | List movements (filtered)        |
| POST   | `/api/v1/warehouse/reservations`                 | Create reservation               |
| GET    | `/api/v1/warehouse/reservations`                 | List reservations                |
| PATCH  | `/api/v1/warehouse/reservations/{reservation_id}`| Update reservation status        |
| GET    | `/api/v1/warehouse/low-stock`                    | Get items below min_quantity     |

**Item filters:** `category`, `search` (name/SKU)

---

### Depreciation

| Method | Path                                     | Description                       |
|--------|------------------------------------------|-----------------------------------|
| GET    | `/api/v1/depreciation/equipment`         | List equipment with depreciation  |
| GET    | `/api/v1/depreciation/equipment/{eq_id}` | Get equipment depreciation detail |
| POST   | `/api/v1/depreciation/calculate`         | Run depreciation calculation      |
| GET    | `/api/v1/depreciation/report`            | Get depreciation report           |

---

### Documents

| Method | Path                                        | Description                      |
|--------|---------------------------------------------|----------------------------------|
| POST   | `/api/v1/documents/upload`                  | Upload a document (multipart)    |
| GET    | `/api/v1/documents/`                        | List documents (filtered)        |
| GET    | `/api/v1/documents/{document_id}`           | Get document metadata            |
| GET    | `/api/v1/documents/{document_id}/download`  | Download document file           |
| POST   | `/api/v1/documents/{document_id}/version`   | Upload new version               |
| DELETE | `/api/v1/documents/{document_id}`           | Delete document                  |

**Filters:** `task_id`, `doc_type`, `uploaded_by`

---

### References

| Method | Path                                            | Description                     |
|--------|-------------------------------------------------|---------------------------------|
| POST   | `/api/v1/references/`                           | Create a reference dictionary   |
| GET    | `/api/v1/references/`                           | List dictionaries               |
| GET    | `/api/v1/references/{code}`                     | Get dictionary by code          |
| PATCH  | `/api/v1/references/{code}`                     | Update dictionary               |
| POST   | `/api/v1/references/{code}/items`               | Add item to dictionary          |
| PATCH  | `/api/v1/references/{code}/items/{item_id}`     | Update dictionary item          |
| DELETE | `/api/v1/references/{code}/items/{item_id}`     | Delete dictionary item          |

---

### Analytics

| Method | Path                                     | Description                          |
|--------|------------------------------------------|--------------------------------------|
| GET    | `/api/v1/analytics/dashboard`            | Dashboard statistics                 |
| GET    | `/api/v1/analytics/performance/{user_id}`| Employee performance metrics         |
| GET    | `/api/v1/analytics/salary/{user_id}`     | Salary calculation                   |
| GET    | `/api/v1/analytics/tenders`              | Tender analytics                     |

**Query parameters:** `period_days`, `year`, `month`
