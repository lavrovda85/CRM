# MCP Server API Documentation

The HVAC CRM/ERP platform exposes a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that allows AI agents to manage the platform programmatically — creating tasks, checking inventory, generating reports, and more.

## Architecture

The MCP server is built with [FastMCP](https://github.com/jlowin/fastmcp) v3.1+ and runs as a separate container from the REST API, sharing the same Python codebase, ORM models, and business logic.

```
┌──────────────────┐         ┌──────────────────┐
│   AI Agent       │         │   MCP Server     │
│  (Cursor, Claude │◄─MCP──►│   :8001          │
│   Desktop, etc.) │  HTTP   │  FastMCP 3.1+    │
└──────────────────┘         └──────┬───────────┘
                                    │
                         ┌──────────┼──────────┐
                         ▼          ▼          ▼
                    PostgreSQL    Redis      MinIO
```

**Transport:** Streamable HTTP (bidirectional, session-based)
**Port:** 8001 (configurable via `MCP_PORT` env var)
**Endpoint:** `http://<host>:8001/mcp`

## Connection Instructions

### Cursor IDE

Add to your MCP server configuration (`.cursor/mcp.json` or Cursor settings):

```json
{
  "mcpServers": {
    "hvac-crm": {
      "url": "http://localhost:8001/mcp",
      "transport": "streamable-http"
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hvac-crm": {
      "url": "http://localhost:8001/mcp",
      "transport": "streamable-http"
    }
  }
}
```

### Programmatic (Python)

```python
from fastmcp import Client

async with Client("http://localhost:8001/mcp") as client:
    result = await client.call_tool("list_tasks", {"status": "in_progress"})
    print(result)
```

## Authentication

The MCP server validates Keycloak JWT tokens passed in the tool call metadata. AI agents must obtain a valid token from Keycloak before calling tools that require authentication.

**Token retrieval:**

```bash
curl -X POST http://localhost:8080/realms/hvac/protocol/openid-connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=hvac-backend" \
  -d "client_secret=YOUR_CLIENT_SECRET"
```

The token should be passed in tool call metadata as `authorization: Bearer <token>`.

---

## Tools Reference

### Task Management

#### `create_task`

Create a new task in the HVAC CRM/ERP system.

**Arguments:**

| Name           | Type        | Required | Description                                              |
|----------------|-------------|----------|----------------------------------------------------------|
| `title`        | `str`       | Yes      | Task title                                               |
| `template_id`  | `str\|null` | No       | UUID of task template (inherits workflow & checklists)   |
| `client_id`    | `str\|null` | No       | UUID of the client                                       |
| `assigned_to`  | `str\|null` | No       | UUID of the assigned engineer                            |
| `custom_fields`| `dict\|null`| No       | Template field values `{key: value}`                     |
| `priority`     | `str`       | No       | `low`, `medium` (default), `high`, `critical`           |
| `due_date`     | `str\|null` | No       | ISO 8601 datetime (e.g. `2026-04-15T18:00:00Z`)         |

**Returns:** `dict` — created task with `id`, `title`, `status`, `priority`, `template_id`, `client_id`, `assigned_to`, `custom_fields`, `due_date`, `created_at`.

**Example:**

```json
// Request
{
  "tool": "create_task",
  "arguments": {
    "title": "AC Installation — Daikin FTXB35C",
    "template_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "client_id": "e5f6a7b8-c9d0-1234-abcd-ef5678901234",
    "assigned_to": "c9d0e1f2-a3b4-5678-abcd-ef9012345678",
    "priority": "high",
    "due_date": "2026-04-15T18:00:00Z"
  }
}

// Response
{
  "id": "f1234567-89ab-cdef-0123-456789abcdef",
  "title": "AC Installation — Daikin FTXB35C",
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

Update fields of an existing task. Cannot change status — use `transition_task` instead.

**Arguments:**

| Name      | Type   | Required | Description                                              |
|-----------|--------|----------|----------------------------------------------------------|
| `task_id` | `str`  | Yes      | UUID of the task to update                               |
| `fields`  | `dict` | Yes      | Fields to update: `title`, `description`, `priority`, `assigned_to`, `due_date`, `custom_fields` |

**Returns:** `dict` — updated task with `id`, `updated_fields`, `updated_at`, and the changed field values.

**Example:**

```json
// Request
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

// Response
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

Transition a task to a new workflow status. Validates the transition against the template's workflow definition and checks gate checklists.

**Arguments:**

| Name        | Type  | Required | Description                                               |
|-------------|-------|----------|-----------------------------------------------------------|
| `task_id`   | `str` | Yes      | UUID of the task                                          |
| `to_status` | `str` | Yes      | Target status (must be a valid transition from current)   |
| `reason`    | `str` | No       | Audit reason for the transition (default: `""`)           |

**Returns:** `dict` — `id`, `from_status`, `to_status`, `transitioned_at`, `reason`.

**Example:**

```json
// Request
{
  "tool": "transition_task",
  "arguments": {
    "task_id": "f1234567-89ab-cdef-0123-456789abcdef",
    "to_status": "completed",
    "reason": "All work done, signed act uploaded"
  }
}

// Response
{
  "id": "f1234567-89ab-cdef-0123-456789abcdef",
  "from_status": "review",
  "to_status": "completed",
  "transitioned_at": "2026-03-18T16:00:00Z",
  "reason": "All work done, signed act uploaded"
}
```

---

#### `list_tasks`

List tasks with optional filters. Results sorted by creation date (descending).

**Arguments:**

| Name          | Type        | Required | Description                        |
|---------------|-------------|----------|------------------------------------|
| `status`      | `str\|null` | No       | Filter by status                   |
| `assigned_to` | `str\|null` | No       | Filter by assignee UUID            |
| `client_id`   | `str\|null` | No       | Filter by client UUID              |
| `limit`       | `int`       | No       | Max results (default: 50, max: 200)|

**Returns:** `list[dict]` — list of tasks, each with `id`, `title`, `status`, `priority`, `assigned_to`, `client_id`, `due_date`, `created_at`.

---

#### `get_task_detail`

Get full details of a specific task including relations (template, client, assignee, checklists, documents, status history).

**Arguments:**

| Name      | Type  | Required | Description     |
|-----------|-------|----------|-----------------|
| `task_id` | `str` | Yes      | UUID of the task|

**Returns:** `dict` — full task data with nested `template`, `client`, `assignee`, `checklists`, `documents`, `status_history`, `custom_fields`.

---

### Template Management

#### `list_templates`

List available active task templates, optionally filtered by category.

**Arguments:**

| Name       | Type        | Required | Description                                                       |
|------------|-------------|----------|-------------------------------------------------------------------|
| `category` | `str\|null` | No       | `installation`, `maintenance`, `repair`, `inspection`, `general`  |

**Returns:** `list[dict]` — list of templates with `id`, `name`, `category`, `description`, `required_fields`, `sla_config`, `is_active`.

---

#### `create_template`

Create a new task template with workflow and field definitions.

**Arguments:**

| Name                  | Type             | Required | Description                                |
|-----------------------|------------------|----------|--------------------------------------------|
| `name`                | `str`            | Yes      | Template name                              |
| `category`            | `str`            | Yes      | Template category                          |
| `workflow_definition` | `dict`           | Yes      | FSM definition (`states` + `transitions`)  |
| `required_fields`     | `list[dict]\|null`| No      | Field definitions                          |
| `sla_config`          | `dict\|null`     | No       | SLA parameters                             |

**Returns:** `dict` — created template with `id`, `name`, `category`, `workflow_definition`, `required_fields`, `sla_config`, `created_at`.

**Example:**

```json
// Request
{
  "tool": "create_template",
  "arguments": {
    "name": "AC Maintenance",
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

// Response
{
  "id": "tmpl-uuid-...",
  "name": "AC Maintenance",
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

Create a task from a template, inheriting workflow, checklists, and SLA.

**Arguments:**

| Name            | Type        | Required | Description                                       |
|-----------------|-------------|----------|---------------------------------------------------|
| `template_id`   | `str`       | Yes      | UUID of the template                              |
| `client_id`     | `str`       | Yes      | UUID of the client                                |
| `title`         | `str`       | Yes      | Task title                                        |
| `assigned_to`   | `str\|null` | No       | UUID of the assigned engineer                     |
| `custom_fields` | `dict\|null`| No       | Template field values (e.g. `{area_sqm: 45}`)    |

**Returns:** `dict` — created task with `id`, `title`, `status`, `template_id`, `client_id`, `assigned_to`, `custom_fields`, `checklists_created`, `sla_deadline`, `created_at`.

---

### CRM (Clients & Deals)

#### `create_client`

Create a new client (individual or organization).

**Arguments:**

| Name          | Type        | Required | Description                               |
|---------------|-------------|----------|-------------------------------------------|
| `name`        | `str`       | Yes      | Client / organization name                |
| `client_type` | `str`       | No       | `individual` (default) or `organization`  |
| `address`     | `str\|null` | No       | Address                                   |
| `phone`       | `str\|null` | No       | Phone number                              |
| `email`       | `str\|null` | No       | Email address                             |

**Returns:** `dict` — `id`, `name`, `client_type`, `address`, `phone`, `email`, `created_at`.

---

#### `search_clients`

Search clients by name, phone, email, or address (case-insensitive).

**Arguments:**

| Name    | Type  | Required | Description                |
|---------|-------|----------|----------------------------|
| `query` | `str` | Yes      | Search query string        |
| `limit` | `int` | No       | Max results (default: 20)  |

**Returns:** `list[dict]` — matching clients with `id`, `name`, `client_type`, `phone`, `email`, `address`.

---

#### `create_deal`

Create a new deal in the CRM sales pipeline.

**Arguments:**

| Name        | Type        | Required | Description                          |
|-------------|-------------|----------|--------------------------------------|
| `client_id` | `str`       | Yes      | UUID of the client                   |
| `title`     | `str`       | Yes      | Deal title                           |
| `amount`    | `float`     | No       | Deal value (default: 0.0)            |
| `stage_id`  | `str\|null` | No       | UUID of pipeline stage (auto: first) |

**Returns:** `dict` — `id`, `client_id`, `title`, `amount`, `stage_id`, `stage_name`, `created_at`.

---

#### `move_deal`

Move a deal to a different pipeline stage.

**Arguments:**

| Name       | Type  | Required | Description                  |
|------------|-------|----------|------------------------------|
| `deal_id`  | `str` | Yes      | UUID of the deal             |
| `stage_id` | `str` | Yes      | UUID of the target stage     |

**Returns:** `dict` — `id`, `title`, `from_stage`, `to_stage`, `moved_at`.

---

### Tender Management

#### `create_tender`

Create a new tender/bid with initial status "search".

**Arguments:**

| Name          | Type          | Required | Description                      |
|---------------|---------------|----------|----------------------------------|
| `title`       | `str`         | Yes      | Tender title                     |
| `source`      | `str\|null`   | No       | Source platform or customer      |
| `budget`      | `float\|null` | No       | Tender budget                    |
| `deadline`    | `str\|null`   | No       | Bid submission deadline (ISO)    |
| `assigned_to` | `str\|null`   | No       | UUID of responsible manager      |

**Returns:** `dict` — `id`, `title`, `source`, `budget`, `status`, `deadline`, `assigned_to`, `created_at`.

---

#### `update_tender_status`

Update the status of a tender through its lifecycle.

**Arguments:**

| Name        | Type  | Required | Description                                                          |
|-------------|-------|----------|----------------------------------------------------------------------|
| `tender_id` | `str` | Yes      | UUID of the tender                                                   |
| `status`    | `str` | Yes      | `search`, `participation`, `won`, `lost`, `execution`, `completed`  |

**Returns:** `dict` — `id`, `title`, `from_status`, `to_status`, `updated_at`.

---

#### `link_tasks_to_tender`

Link existing tasks to a tender for grouping and reporting.

**Arguments:**

| Name        | Type        | Required | Description                    |
|-------------|-------------|----------|--------------------------------|
| `tender_id` | `str`       | Yes      | UUID of the tender             |
| `task_ids`  | `list[str]` | Yes      | List of task UUIDs to link     |

**Returns:** `dict` — `tender_id`, `linked_count`, `task_ids`, `linked_at`.

---

#### `list_tenders`

List tenders with optional status filter. Sorted by deadline (soonest first).

**Arguments:**

| Name     | Type        | Required | Description                         |
|----------|-------------|----------|-------------------------------------|
| `status` | `str\|null` | No       | Filter by tender status             |
| `limit`  | `int`       | No       | Max results (default: 50, max: 200) |

**Returns:** `list[dict]` — tenders with `id`, `title`, `source`, `budget`, `status`, `deadline`, `assigned_to`, `created_at`.

---

### Warehouse Management

#### `check_stock`

Check warehouse stock levels. Query by specific item or filter by category.

**Arguments:**

| Name       | Type        | Required | Description                                             |
|------------|-------------|----------|---------------------------------------------------------|
| `item_id`  | `str\|null` | No       | UUID of a specific warehouse item                       |
| `category` | `str\|null` | No       | `materials`, `tools`, `consumables`, `equipment`        |

**Returns:** `list[dict]` — items with `id`, `name`, `sku`, `category`, `unit`, `quantity`, `reserved_quantity`, `available`, `min_quantity`, `price`.

---

#### `reserve_materials`

Reserve materials from warehouse for a specific task.

**Arguments:**

| Name      | Type        | Required | Description                                             |
|-----------|-------------|----------|---------------------------------------------------------|
| `task_id` | `str`       | Yes      | UUID of the task                                        |
| `items`   | `list[dict]`| Yes      | Items to reserve: `[{item_id: "uuid", quantity: 5.0}]` |

**Returns:** `dict` — `task_id`, `reserved_items` (list of `{item_id, quantity, status}`), `total_cost`, `reserved_at`.

**Example:**

```json
// Request
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

// Response
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

Record an inventory movement (intake, consumption, write-off, transfer, return).

**Arguments:**

| Name            | Type        | Required | Description                                                 |
|-----------------|-------------|----------|-------------------------------------------------------------|
| `item_id`       | `str`       | Yes      | UUID of the warehouse item                                  |
| `movement_type` | `str`       | Yes      | `intake`, `consumption`, `write_off`, `transfer`, `return`  |
| `quantity`      | `float`     | Yes      | Quantity (always positive)                                  |
| `task_id`       | `str\|null` | No       | UUID of related task (for consumption)                      |
| `reason`        | `str\|null` | No       | Comment / reason                                            |

**Returns:** `dict` — `id`, `item_id`, `movement_type`, `quantity`, `task_id`, `reason`, `new_quantity`, `recorded_at`.

---

### Analytics & Reporting

#### `get_dashboard_stats`

Get aggregated dashboard statistics for the platform.

**Arguments:**

| Name          | Type  | Required | Description                      |
|---------------|-------|----------|----------------------------------|
| `period_days` | `int` | No       | Period in days (default: 30)     |

**Returns:** `dict` with sections:
- `tasks` — `{total, new, in_progress, completed, overdue}`
- `deals` — `{total, total_amount, won_count, won_amount, conversion_rate}`
- `tenders` — `{total, active, won, lost, win_rate}`
- `warehouse` — `{low_stock_items, movements_count, total_consumption_cost}`
- `period_days`, `generated_at`

---

#### `get_employee_performance`

Get performance metrics for a specific employee.

**Arguments:**

| Name          | Type  | Required | Description                  |
|---------------|-------|----------|------------------------------|
| `user_id`     | `str` | Yes      | UUID of the employee         |
| `period_days` | `int` | No       | Period in days (default: 30) |

**Returns:** `dict` — `user_id`, `user_name`, `tasks` (assigned, completed, in_progress, overdue, avg_completion_hours, sla_compliance_rate), `time_entries` (total_hours, billable_hours), `period_days`.

---

#### `calculate_salary`

Calculate salary for an employee based on their `salary_config`, completed tasks, and logged hours.

**Arguments:**

| Name      | Type  | Required | Description                |
|-----------|-------|----------|----------------------------|
| `user_id` | `str` | Yes      | UUID of the employee       |
| `year`    | `int` | Yes      | Year (e.g. 2026)           |
| `month`   | `int` | Yes      | Month (1-12)               |

**Returns:** `dict` — `user_id`, `user_name`, `year`, `month`, `base_salary`, `task_bonus`, `overtime_bonus`, `deductions`, `total`, `breakdown` (list of calculation components).

**Example:**

```json
// Request
{
  "tool": "calculate_salary",
  "arguments": {
    "user_id": "user-uuid-ivanov",
    "year": 2026,
    "month": 3
  }
}

// Response
{
  "user_id": "user-uuid-ivanov",
  "user_name": "Ivanov Sergei",
  "year": 2026,
  "month": 3,
  "base_salary": 50000.0,
  "task_bonus": 18000.0,
  "overtime_bonus": 4500.0,
  "deductions": 0.0,
  "total": 72500.0,
  "breakdown": [
    {"type": "base", "amount": 50000.0, "description": "Base monthly salary"},
    {"type": "task_bonus", "amount": 18000.0, "description": "6 installations x 3000"},
    {"type": "overtime", "amount": 4500.0, "description": "12 overtime hours x 375"}
  ]
}
```

---

#### `get_tender_analytics`

Get analytics on tender participation and success rates.

**Arguments:**

| Name          | Type  | Required | Description                  |
|---------------|-------|----------|------------------------------|
| `period_days` | `int` | No       | Period in days (default: 90) |

**Returns:** `dict` — `funnel` (search, participation, won, lost, execution, completed), `financials` (total_budget, total_won_budget, avg_margin), `by_source` (list of per-source stats), `timing` (avg_days_to_decision, avg_execution_days).

---

## Usage Scenarios

### Scenario 1: AI Agent Creates a Task from Template

An AI agent needs to create a new AC installation task for a client.

```
Agent: "Create an AC installation task for client Petrov"

1. Agent calls list_templates(category="installation")
   → Gets template "AC Installation" with id "tmpl-uuid-123"

2. Agent calls search_clients(query="Petrov")
   → Gets client "Petrov Ivan" with id "client-uuid-456"

3. Agent calls instantiate_template(
     template_id="tmpl-uuid-123",
     client_id="client-uuid-456",
     title="AC Installation — apt. Petrov",
     assigned_to="engineer-uuid-789",
     custom_fields={"area_sqm": 45, "equipment_model": "Daikin FTXB35C"}
   )
   → Task created with checklists, SLA deadline set, status="new"
```

### Scenario 2: AI Agent Checks Warehouse Stock and Reserves Materials

Before starting installation work, an AI agent verifies stock and reserves needed materials.

```
Agent: "Check if we have enough copper tubing and brackets for the installation"

1. Agent calls check_stock(category="materials")
   → Gets all materials with quantities and available stock

2. Agent identifies:
   - Copper tube 6.35mm: available=45m, needed=10m ✓
   - Wall bracket: available=12pcs, needed=2pcs ✓

3. Agent calls reserve_materials(
     task_id="task-uuid-...",
     items=[
       {"item_id": "copper-tube-uuid", "quantity": 10.0},
       {"item_id": "bracket-uuid", "quantity": 2.0}
     ]
   )
   → Materials reserved, total cost calculated

4. If insufficient stock, agent notifies the user:
   "Not enough copper tubing — only 3m available, need 10m.
    Should I create a purchase request?"
```

### Scenario 3: AI Agent Generates Salary Report

An accountant asks the AI agent to prepare salary calculations for the team.

```
Agent: "Calculate salary for engineer Ivanov for March 2026"

1. Agent calls calculate_salary(
     user_id="user-uuid-ivanov",
     year=2026,
     month=3
   )
   → Returns breakdown: base=50000, task_bonus=18000 (6 installations),
     overtime=4500 (12 extra hours), total=72500

2. Agent calls get_employee_performance(
     user_id="user-uuid-ivanov",
     period_days=31
   )
   → Returns: 8 tasks completed, avg 4.2 hours, 95% SLA compliance

3. Agent presents the report:
   "Ivanov S. — March 2026:
    Base salary:     50,000 ₽
    Task bonuses:    18,000 ₽ (6 installations × 3,000 ₽)
    Overtime:         4,500 ₽ (12 hours × 375 ₽)
    Total:           72,500 ₽
    Performance: 8 tasks, 95% SLA compliance"
```
