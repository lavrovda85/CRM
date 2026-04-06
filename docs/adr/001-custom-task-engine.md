# ADR-001: Build Custom Task Engine Instead of Integrating Plane/Taiga

**Date:** 2026-03-01
**Status:** Accepted
**Deciders:** Architecture Team

## Context

The HVAC CRM/ERP platform requires a task management system with the following industry-specific requirements:

1. **Template-based task creation** — reusable blueprints for installation, maintenance, repair, and inspection workflows with configurable custom fields, checklists, and SLA parameters.
2. **Workflow engine with gate conditions** — finite-state machine where transitions between statuses are guarded by role checks, checklist completion, required document uploads, and mandatory field validation.
3. **Auto-actions on transitions** — automatic warehouse stock deductions, time entry closures, and multi-channel notifications triggered by specific status changes.
4. **Deep integration with warehouse, time tracking, and salary modules** — task completion directly affects inventory levels, work hour accounting, and payroll calculations.
5. **MCP-first AI integration** — all task operations must be exposed as Model Context Protocol tools for AI agent automation, with the same business logic as the REST API.

We evaluated three options:

### Option A: Integrate Plane (open-source)

[Plane](https://plane.so/) provides Kanban boards, issues, and modules. However:
- No concept of task templates with configurable custom fields
- No workflow engine with gate conditions or auto-actions
- No built-in warehouse/inventory integration
- Would require significant forking/extension to support HVAC-specific workflows
- Separate database and API surface — duplicated auth, data sync complexity
- MCP integration would require a bridge layer

### Option B: Integrate Taiga (open-source)

[Taiga](https://taiga.io/) offers Scrum/Kanban with custom fields and workflows. However:
- Workflow customization is limited to status ordering, not conditional transitions
- No gate checklists (checklists exist but don't block transitions)
- No auto-action system for warehouse deductions or notifications
- Django-based — different tech stack from our FastAPI backend
- Would require maintaining a separate service with its own PostgreSQL database

### Option C: Build Custom (chosen)

Build a custom task engine within our existing FastAPI/SQLAlchemy codebase:
- `WorkflowEngine` class implementing FSM validation and auto-actions
- `TaskTemplate` model with JSONB `workflow_definition`
- Shared database, shared business logic, shared auth (Keycloak JWT)
- Native MCP tool exposure via the same Python process

## Decision

**Build a custom task engine** within the existing backend codebase.

The task engine is implemented as:
- `TaskTemplate` ORM model with `workflow_definition` (JSONB FSM), `TemplateChecklist`, `TemplateField`, and `TemplateStage` child models
- `WorkflowEngine` service class (`backend/app/services/workflow_engine.py`) with methods: `validate_transition`, `execute_transition`, `get_available_transitions`
- Gate condition validators: `_check_required_roles`, `_check_required_fields`, `_check_required_checklists`, `_check_required_documents`
- Auto-action executors: `_action_deduct_warehouse`, `_action_complete_time_entry`, `_action_notify`
- MCP tools (`task_tools.py`, `template_tools.py`) that call the same service layer
- REST API endpoints (`/api/v1/tasks/`, `/api/v1/templates/`) that call the same service layer

## Consequences

### Positive

- **Full control over workflow semantics** — gate conditions, auto-actions, and the FSM engine are implemented exactly as the HVAC domain requires, with no workarounds or upstream dependency constraints.
- **Single database** — tasks, templates, warehouse, time entries, and salary data live in the same PostgreSQL instance with strong referential integrity and transactional guarantees.
- **Unified auth** — Keycloak JWT validation in one place; no need to synchronize user sessions across services.
- **Native MCP integration** — MCP tools call the same Python service layer as REST endpoints, ensuring consistent business logic without a bridge or adapter.
- **Performance** — no inter-service network calls for task operations; all queries are direct SQL through SQLAlchemy.
- **Simpler deployment** — one backend container serves both REST and MCP; no additional service to deploy, monitor, or upgrade.

### Negative

- **More initial development effort** — building the workflow engine, template system, and Kanban UI from scratch requires more upfront engineering than integrating an existing tool.
- **Maintenance burden** — we own the full task management codebase including edge cases (concurrent transitions, checklist race conditions, template versioning).
- **No community UI** — Plane/Taiga have polished, battle-tested frontends; we must build our own Kanban board, task detail views, and template editors in Next.js.

### Mitigations

- The workflow engine is well-isolated in `WorkflowEngine` with comprehensive validation methods, making it testable and maintainable.
- Template-driven design means adding new workflow types (e.g., "VRF system installation", "duct cleaning") requires only creating a new template in the database — no code changes.
- The frontend Kanban board leverages proven React libraries (dnd-kit) and communicates with the backend via standard REST endpoints.

## Alternatives Considered

| Criteria                    | Plane       | Taiga       | Custom (chosen) |
|-----------------------------|-------------|-------------|-----------------|
| Template-based creation     | ✗           | Partial     | ✓               |
| Gate checklists             | ✗           | ✗           | ✓               |
| Auto-actions (warehouse)    | ✗           | ✗           | ✓               |
| JSONB workflow definition   | ✗           | ✗           | ✓               |
| Same database as CRM        | ✗           | ✗           | ✓               |
| Native MCP tools            | ✗           | ✗           | ✓               |
| Development effort          | Low-Medium  | Medium      | High            |
| Long-term flexibility       | Low         | Medium      | High            |
