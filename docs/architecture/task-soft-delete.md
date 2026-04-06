# Task soft delete

## Behavior

- `DELETE /api/v1/tasks/{id}` sets `tasks.deleted_at` and `tasks.deleted_by` (no row removal). Related rows (comments, history, warehouse links, etc.) stay in the database.
- Soft-deleted tasks are excluded from:
  - Task list and search (`TaskService.list_tasks`, `search_tasks`, REST `GET /tasks`, MCP `list_tasks` / `search_tasks`)
  - Task detail (`GET /tasks/{id}`, MCP `get_task_detail`) — returns 404 as for missing tasks
  - Board grouping (REST + MCP `get_board`)
  - Dashboard and analytics aggregations (`analytics_read`)
  - Tender task linking validation and bulk attach (`tender_service`)
- **Trash / restore** (admin or manager):
  - `GET /api/v1/tasks/deleted` — paginated list of soft-deleted tasks
  - `POST /api/v1/tasks/{id}/restore` — clears `deleted_at` / `deleted_by`
- MCP: `delete_task` performs soft delete; `restore_task` restores.

## Schema

Columns on `tasks` (see `app/models/task.py`):

| Column      | Type        | Meaning                          |
|------------|-------------|----------------------------------|
| `deleted_at`  | timestamptz NULL | Set when soft-deleted      |
| `deleted_by`  | uuid NULL FK `users(id)` | Who deleted |

Debug startup (`DEBUG=1`) runs `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for these columns when Alembic is not used.

## Query helper

Use `Task.active_filter()` (i.e. `deleted_at IS NULL`) in any new `Task` query that should only see active tasks.
