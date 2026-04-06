# System Architecture Overview

This document describes the HVAC CRM/ERP platform architecture using the [C4 model](https://c4model.com/) approach — from system context down to key container interactions.

## 1. System Context

The HVAC CRM/ERP Platform is used by HVAC company employees (managers, engineers, warehouse staff, accountants) and integrates with external systems.

**Actors:**

| Actor              | Description                                                  |
|--------------------|--------------------------------------------------------------|
| HVAC Manager       | Creates deals, assigns tasks, tracks tenders                 |
| Field Engineer     | Executes tasks, logs time, fills checklists                  |
| Warehouse Manager  | Manages inventory, processes material requests               |
| Accountant         | Reviews salary reports, depreciation, financial analytics    |
| AI Agent           | Automates operations via MCP (task creation, stock checks)   |

**External Systems:**

| System        | Integration Point              | Purpose                                  |
|---------------|-------------------------------|------------------------------------------|
| Keycloak      | OIDC / JWT                    | Authentication & SSO, role management    |
| MinIO         | S3 API                        | Document & photo storage                 |
| Telegram      | Bot API (via Celery worker)   | Push notifications to field engineers    |
| zakupki.gov   | Manual entry / future parser  | Tender source                            |

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   HVAC Manager   │     │  Field Engineer   │     │  Warehouse Mgr   │
│   Accountant     │     │                  │     │                  │
└───────┬──────────┘     └───────┬──────────┘     └───────┬──────────┘
        │                        │                        │
        └────────────┬───────────┴────────────┬───────────┘
                     │                        │
                     ▼                        ▼
              ┌──────────────┐        ┌──────────────┐
              │   Frontend   │        │  AI Agent    │
              │  (Next.js)   │        │ (MCP Client) │
              └──────┬───────┘        └──────┬───────┘
                     │ REST + WS             │ MCP (HTTP)
                     ▼                       ▼
            ┌────────────────────────────────────────┐
            │       HVAC CRM/ERP Platform            │
            │  ┌──────────┐  ┌───────────┐           │
            │  │ REST API  │  │MCP Server │           │
            │  │ :8000     │  │ :8001     │           │
            │  └─────┬─────┘  └─────┬─────┘           │
            │        └──────┬───────┘                 │
            │               ▼                         │
            │  ┌────────────────────┐                 │
            │  │  Business Logic    │                 │
            │  │  Workflow Engine   │                 │
            │  └────────┬───────────┘                 │
            │           │                             │
            │  ┌────────┴───────────┐                 │
            │  │  Celery Workers    │                 │
            │  │  (notifications,   │                 │
            │  │   SLA, reports)    │                 │
            │  └────────────────────┘                 │
            └──────────────┬─────────────────────────┘
                           │
        ┌──────────┬───────┼───────┬──────────┐
        ▼          ▼       ▼       ▼          ▼
   ┌─────────┐ ┌───────┐ ┌─────┐ ┌────────┐ ┌──────────┐
   │PostgreSQL│ │ Redis │ │MinIO│ │Keycloak│ │ Telegram │
   │  :5432   │ │ :6379 │ │:9000│ │ :8080  │ │  Bot API │
   └─────────┘ └───────┘ └─────┘ └────────┘ └──────────┘
```

## 2. Container Diagram

| Container        | Technology             | Port | Responsibility                                                       |
|------------------|------------------------|------|----------------------------------------------------------------------|
| **Frontend**     | Next.js 15 (React)     | 3000 | Server-side rendered UI, Kanban boards, forms, dashboards            |
| **Backend API**  | FastAPI + Uvicorn      | 8000 | REST API, WebSocket for realtime, JWT validation                     |
| **MCP Server**   | FastMCP (Python)       | 8001 | Model Context Protocol server for AI agent integration               |
| **Celery Worker**| Celery 5.4 (Python)    | —    | Async jobs: notifications, SLA monitoring, depreciation, reports     |
| **Celery Beat**  | Celery Beat            | —    | Periodic task scheduler (SLA checks, depreciation runs)              |
| **PostgreSQL**   | PostgreSQL 16          | 5432 | Primary data store for all entities                                  |
| **Redis**        | Redis 7                | 6379 | Cache layer, Celery broker (db 1), Celery results (db 2)            |
| **MinIO**        | MinIO (S3-compatible)  | 9000 | Object storage for documents, photos, signed acts                    |
| **Keycloak**     | Keycloak 25.0          | 8080 | OIDC identity provider, user management, RBAC                       |
| **Nginx**        | Nginx (alpine)         | 80   | Reverse proxy, static asset serving, SSL termination (prod)          |

### Container Interactions

```
Frontend ──REST/WS──► Backend API ──SQL──► PostgreSQL
                         │
                         ├──S3──► MinIO
                         ├──Redis──► Redis (cache)
                         └──OIDC──► Keycloak (JWT validation)

AI Agent ──MCP/HTTP──► MCP Server ──SQL──► PostgreSQL
                          │
                          ├──S3──► MinIO
                          └──Redis──► Redis

Celery Worker ◄──broker──► Redis
      │
      ├──SQL──► PostgreSQL
      ├──S3──► MinIO
      └──HTTP──► Telegram Bot API

Celery Beat ──broker──► Redis (schedules tasks for Worker)
```

## 3. Key Design Decisions

### Why Custom Task Engine Instead of Plane/Taiga

Off-the-shelf project management tools lack HVAC-specific workflow semantics: gate checklists that block status transitions, automatic warehouse deductions on task completion, SLA enforcement with field-specific deadlines, and template-based task instantiation with configurable custom fields. Building a custom engine gives full control over the finite-state machine and auto-actions while avoiding the overhead of adapting a general-purpose tool.

See [ADR-001](../adr/001-custom-task-engine.md) for the full decision record.

### Why Raw PostgreSQL (No Document DB)

All entities have well-defined relational structures with strong referential integrity requirements (tasks → templates → checklists, warehouse movements → items → tasks). JSONB columns provide the flexibility of document storage where needed (workflow definitions, custom fields, salary configs) without sacrificing transactional guarantees or query performance. PostgreSQL's native JSONB indexing (GIN) handles both structured and semi-structured queries efficiently.

### MCP-First AI Integration

Instead of building a custom chatbot API, the platform implements the Model Context Protocol standard. This allows any MCP-compatible AI client (Cursor, Claude Desktop, custom agents) to connect immediately without bespoke integration code. The MCP server shares the same codebase, models, and business logic as the REST API, ensuring consistency.

## 4. Technology Choices

| Decision                  | Choice                  | Justification                                                                  |
|---------------------------|-------------------------|--------------------------------------------------------------------------------|
| API Framework             | FastAPI                 | Native async, automatic OpenAPI, Pydantic integration, mature ecosystem        |
| ORM                       | SQLAlchemy 2 (async)    | Industry standard, full async support, flexible query building                 |
| Auth                      | Keycloak OIDC           | Enterprise SSO, RBAC, user federation, no auth code to maintain                |
| MCP Library               | FastMCP 3.1+            | Official Python SDK, streamable HTTP transport, decorator-based tools          |
| Task Queue                | Celery + Redis          | Battle-tested, supports periodic tasks (Beat), scales horizontally             |
| Object Storage            | MinIO                   | S3-compatible, self-hosted, drop-in replacement for AWS S3 in production       |
| Frontend                  | Next.js 15              | SSR, App Router, TypeScript-first, large component ecosystem                   |
| Serialization             | orjson                  | 3-10x faster JSON serialization than stdlib, used as FastAPI default           |
| Logging                   | structlog               | Structured JSON logging, context binding, dev-friendly console output          |
| Database                  | PostgreSQL 16           | JSONB, GIN indexes, CTEs, window functions, rock-solid reliability             |
| Validation                | Pydantic v2             | Rust-core performance, seamless FastAPI/SQLAlchemy integration                 |

## 5. Data Flow Diagrams

### 5.1 Task Creation from Template

```
AI Agent / User
      │
      ▼
  [create_task / POST /api/v1/tasks]
      │
      ├─ 1. Resolve TaskTemplate by template_id
      │     └─ Load workflow_definition, checklists, fields, SLA config
      │
      ├─ 2. Determine initial_state from workflow_definition
      │
      ├─ 3. INSERT Task row
      │     └─ status = initial_state, custom_fields = input values
      │
      ├─ 4. Copy TemplateChecklists → Checklist + ChecklistItem rows
      │
      ├─ 5. Calculate sla_deadline from sla_config.max_duration_hours
      │
      ├─ 6. INSERT TaskStatusHistory (initial entry)
      │
      └─ 7. Return created task with checklists
```

### 5.2 Workflow Transition

```
User / AI Agent
      │
      ▼
  [transition_task / POST /api/v1/tasks/{id}/transition]
      │
      ├─ 1. Load Task + Template.workflow_definition
      │
      ├─ 2. Find matching transition (from_status → to_status)
      │     └─ If not found → 409 WORKFLOW_TRANSITION_DENIED
      │
      ├─ 3. Validate conditions:
      │     ├─ Required roles   → user.roles ∩ transition.required_roles
      │     ├─ Required fields  → task.custom_fields[key] not empty
      │     ├─ Gate checklists  → checklist.is_completed == true
      │     └─ Required docs    → COUNT(documents) by type >= min_count
      │
      ├─ 4. Update task.status, set started_at / completed_at
      │
      ├─ 5. INSERT TaskStatusHistory
      │
      ├─ 6. Execute auto_actions:
      │     ├─ deduct_warehouse  → UPDATE warehouse_items, INSERT movement
      │     ├─ complete_time_entry → close open TimeEntry rows
      │     └─ notify            → INSERT Notification + Celery dispatch
      │
      └─ 7. Return updated task
```

### 5.3 File Upload

```
User (Frontend / Mobile)
      │
      ▼
  [POST /api/v1/documents/upload]
      │
      ├─ 1. Validate file (size, MIME type)
      │
      ├─ 2. Generate storage key:  {task_id}/{uuid}/{filename}
      │
      ├─ 3. Upload to MinIO bucket (hvac-documents)
      │     └─ Multipart upload via boto3 / presigned URL
      │
      ├─ 4. INSERT Document row
      │     └─ storage_path, mime_type, file_size, doc_type, label
      │
      ├─ 5. INSERT DocumentVersion (version = 1)
      │
      └─ 6. Return document metadata with download URL
```
