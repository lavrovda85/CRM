# Database Schema

PostgreSQL 16 is the primary data store. All tables share a common pattern: UUID primary key (`id`), `created_at`, and `updated_at` timestamps provided by the `BaseModel` mixin.

## Entity-Relationship Overview

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

## Entities

### users

| Column           | Type         | Nullable | Description                                    |
|------------------|-------------|----------|------------------------------------------------|
| `id`             | UUID PK     | No       | Auto-generated UUID                            |
| `keycloak_id`    | VARCHAR(255)| No       | Keycloak subject ID (unique, indexed)          |
| `email`          | VARCHAR(255)| No       | Unique, indexed                                |
| `full_name`      | VARCHAR(255)| No       | Display name                                   |
| `phone`          | VARCHAR(50) | Yes      | Phone number                                   |
| `role`           | VARCHAR(50) | No       | Primary role (admin, manager, engineer, etc.)  |
| `position`       | VARCHAR(255)| Yes      | Job title                                      |
| `telegram_chat_id`| VARCHAR(100)| Yes     | Telegram chat ID for notifications             |
| `salary_config`  | JSONB       | No       | Salary calculation parameters (see below)      |
| `is_active`      | BOOLEAN     | No       | Soft-delete flag                               |
| `notes`          | TEXT        | Yes      | Internal notes                                 |
| `created_at`     | TIMESTAMPTZ | No       | server_default: now()                          |
| `updated_at`     | TIMESTAMPTZ | No       | server_default: now(), onupdate: now()         |

**Indexes:** `keycloak_id` (unique), `email` (unique)

**Relationships:** → assigned_tasks (Task), → time_entries (TimeEntry), → comments (Comment)

---

### clients

| Column        | Type         | Nullable | Description                             |
|---------------|-------------|----------|-----------------------------------------|
| `id`          | UUID PK     | No       | Auto-generated UUID                     |
| `name`        | VARCHAR(500)| No       | Client / organization name (indexed)    |
| `client_type` | VARCHAR(50) | No       | `individual` or `organization`          |
| `address`     | TEXT        | Yes      | Primary address                         |
| `coordinates` | JSONB       | Yes      | GPS coordinates `{lat, lng}`            |
| `phone`       | VARCHAR(50) | Yes      | Primary phone                           |
| `email`       | VARCHAR(255)| Yes      | Email address                           |
| `inn`         | VARCHAR(20) | Yes      | Tax ID (for organizations)              |
| `metadata`    | JSONB       | No       | Extensible metadata                     |
| `notes`       | TEXT        | Yes      | Manager notes                           |
| `created_at`  | TIMESTAMPTZ | No       |                                         |
| `updated_at`  | TIMESTAMPTZ | No       |                                         |

**Indexes:** `name`

**Relationships:** → contacts (ClientContact), → deals (Deal), → tasks (Task)

---

### client_contacts

| Column       | Type         | Nullable | Description                        |
|-------------|-------------|----------|------------------------------------|
| `id`         | UUID PK     | No       |                                    |
| `client_id`  | UUID FK     | No       | → clients.id (CASCADE)            |
| `full_name`  | VARCHAR(255)| No       | Contact person name                |
| `position`   | VARCHAR(255)| Yes      | Job position                       |
| `phone`      | VARCHAR(50) | Yes      |                                    |
| `email`      | VARCHAR(255)| Yes      |                                    |
| `is_primary` | BOOLEAN     | No       | Primary contact flag               |
| `created_at` | TIMESTAMPTZ | No       |                                    |
| `updated_at` | TIMESTAMPTZ | No       |                                    |

**Indexes:** `client_id`

---

### deal_stages

| Column    | Type         | Nullable | Description                           |
|-----------|-------------|----------|---------------------------------------|
| `id`      | UUID PK     | No       |                                       |
| `name`    | VARCHAR(100)| No       | Stage name                            |
| `order`   | INTEGER     | No       | Position in pipeline                  |
| `color`   | VARCHAR(7)  | No       | HEX color for UI (default `#6366f1`) |
| `is_won`  | BOOLEAN     | No       | Marks the "won" stage                 |
| `is_lost` | BOOLEAN     | No       | Marks the "lost" stage                |
| `created_at`| TIMESTAMPTZ| No      |                                       |
| `updated_at`| TIMESTAMPTZ| No      |                                       |

---

### deals

| Column          | Type          | Nullable | Description                         |
|-----------------|--------------|----------|-------------------------------------|
| `id`            | UUID PK      | No       |                                     |
| `client_id`     | UUID FK      | No       | → clients.id (indexed)             |
| `title`         | VARCHAR(500) | No       | Deal title                          |
| `description`   | TEXT         | Yes      |                                     |
| `amount`        | NUMERIC(15,2)| No       | Deal value                          |
| `stage_id`      | UUID FK      | No       | → deal_stages.id (indexed)         |
| `assigned_to`   | UUID FK      | Yes      | → users.id (indexed)               |
| `expected_close` | DATE        | Yes      | Expected close date                 |
| `source`        | VARCHAR(100) | Yes      | Lead source                         |
| `created_at`    | TIMESTAMPTZ  | No       |                                     |
| `updated_at`    | TIMESTAMPTZ  | No       |                                     |

**Indexes:** `client_id`, `stage_id`, `assigned_to`

---

### tenders

| Column              | Type          | Nullable | Description                              |
|---------------------|--------------|----------|------------------------------------------|
| `id`                | UUID PK      | No       |                                          |
| `title`             | VARCHAR(500) | No       | Tender title (indexed)                   |
| `description`       | TEXT         | Yes      |                                          |
| `source`            | VARCHAR(255) | Yes      | Source platform / customer               |
| `budget`            | NUMERIC(15,2)| Yes      | Tender budget                            |
| `our_price`         | NUMERIC(15,2)| Yes      | Our bid amount                           |
| `status`            | VARCHAR(50)  | No       | Lifecycle state (indexed)                |
| `deadline`          | DATE         | Yes      | Bid submission deadline                  |
| `execution_deadline` | DATE        | Yes      | Execution completion deadline            |
| `assigned_to`       | UUID FK      | Yes      | → users.id (indexed)                    |
| `requirements`      | JSONB        | No       | Tender requirements                      |
| `documents_url`     | VARCHAR(1000)| Yes      | External docs link                       |
| `notes`             | TEXT         | Yes      |                                          |
| `created_at`        | TIMESTAMPTZ  | No       |                                          |
| `updated_at`        | TIMESTAMPTZ  | No       |                                          |

**Status values:** `search`, `participation`, `won`, `lost`, `execution`, `completed`

**Indexes:** `title`, `status`, `assigned_to`

---

### task_templates

| Column               | Type         | Nullable | Description                                   |
|----------------------|-------------|----------|-----------------------------------------------|
| `id`                 | UUID PK     | No       |                                               |
| `name`               | VARCHAR(255)| No       | Template name (indexed)                       |
| `category`           | VARCHAR(100)| No       | Category (indexed)                            |
| `description`        | TEXT        | Yes      |                                               |
| `workflow_definition`| JSONB       | No       | FSM definition (see JSONB section below)      |
| `required_fields`    | JSONB       | No       | Field definitions                             |
| `sla_config`         | JSONB       | No       | SLA parameters                                |
| `auto_warehouse`     | JSONB       | No       | Auto-deduction rules                          |
| `required_documents` | JSONB       | No       | Document requirements per stage               |
| `is_active`          | BOOLEAN     | No       | Active template flag                          |
| `created_at`         | TIMESTAMPTZ | No       |                                               |
| `updated_at`         | TIMESTAMPTZ | No       |                                               |

**Category values:** `installation`, `maintenance`, `repair`, `inspection`, `general`

**Indexes:** `name`, `category`

**Relationships:** → stages (TemplateStage), → checklists (TemplateChecklist), → fields (TemplateField), → tasks (Task)

---

### template_stages

| Column        | Type         | Nullable | Description                       |
|---------------|-------------|----------|-----------------------------------|
| `id`          | UUID PK     | No       |                                   |
| `template_id` | UUID FK     | No       | → task_templates.id (CASCADE)    |
| `name`        | VARCHAR(255)| No       | Stage display name                |
| `status_id`   | VARCHAR(100)| No       | Matches workflow_definition state |
| `order`       | INTEGER     | No       | Display order                     |
| `description` | TEXT        | Yes      |                                   |

**Indexes:** `template_id`

---

### template_checklists

| Column           | Type         | Nullable | Description                               |
|------------------|-------------|----------|-------------------------------------------|
| `id`             | UUID PK     | No       |                                           |
| `template_id`    | UUID FK     | No       | → task_templates.id (CASCADE)            |
| `checklist_id`   | VARCHAR(100)| No       | Unique key within template                |
| `title`          | VARCHAR(255)| No       | Checklist display name                    |
| `gate_transition`| VARCHAR(200)| Yes      | Blocked transition (`from->to`)           |
| `items`          | JSONB       | No       | Array of item definitions                 |

**Indexes:** `template_id`

---

### template_fields

| Column         | Type         | Nullable | Description                                 |
|----------------|-------------|----------|---------------------------------------------|
| `id`           | UUID PK     | No       |                                             |
| `template_id`  | UUID FK     | No       | → task_templates.id (CASCADE)              |
| `key`          | VARCHAR(100)| No       | Machine-readable field name                 |
| `label`        | VARCHAR(255)| No       | Human-readable label                        |
| `field_type`   | VARCHAR(50) | No       | string, integer, decimal, enum, reference, address, date |
| `is_required`  | BOOLEAN     | No       | Required field flag                         |
| `options`      | JSONB       | Yes      | Options for enum type                       |
| `ref_table`    | VARCHAR(100)| Yes      | Reference table for reference type          |
| `default_value`| VARCHAR(500)| Yes      | Default value                               |
| `order`        | INTEGER     | No       | Display order                               |

**Indexes:** `template_id`

---

### tasks

| Column         | Type          | Nullable | Description                              |
|----------------|--------------|----------|------------------------------------------|
| `id`           | UUID PK      | No       |                                          |
| `template_id`  | UUID FK      | Yes      | → task_templates.id (indexed)           |
| `board_id`     | UUID FK      | Yes      | → boards.id (indexed)                   |
| `client_id`    | UUID FK      | Yes      | → clients.id (indexed)                  |
| `deal_id`      | UUID FK      | Yes      | → deals.id (indexed)                    |
| `tender_id`    | UUID FK      | Yes      | → tenders.id (indexed)                  |
| `assigned_to`  | UUID FK      | Yes      | → users.id (indexed)                    |
| `created_by`   | UUID FK      | Yes      | → users.id                              |
| `title`        | VARCHAR(500) | No       | Task title (indexed)                     |
| `description`  | TEXT         | Yes      |                                          |
| `status`       | VARCHAR(100) | No       | Current workflow state (indexed)         |
| `priority`     | VARCHAR(20)  | No       | low, medium, high, critical (indexed)   |
| `custom_fields`| JSONB        | No       | Template field values (see below)        |
| `due_date`     | TIMESTAMPTZ  | Yes      | Deadline                                 |
| `started_at`   | TIMESTAMPTZ  | Yes      | Actual start time                        |
| `completed_at` | TIMESTAMPTZ  | Yes      | Actual completion time                   |
| `sla_deadline` | TIMESTAMPTZ  | Yes      | SLA deadline (auto-calculated)           |
| `created_at`   | TIMESTAMPTZ  | No       |                                          |
| `updated_at`   | TIMESTAMPTZ  | No       |                                          |

**Indexes:** `template_id`, `board_id`, `client_id`, `deal_id`, `tender_id`, `assigned_to`, `title`, `status`, `priority`

**Relationships:** → status_history, checklists, time_entries, documents, comments, reservations, equipment_usage

---

### task_status_history

| Column           | Type         | Nullable | Description                          |
|------------------|-------------|----------|--------------------------------------|
| `id`             | UUID PK     | No       |                                      |
| `task_id`        | UUID FK     | No       | → tasks.id (CASCADE, indexed)       |
| `from_status`    | VARCHAR(100)| No       | Previous status                      |
| `to_status`      | VARCHAR(100)| No       | New status                           |
| `changed_by`     | UUID FK     | No       | → users.id                          |
| `reason`         | TEXT        | Yes      | Transition comment                   |
| `transition_data`| JSONB       | No       | Additional transition metadata       |
| `created_at`     | TIMESTAMPTZ | No       |                                      |
| `updated_at`     | TIMESTAMPTZ | No       |                                      |

**Indexes:** `task_id`

---

### boards

| Column        | Type         | Nullable | Description                           |
|---------------|-------------|----------|---------------------------------------|
| `id`          | UUID PK     | No       |                                       |
| `name`        | VARCHAR(255)| No       | Board name                            |
| `description` | TEXT        | Yes      |                                       |
| `board_type`  | VARCHAR(50) | No       | kanban, scrum, tender                 |
| `owner_id`    | UUID FK     | Yes      | → users.id                           |
| `columns`     | JSONB       | No       | Column definitions (status mapping)   |
| `is_archived` | BOOLEAN     | No       | Archive flag                          |
| `created_at`  | TIMESTAMPTZ | No       |                                       |
| `updated_at`  | TIMESTAMPTZ | No       |                                       |

---

### checklists

| Column           | Type         | Nullable | Description                               |
|------------------|-------------|----------|-------------------------------------------|
| `id`             | UUID PK     | No       |                                           |
| `task_id`        | UUID FK     | No       | → tasks.id (CASCADE, indexed)            |
| `title`          | VARCHAR(255)| No       | Checklist name                            |
| `gate_transition`| VARCHAR(200)| Yes      | Blocked transition key (`from->to`)       |
| `is_completed`   | BOOLEAN     | No       | All items completed                       |
| `created_at`     | TIMESTAMPTZ | No       |                                           |
| `updated_at`     | TIMESTAMPTZ | No       |                                           |

**Indexes:** `task_id`

---

### checklist_items

| Column         | Type         | Nullable | Description                          |
|----------------|-------------|----------|--------------------------------------|
| `id`           | UUID PK     | No       |                                      |
| `checklist_id` | UUID FK     | No       | → checklists.id (CASCADE, indexed)  |
| `title`        | VARCHAR(500)| No       | Item text                            |
| `is_completed` | BOOLEAN     | No       | Completion flag                      |
| `completed_by` | UUID FK     | Yes      | → users.id                          |
| `completed_at` | TIMESTAMPTZ | Yes      | Completion timestamp                 |
| `order`        | INTEGER     | No       | Display order                        |
| `created_at`   | TIMESTAMPTZ | No       |                                      |
| `updated_at`   | TIMESTAMPTZ | No       |                                      |

**Indexes:** `checklist_id`

---

### time_entries

| Column            | Type         | Nullable | Description                         |
|-------------------|-------------|----------|-------------------------------------|
| `id`              | UUID PK     | No       |                                     |
| `task_id`         | UUID FK     | No       | → tasks.id (CASCADE, indexed)      |
| `user_id`         | UUID FK     | No       | → users.id (indexed)               |
| `started_at`      | TIMESTAMPTZ | Yes      | Timer start                         |
| `ended_at`        | TIMESTAMPTZ | Yes      | Timer end                           |
| `duration_minutes`| INTEGER     | No       | Duration (calculated or manual)     |
| `entry_type`      | VARCHAR(20) | No       | `timer` or `manual`                 |
| `is_billable`     | BOOLEAN     | No       | Billable flag (default true)        |
| `notes`           | TEXT        | Yes      |                                     |
| `created_at`      | TIMESTAMPTZ | No       |                                     |
| `updated_at`      | TIMESTAMPTZ | No       |                                     |

**Indexes:** `task_id`, `user_id`

---

### warehouse_items

| Column             | Type          | Nullable | Description                          |
|--------------------|--------------|----------|--------------------------------------|
| `id`               | UUID PK      | No       |                                      |
| `name`             | VARCHAR(500) | No       | Item name (indexed)                  |
| `sku`              | VARCHAR(100) | No       | SKU code (unique, indexed)           |
| `category`         | VARCHAR(100) | No       | materials, tools, consumables, equipment (indexed) |
| `unit`             | VARCHAR(20)  | No       | Unit of measure (pcs, m, kg, l)      |
| `quantity`         | NUMERIC(15,3)| No       | Current stock quantity               |
| `reserved_quantity`| NUMERIC(15,3)| No       | Reserved for tasks                   |
| `min_quantity`     | NUMERIC(15,3)| No       | Low-stock alert threshold            |
| `price`            | NUMERIC(15,2)| No       | Unit price                           |
| `description`      | TEXT         | Yes      |                                      |
| `location`         | VARCHAR(255) | Yes      | Storage location                     |
| `created_at`       | TIMESTAMPTZ  | No       |                                      |
| `updated_at`       | TIMESTAMPTZ  | No       |                                      |

**Indexes:** `name`, `sku` (unique), `category`

---

### warehouse_movements

| Column         | Type          | Nullable | Description                              |
|----------------|--------------|----------|------------------------------------------|
| `id`           | UUID PK      | No       |                                          |
| `item_id`      | UUID FK      | No       | → warehouse_items.id (indexed)          |
| `task_id`      | UUID FK      | Yes      | → tasks.id (indexed)                    |
| `user_id`      | UUID FK      | No       | → users.id                              |
| `movement_type`| VARCHAR(50)  | No       | intake, consumption, write_off, transfer, return (indexed) |
| `quantity`     | NUMERIC(15,3)| No       | Movement quantity (always positive)      |
| `unit_price`   | NUMERIC(15,2)| Yes      | Price at movement time                   |
| `reason`       | TEXT         | Yes      | Comment / reason                         |
| `destination`  | VARCHAR(255) | Yes      | Transfer destination                     |
| `created_at`   | TIMESTAMPTZ  | No       |                                          |
| `updated_at`   | TIMESTAMPTZ  | No       |                                          |

**Indexes:** `item_id`, `task_id`, `movement_type`

---

### warehouse_reservations

| Column     | Type          | Nullable | Description                               |
|-----------|--------------|----------|-------------------------------------------|
| `id`       | UUID PK      | No       |                                           |
| `item_id`  | UUID FK      | No       | → warehouse_items.id (indexed)           |
| `task_id`  | UUID FK      | No       | → tasks.id (indexed)                     |
| `quantity` | NUMERIC(15,3)| No       | Reserved quantity                         |
| `status`   | VARCHAR(50)  | No       | reserved, consumed, cancelled             |
| `created_at`| TIMESTAMPTZ | No       |                                           |
| `updated_at`| TIMESTAMPTZ | No       |                                           |

**Indexes:** `item_id`, `task_id`

---

### equipment

| Column              | Type          | Nullable | Description                          |
|---------------------|--------------|----------|--------------------------------------|
| `id`                | UUID PK      | No       |                                      |
| `name`              | VARCHAR(500) | No       | Equipment name (indexed)             |
| `serial_number`     | VARCHAR(200) | No       | Serial number (unique, indexed)      |
| `category`          | VARCHAR(100) | No       | power_tool, measuring, hand_tool, safety, vehicle (indexed) |
| `purchase_price`    | NUMERIC(15,2)| No       | Original price                       |
| `purchase_date`     | DATE         | No       |                                      |
| `service_life_months`| INTEGER     | No       | Expected service life                |
| `current_value`     | NUMERIC(15,2)| No       | Current book value                   |
| `status`            | VARCHAR(50)  | No       | active, maintenance, written_off, lost (indexed) |
| `assigned_to`       | UUID FK      | Yes      | → users.id                          |
| `location`          | VARCHAR(255) | Yes      |                                      |
| `notes`             | TEXT         | Yes      |                                      |
| `created_at`        | TIMESTAMPTZ  | No       |                                      |
| `updated_at`        | TIMESTAMPTZ  | No       |                                      |

**Indexes:** `name`, `serial_number` (unique), `category`, `status`

---

### equipment_usage

| Column        | Type         | Nullable | Description                     |
|---------------|-------------|----------|---------------------------------|
| `id`          | UUID PK     | No       |                                 |
| `equipment_id`| UUID FK     | No       | → equipment.id (indexed)       |
| `task_id`     | UUID FK     | No       | → tasks.id (indexed)           |
| `user_id`     | UUID FK     | No       | → users.id                     |
| `hours_used`  | NUMERIC(8,2)| No       | Usage duration in hours         |
| `notes`       | TEXT        | Yes      |                                 |
| `created_at`  | TIMESTAMPTZ | No       |                                 |
| `updated_at`  | TIMESTAMPTZ | No       |                                 |

**Indexes:** `equipment_id`, `task_id`

---

### depreciation_records

| Column           | Type          | Nullable | Description                        |
|------------------|--------------|----------|------------------------------------|
| `id`             | UUID PK      | No       |                                    |
| `equipment_id`   | UUID FK      | No       | → equipment.id (CASCADE, indexed) |
| `period_date`    | DATE         | No       | First day of the month             |
| `amount`         | NUMERIC(15,2)| No       | Depreciation for this period       |
| `accumulated`    | NUMERIC(15,2)| No       | Total accumulated depreciation     |
| `remaining_value`| NUMERIC(15,2)| No       | Book value after this period       |
| `method`         | VARCHAR(50)  | No       | straight_line, declining_balance   |
| `notes`          | TEXT         | Yes      |                                    |
| `created_at`     | TIMESTAMPTZ  | No       |                                    |
| `updated_at`     | TIMESTAMPTZ  | No       |                                    |

**Indexes:** `equipment_id`

---

### documents

| Column        | Type          | Nullable | Description                               |
|---------------|--------------|----------|-------------------------------------------|
| `id`          | UUID PK      | No       |                                           |
| `task_id`     | UUID FK      | Yes      | → tasks.id (SET NULL, indexed)           |
| `uploaded_by` | UUID FK      | No       | → users.id                               |
| `doc_type`    | VARCHAR(50)  | No       | photo, signed_act, invoice, report, other (indexed) |
| `label`       | VARCHAR(200) | Yes      | Semantic label (e.g. indoor_unit_installed)|
| `filename`    | VARCHAR(500) | No       | Original filename                         |
| `storage_path`| VARCHAR(1000)| No       | MinIO path (bucket/key)                   |
| `mime_type`   | VARCHAR(100) | No       | MIME type                                 |
| `file_size`   | BIGINT       | No       | Size in bytes                             |
| `version`     | INTEGER      | No       | Current version number                    |
| `metadata`    | JSONB        | No       | EXIF, GPS, signatures, etc.               |
| `description` | TEXT         | Yes      |                                           |
| `created_at`  | TIMESTAMPTZ  | No       |                                           |
| `updated_at`  | TIMESTAMPTZ  | No       |                                           |

**Indexes:** `task_id`, `doc_type`

---

### document_versions

| Column        | Type          | Nullable | Description                        |
|---------------|--------------|----------|------------------------------------|
| `id`          | UUID PK      | No       |                                    |
| `document_id` | UUID FK      | No       | → documents.id (CASCADE, indexed) |
| `version`     | INTEGER      | No       | Version number                     |
| `storage_path`| VARCHAR(1000)| No       | MinIO path for this version        |
| `file_size`   | BIGINT       | No       | Size in bytes                      |
| `uploaded_by` | UUID FK      | No       | → users.id                        |
| `created_at`  | TIMESTAMPTZ  | No       |                                    |
| `updated_at`  | TIMESTAMPTZ  | No       |                                    |

**Indexes:** `document_id`

---

### comments

| Column        | Type         | Nullable | Description                          |
|---------------|-------------|----------|--------------------------------------|
| `id`          | UUID PK     | No       |                                      |
| `task_id`     | UUID FK     | No       | → tasks.id (CASCADE, indexed)       |
| `author_id`   | UUID FK     | No       | → users.id                          |
| `body`        | TEXT        | No       | Comment text (Markdown supported)    |
| `mentions`    | JSONB       | No       | Array of mentioned user UUIDs        |
| `attachments` | JSONB       | No       | Array of attached document UUIDs     |
| `created_at`  | TIMESTAMPTZ | No       |                                      |
| `updated_at`  | TIMESTAMPTZ | No       |                                      |

**Indexes:** `task_id`

---

### notifications

| Column        | Type         | Nullable | Description                              |
|---------------|-------------|----------|------------------------------------------|
| `id`          | UUID PK     | No       |                                          |
| `user_id`     | UUID FK     | No       | → users.id (indexed)                    |
| `channel`     | VARCHAR(50) | No       | telegram, web_push, email                |
| `event_type`  | VARCHAR(100)| No       | task_assigned, status_changed, etc. (indexed) |
| `title`       | VARCHAR(500)| No       | Notification title                       |
| `body`        | TEXT        | No       | Notification body                        |
| `data`        | JSONB       | No       | Structured event data                    |
| `is_read`     | BOOLEAN     | No       | Read flag                                |
| `is_delivered` | BOOLEAN    | No       | Delivery confirmation                    |
| `created_at`  | TIMESTAMPTZ | No       |                                          |
| `updated_at`  | TIMESTAMPTZ | No       |                                          |

**Indexes:** `user_id`, `event_type`

---

### references

| Column       | Type         | Nullable | Description                          |
|-------------|-------------|----------|--------------------------------------|
| `id`         | UUID PK     | No       |                                      |
| `code`       | VARCHAR(100)| No       | Dictionary code (unique, indexed)    |
| `name`       | VARCHAR(255)| No       | Display name                         |
| `description`| VARCHAR(1000)| Yes     |                                      |
| `is_system`  | BOOLEAN     | No       | System dictionary (non-deletable)    |
| `created_at` | TIMESTAMPTZ | No       |                                      |
| `updated_at` | TIMESTAMPTZ | No       |                                      |

**Indexes:** `code` (unique)

---

### reference_items

| Column        | Type         | Nullable | Description                     |
|---------------|-------------|----------|---------------------------------|
| `id`          | UUID PK     | No       |                                 |
| `reference_id`| UUID FK     | No       | → references.id (CASCADE, indexed) |
| `code`        | VARCHAR(100)| No       | Item code                       |
| `name`        | VARCHAR(500)| No       | Display name                    |
| `metadata`    | JSONB       | No       | Extra attributes (unit, price)  |
| `order`       | INTEGER     | No       | Sort order                      |
| `is_active`   | BOOLEAN     | No       | Active flag                     |
| `created_at`  | TIMESTAMPTZ | No       |                                 |
| `updated_at`  | TIMESTAMPTZ | No       |                                 |

**Indexes:** `reference_id`

---

## JSONB Field Structures

### workflow_definition (task_templates)

The core finite-state machine definition stored as JSONB:

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

See [Workflow Engine Documentation](workflow-engine.md) for detailed semantics.

### custom_fields (tasks)

Template-defined fields filled at task level:

```json
{
  "area_sqm": 45.0,
  "equipment_model": "Daikin FTXB35C",
  "floor": 7,
  "address": "Moscow, Lenin St. 15, apt 42",
  "materials_used": [
    {"item_id": "uuid-copper-tube", "quantity": 10.0},
    {"item_id": "uuid-bracket", "quantity": 2.0}
  ],
  "customer_signature": true,
  "installation_notes": "Wall mount, east side"
}
```

### salary_config (users)

Per-employee salary calculation parameters:

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
