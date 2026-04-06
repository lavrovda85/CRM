# Workflow Engine

The workflow engine is a finite-state machine (FSM) that controls task lifecycle transitions. It is implemented in `backend/app/services/workflow_engine.py` as the `WorkflowEngine` class and is the core business logic layer of the platform.

## Overview

Every task can be associated with a `TaskTemplate` that defines a `workflow_definition` — a JSONB field describing the states a task can pass through, the allowed transitions between them, and conditions that must be met before each transition is permitted.

```
┌─────────┐   transition   ┌─────────────┐   transition   ┌───────────┐
│  new     │──────────────►│ in_progress  │──────────────►│ completed  │
│ (initial)│               │(intermediate)│               │  (final)   │
└─────────┘               └─────────────┘               └───────────┘
      │                                                       ▲
      │              transition                               │
      └───────────────────────────────────────────────────────┘
                    (if no intermediate steps)
```

## Workflow Definition (JSON Structure)

The `workflow_definition` is stored as JSONB on the `task_templates` table. It has two top-level keys: `states` and `transitions`, plus an `initial_state` indicator.

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

### Pydantic Validation

The JSON structure is parsed and validated at runtime by the `WorkflowDefinition` and `WorkflowTransition` Pydantic models (see `backend/app/schemas/template.py`).

## State Types

| Type           | Semantics                                                             |
|----------------|-----------------------------------------------------------------------|
| `initial`      | The entry point. Tasks start in this state when created from template. Only one initial state per workflow. The engine reads `initial_state` to determine which state to assign on task creation. |
| `intermediate` | A working state. Tasks spend time here while actions are being performed (site survey, installation, review, etc.). |
| `final`        | Successful completion. When a task reaches a final state, `completed_at` is set. No further transitions are expected. |
| `terminal`     | Dead end without successful completion (cancelled, rejected). `completed_at` is NOT set. No further transitions. |

The engine sets lifecycle timestamps automatically:
- `started_at` is set on the first transition out of `initial` (unless the target is also `cancelled`)
- `completed_at` is set when entering a `final` state (`completed`, `done`, `closed`)

## Transition Conditions

Each transition can specify zero or more conditions. All conditions must be satisfied for the transition to proceed. If any condition fails, a `WorkflowTransitionError` (HTTP 409) is raised with details about which conditions were not met.

### Required Roles

```json
{
  "from": "review",
  "to": "completed",
  "required_roles": ["manager"]
}
```

The user performing the transition must have **at least one** of the listed roles (extracted from the Keycloak JWT `realm_access.roles`). If the list is empty, any authenticated user can perform the transition.

### Required Fields

```json
{
  "from": "site_survey",
  "to": "in_progress",
  "required_fields": ["area_sqm", "equipment_model", "floor"]
}
```

The engine checks that all listed fields have non-empty values. It first checks the task's standard ORM columns, then falls back to `custom_fields` JSONB. A field is considered empty if it is `null`, an empty string, or missing from both sources.

### Required Checklists

```json
{
  "from": "in_progress",
  "to": "review",
  "required_checklists": ["installation_checklist"]
}
```

The engine looks up `Checklist` rows attached to the task where `title` or `gate_transition` matches. The gate_transition format is `"from->to"` (e.g. `"in_progress->review"`). All items in matching checklists must be marked `is_completed = true`.

Checklists are created automatically when a task is instantiated from a template (copied from `TemplateChecklist` rows). Each checklist item maps to a `ChecklistItem` row that individual users can toggle.

### Required Documents

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

The engine counts `Document` rows attached to the task grouped by `doc_type`. Each requirement specifies a document type and the minimum number of uploads needed. The transition is blocked until all minimums are met.

## Auto-Actions

Transitions can trigger automatic side effects after the status change is committed. These are defined in the `auto_actions` array of each transition.

### `deduct_warehouse`

Automatically deducts materials from warehouse stock based on the task's `custom_fields`.

```json
{
  "type": "deduct_warehouse",
  "from_field": "materials_used"
}
```

**Behavior:**

1. Read `task.custom_fields[from_field]` (defaults to `"materials_used"`)
2. Expect an array of `{"item_id": "uuid", "quantity": N}`
3. For each item:
   - Verify `available = quantity - reserved_quantity >= requested`
   - Subtract from `WarehouseItem.quantity`
   - Create a `WarehouseMovement` record with `movement_type = "consumption"`
4. If stock is insufficient, raise `WarehouseInsufficientStockError` (rolls back the transition)

### `complete_time_entry`

Closes all open (running) time entries for the task.

```json
{
  "type": "complete_time_entry"
}
```

**Behavior:**

1. Find all `TimeEntry` rows where `task_id` matches and `ended_at IS NULL`
2. Set `ended_at = now()`
3. Calculate `duration_minutes = (ended_at - started_at) / 60`

This is typically used on transitions to `review` or `completed` to ensure no timers are left running.

### `notify`

Creates notification records and dispatches them via Celery.

```json
{
  "type": "notify",
  "channel": "telegram",
  "template": "task_completed"
}
```

**Behavior:**

1. Determine recipients: task assignee + task creator (if different)
2. Create `Notification` row for each recipient with `channel`, `event_type`, title, and body
3. Dispatch `send_task_notification` Celery task for async delivery

**Channels:** `telegram`, `web_push`, `email`

## How to Create Custom Workflow Templates

### Step 1: Define States

List all meaningful states your workflow will have. Include at least one `initial` and one `final` state.

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

### Step 2: Define Transitions

For each pair of states that should be connected, create a transition object specifying the conditions and auto-actions.

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

### Step 3: Create Checklists

Add `TemplateChecklist` rows to the template, each with a `gate_transition` matching the transition it should block:

```json
{
  "checklist_id": "diagnostics_checklist",
  "title": "Diagnostics Checklist",
  "gate_transition": "diagnostics->awaiting_parts",
  "items": [
    "Check power supply",
    "Measure refrigerant pressure",
    "Inspect compressor",
    "Check condensate drain",
    "Test thermostat"
  ]
}
```

### Step 4: Define Custom Fields

Add `TemplateField` rows for data that engineers must fill in:

| key                | label             | field_type | is_required |
|--------------------|-------------------|------------|-------------|
| `defect_description`| Defect Description| string     | true        |
| `parts_needed`     | Parts Needed      | string     | false       |
| `equipment_model`  | Equipment Model   | reference  | true        |
| `repair_cost`      | Estimated Cost    | decimal    | false       |

### Step 5: Configure SLA

Set SLA deadlines and warning thresholds:

```json
{
  "max_duration_hours": 72,
  "warning_at_percent": 75
}
```

The Celery Beat SLA monitor (`sla_monitor.py`) periodically checks tasks against their `sla_deadline` and sends warnings when the threshold is reached.

---

## Example: AC Installation Workflow (Step-by-Step)

This example traces a complete AC installation task through its workflow.

### Template Definition

**Template name:** AC Installation
**Category:** installation

**States:**

| State        | Type          | Description                                    |
|-------------|---------------|------------------------------------------------|
| `new`        | initial       | Task created, not yet started                  |
| `site_survey`| intermediate  | Engineer visits site to assess conditions       |
| `in_progress`| intermediate  | Active installation work                        |
| `review`     | intermediate  | Manager reviews work and documents              |
| `completed`  | final         | Installation accepted by customer               |
| `cancelled`  | terminal      | Task cancelled                                  |

### Walkthrough

#### 1. Task Creation

A manager creates a task from the "AC Installation" template for client Petrov:

```
POST /api/v1/templates/{template_id}/instantiate
{
  "client_id": "client-uuid",
  "title": "AC Install — apt. Petrov",
  "assigned_to": "engineer-uuid",
  "custom_fields": {"equipment_model": "Daikin FTXB35C", "floor": 7}
}
```

**Result:**
- Task created with `status = "new"`
- 3 checklists created from template (Site Survey, Installation, Final Review)
- `sla_deadline` calculated from `sla_config.max_duration_hours`

#### 2. Start Site Survey (`new` → `site_survey`)

The engineer starts work:

```
POST /api/v1/tasks/{task_id}/transition
{"to_status": "site_survey"}
```

**Conditions checked:**
- ✅ Required roles: `["engineer", "manager"]` — engineer has the role
- No required fields, checklists, or documents

**Side effects:**
- `task.started_at` is set (first transition from initial state)
- `TaskStatusHistory` entry recorded

#### 3. Complete Survey (`site_survey` → `in_progress`)

After visiting the site, the engineer fills in the site survey checklist and required fields:

```
POST /api/v1/tasks/{task_id}/transition
{"to_status": "in_progress"}
```

**Conditions checked:**
- ✅ Required roles: `["engineer"]`
- ✅ Required fields: `area_sqm`, `equipment_model` — both filled in custom_fields
- ✅ Required checklists: `"site_survey_checklist"` — all items checked
- ✅ Required documents: 2 photos uploaded (`doc_type = "photo"`)

#### 4. Complete Installation (`in_progress` → `review`)

The engineer finishes the installation and fills in the installation checklist:

```
POST /api/v1/tasks/{task_id}/transition
{"to_status": "review"}
```

**Conditions checked:**
- ✅ Required checklists: `"installation_checklist"` — all items checked

**Auto-actions executed:**
1. **`deduct_warehouse`** — reads `custom_fields.materials_used`:
   - Deducts 10m copper tubing from stock
   - Deducts 2 wall brackets from stock
   - Creates `WarehouseMovement` records
2. **`complete_time_entry`** — closes the engineer's running timer

#### 5. Manager Approval (`review` → `completed`)

The manager reviews the work, confirms the signed acceptance act is uploaded:

```
POST /api/v1/tasks/{task_id}/transition
{"to_status": "completed", "reason": "Customer signed acceptance act"}
```

**Conditions checked:**
- ✅ Required roles: `["manager"]`
- ✅ Required documents: 1 `signed_act` uploaded

**Auto-actions executed:**
1. **`notify`** — sends Telegram notification to the engineer and the manager:
   > "Task 'AC Install — apt. Petrov' completed"

**Side effects:**
- `task.completed_at` is set
- `TaskStatusHistory` entry with reason recorded
- Task appears as "completed" on the Kanban board

### State Diagram

```
                    ┌──────────┐
                    │   new    │
                    │ (initial)│
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
                    │ (final)  │
                    └──────────┘

   Any state ──────► cancelled (terminal)
```
