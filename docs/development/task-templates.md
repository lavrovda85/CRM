# Task templates: REST, MCP, AI assistant

## Editing templates

- **REST** (authenticated): `GET/PATCH/POST /api/v1/templates/` — full CRUD, checklists, `workflow_definition`, `required_fields` JSON, `TemplateField` rows (see OpenAPI).
- **MCP tools**: `list_templates`, `get_template`, `create_template`, `update_template`, `delete_template` — same domain; mutating tools **commit** the session so changes persist.

## Creating tasks from a template

### REST

`POST /api/v1/tasks/` with `template_id` copies template checklists and uses `workflow_definition.initial_state` (default `new`).

### MCP / AI assistant

- **`create_task`** with `template_id` calls **`TemplateService.instantiate_template`** (checklists, SLA deadline, `initial_state`, validation of required custom fields — same as `instantiate_template` tool).
- **`instantiate_template`** tool: `client_id` is optional; supports `due_date`, `priority`.

### Required custom fields

Instantiation validates:

1. **`template_fields`** rows with `is_required`.
2. Keys listed in **`task_templates.required_fields`** JSON (string keys or `{"key": "...", "required": true}`).

Put address / phone in `custom_fields` under those keys, not only in the title, or creation returns a validation error (not an internal error).

## Actor / `users.id` (FK fixes)

JWT `sub` may differ from CRM `users.id` (user is keyed by `keycloak_id`). For MCP tools invoked from **AI assistant HTTP**, `invoke_crm_tool` resolves `sub` → `users.id` before execution. REST task endpoints use **`get_crm_user_id`** for `created_by`, history, comments, etc.

Ensure every logged-in user has a row in `users` with matching `keycloak_id` (sync from Keycloak); otherwise resolution raises `NotFoundError`.
