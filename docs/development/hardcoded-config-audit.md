# Hardcoded to Config Audit

This document tracks high-impact hardcoded values and where they were moved to configuration.

## Already moved to env/config

| Area | Before | Now | Key / Source |
|---|---|---|---|
| Tasks timeline "due soon" warning threshold | Constant in UI | Env-driven | `NEXT_PUBLIC_TASK_DUE_SOON_MINUTES` |
| Tasks timeline start/end hours | `8..20` in UI | Env-driven | `NEXT_PUBLIC_TASK_TIMELINE_HOUR_START`, `NEXT_PUBLIC_TASK_TIMELINE_HOUR_END` |
| Avatar service URL (DiceBear) | Literal URL in board components | Env-driven | `NEXT_PUBLIC_AVATAR_SERVICE_BASE_URL` |
| Scheduled task creation toggle | Static code-level behavior | Config + DB override | `TASK_SCHEDULER_ENABLED` + `/api/v1/admin/settings/scheduler` |
| Scheduler cron rule | Env-only static cron in beat | Runtime rule from admin settings (DB override supported) | `cron_*` fields in admin scheduler |
| Scheduler payload (title, assignee, due, priority, ids) | Env-only static values | Env defaults + DB override | `task_scheduler_*` settings |

## Persisted runtime admin config

| Setting group | Storage | Read path | Write path |
|---|---|---|---|
| Scheduler runtime settings | PostgreSQL table `system_settings` (JSON value by key) | `GET /api/v1/admin/settings` | `PATCH /api/v1/admin/settings/scheduler` |

## Frontend behavior persistence (session)

| Behavior | Storage | Key |
|---|---|---|
| Last tasks view (`kanban/list/timeline/month`) | `sessionStorage` | `tasks_last_view` |
| Last selected tasks calendar day | `sessionStorage` | `tasks_last_calendar_date` |

## Still hardcoded (recommended next migration)

| Candidate | Current location | Recommendation |
|---|---|---|
| Sidebar brand text / mark (`SPEC CRM`, `S`) | `frontend/src/components/layout/Sidebar.tsx` | Add `NEXT_PUBLIC_APP_BRAND_NAME` / `NEXT_PUBLIC_APP_BRAND_SHORT` |
| Kanban status colors map | `frontend/src/app/tasks/page.tsx` | Keep as code theme constant unless dynamic branding required |
| Some pagination defaults (`limit=200`) | Multiple frontend pages | Move to typed constants (`frontend/src/lib/constants.ts`) |
| Task transition map on task details page | `frontend/src/app/tasks/[id]/page.tsx` | Optionally derive from backend workflow metadata |

## Notes

- Sensitive values (tokens, secrets, passwords, API keys) are intentionally excluded from admin env preview.
- Admin settings API is RBAC-protected (`admin` only) on backend.
