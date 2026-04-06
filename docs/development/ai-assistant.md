# AI assistant (OpenAI + MCP tools)

The backend exposes:

- `GET /api/v1/ai-assistant/status` — whether `OPENAI_API_KEY` is set and which model is configured (no secrets).
- `GET /api/v1/ai-assistant/messages` — persisted chat history for the **current user** (JWT `sub`).
- `POST /api/v1/ai-assistant/clear` — delete stored messages + session context for the current user (called on logout from the frontend).
- `POST /api/v1/ai-assistant/chat` — authenticated JSON chat (`{"message":"..."}`); the model may call `invoke_crm_tool` which runs the same `@mcp.tool()` functions as the standalone MCP server, with the **current JWT user** bound via `app.mcp.actor_context`.
- `POST /api/v1/ai-assistant/chat/upload` — **multipart/form-data**: `message` (optional, text hint) + `files` (repeat field name; at least one file). Supported types:
  - **PDF** — text extraction (`pypdf`); scanned PDFs without text: user should upload **page images** (JPEG/PNG/WebP/GIF) for vision.
  - **DOCX** — paragraphs and tables (python-docx).
  - **XLSX / CSV** — tabular text for `bulk_create_tasks` (openpyxl / UTF-8).
  - **Images** — passed to `gpt-4o-mini` as vision (base64 data URLs).  
  Combined extracted text is capped (~80k chars). The model is instructed to parse ТЗ / ведомости работ into tasks via `bulk_create_tasks` or `create_task`.

## Per-user history and session memory

- Messages are stored in PostgreSQL (`ai_assistant_messages`, `ai_assistant_sessions`).
- After successful tools such as `create_task`, the server merges `last_task_id` / `last_task_title` into session JSON and injects them as an extra **system** message on the next turn so follow-ups like «назначь её на …» work without re-listing tasks.
- MCP tool `assign_task_to_user` assigns by name in **one** call (preferred). `search_users` resolves names to UUIDs for manual `update_task` / `create_task`.
- MCP tool `search_tasks` finds tasks by substring in **title**, **description**, or **custom_fields** (e.g. address); use before `delete_task` when the user does not give a UUID.
- Default `AI_ASSISTANT_MAX_TOOL_ROUNDS` is **24** (max 48).

In **debug** mode, `create_all` creates these tables automatically. In production without Alembic, apply equivalent DDL (see model definitions in `app/models/ai_assistant_chat.py`).

## Environment variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key (required for chat). |
| `OPENAI_MODEL` | Model id, default `gpt-4o-mini`. |
| `AI_ASSISTANT_TIMEZONE` | IANA timezone for the **server clock** injected into each assistant turn (default `Europe/Moscow`) so phrases like «сегодня»/«завтра» match the calendar you expect. |
| `AI_ASSISTANT_MAX_TOOL_ROUNDS` | Max tool loop iterations (default **24** in code; Docker Compose default **24**). |

Copy `.env.example` to `.env` and set values locally. Do not commit secrets.

### Docker Compose

The `backend` service must receive these variables. The project `docker-compose.yml` passes
`OPENAI_*` from the **repository root** `.env` into the container (Compose substitutes `${…}` from that file).

After changing `.env`, recreate the backend container:  
`docker compose up -d --force-recreate backend`

### Local `uvicorn` from `backend/`

Settings load `.env` from the **repository root** first, then `backend/.env`, so a single root `.env` works even when the current working directory is `backend/`.

## Frontend

The page `/assistant` provides text input, **file attachments** (paperclip), and optional browser speech recognition (Web Speech API) where supported. With files, the client calls `POST /ai-assistant/chat/upload` via `FormData`.

**Frontend:** the UI keeps a Zustand copy for smooth navigation, but **authoritative history** is loaded from `GET /ai-assistant/messages` and refreshed from each `POST /chat` response. On **logout**, the client calls `POST /ai-assistant/clear` (with the access token) then clears local state.

The assistant system prompt instructs the model to call tools autonomously (derive `title`, resolve templates via `list_templates`, ISO `due_date`). The backend also maps common synonyms (`name`, `subject`, …) to `create_task.title` before invocation so tool calls are less brittle.

## Security

- Rotate any API key that was pasted into chat or committed to git.
- The backend never logs or returns raw API keys.
