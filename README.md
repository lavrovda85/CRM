# HVAC CRM/ERP Platform

An industry-specific CRM/ERP system for HVAC companies — covering the full cycle from lead to completed installation, with built-in workflow engine, warehouse management, time tracking, tender management, salary calculation, and AI agent integration via the Model Context Protocol (MCP).

## Tech Stack

| Layer            | Technology                        | Version  |
|------------------|-----------------------------------|----------|
| Backend API      | FastAPI + Uvicorn                 | 0.115+   |
| ORM / Migrations | SQLAlchemy 2 (async) + Alembic   | 2.0.36+  |
| Database         | PostgreSQL                        | 16       |
| Cache / Broker   | Redis                             | 7        |
| Task Queue       | Celery (worker + beat)            | 5.4+     |
| Object Storage   | MinIO (S3-compatible)             | latest   |
| Auth / SSO       | Keycloak (OIDC)                   | 25.0     |
| MCP Server       | FastMCP (streamable HTTP)         | 3.1+     |
| Frontend         | Next.js + React + TypeScript      | 15       |
| Reverse Proxy    | Nginx                             | alpine   |
| Serialization    | orjson, Pydantic v2               | —        |
| Logging          | structlog                         | 24.4+    |
| Language         | Python 3.12, TypeScript 5         | —        |

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url> && cd CRM

# 2. Copy and configure environment variables
cp .env.example .env
# Edit .env — set passwords, secrets, and Keycloak client secret

# 3. Start all services
docker compose up -d

# 4. Run database migrations
docker compose exec backend alembic upgrade head

# 5. Open the application
#    Frontend:      http://localhost:3000
#    Backend API:   http://localhost:8000/api/docs
#    Keycloak:      http://localhost:8080
#    MinIO Console: http://localhost:9001
#    MCP Server:    http://localhost:8001/mcp
```

## Architecture Overview

The platform follows a containerized microservice-style architecture orchestrated via Docker Compose. The backend exposes both a REST API (port 8000) and an MCP server (port 8001) from the same codebase. A Celery worker handles background jobs (notifications, depreciation, reports, SLA monitoring), while Celery Beat drives periodic schedules.

For the full C4 architecture description, see [docs/architecture/system-overview.md](docs/architecture/system-overview.md).

## Modules

| Module           | Description                                                                 |
|------------------|-----------------------------------------------------------------------------|
| **Tasks**        | Core task management with template-based workflow engine and checklists      |
| **Templates**    | Reusable task blueprints with configurable workflow, fields, and SLA         |
| **Boards**       | Kanban/Scrum boards for task visualization                                  |
| **Clients**      | Customer management (individuals & organizations) with contacts             |
| **Deals**        | Sales pipeline with configurable stages                                     |
| **Tenders**      | Tender/bid lifecycle tracking with task linking                             |
| **Warehouse**    | Inventory management: stock, reservations, movements, low-stock alerts      |
| **Equipment**    | Tool & equipment tracking with depreciation calculations                    |
| **Time Tracking**| Work hours logging (timer & manual), billable/non-billable split            |
| **Documents**    | File management with versioning, stored in MinIO                            |
| **Analytics**    | Dashboard stats, employee performance, salary calculation, tender analytics |
| **References**   | Dynamic dictionaries (materials, services, work types)                      |
| **Notifications**| Multi-channel delivery: Telegram, web push, email                           |

## MCP Server (AI Agent Integration)

The platform includes a dedicated [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes all core operations as MCP tools. AI agents (Cursor, Claude Desktop, custom agents) can connect and manage the platform programmatically.

**Connection:**

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

**Available tool groups:** Task management, Template management, CRM (clients & deals), Tenders, Warehouse, Analytics.

Full MCP API documentation: [docs/api/mcp-server.md](docs/api/mcp-server.md).

## Development Setup

### Prerequisites

- Docker & Docker Compose v2
- Python 3.12+ (for local backend development)
- Node.js 20+ (for local frontend development)

### Backend (local)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Start infrastructure services
docker compose up -d postgres redis minio keycloak

# Run migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start the MCP server (separate terminal)
python -m app.mcp.server

# Start the Celery worker (separate terminal)
celery -A app.workers.celery_app worker --loglevel=info

# Run tests
pytest --cov=app
```

### Frontend (local)

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

### Linting & Type Checking

```bash
cd backend
ruff check .
mypy app/
```

## Environment Variables

| Variable                         | Description                                 | Default / Example                                  |
|----------------------------------|---------------------------------------------|----------------------------------------------------|
| `POSTGRES_DB`                    | PostgreSQL database name                    | `hvac_crm`                                         |
| `POSTGRES_USER`                  | PostgreSQL user                             | `hvac_admin`                                       |
| `POSTGRES_PASSWORD`              | PostgreSQL password                         | —                                                  |
| `DATABASE_URL`                   | Async connection string (asyncpg)           | `postgresql+asyncpg://user:pass@postgres:5432/db`  |
| `DATABASE_URL_SYNC`              | Sync connection string (for Alembic)        | `postgresql://user:pass@postgres:5432/db`          |
| `REDIS_URL`                      | Redis connection URL                        | `redis://redis:6379/0`                             |
| `CELERY_BROKER_URL`              | Celery broker URL                           | `redis://redis:6379/1`                             |
| `CELERY_RESULT_BACKEND`          | Celery result backend URL                   | `redis://redis:6379/2`                             |
| `MINIO_ENDPOINT`                 | MinIO S3 endpoint                           | `http://minio:9000`                                |
| `MINIO_ACCESS_KEY`               | MinIO access key                            | `minioadmin`                                       |
| `MINIO_SECRET_KEY`               | MinIO secret key                            | —                                                  |
| `MINIO_BUCKET`                   | MinIO bucket for documents                  | `hvac-documents`                                   |
| `KEYCLOAK_URL`                   | Keycloak base URL                           | `http://keycloak:8080`                             |
| `KEYCLOAK_REALM`                 | Keycloak realm name                         | `hvac`                                             |
| `KEYCLOAK_CLIENT_ID`             | Backend client ID in Keycloak               | `hvac-backend`                                     |
| `KEYCLOAK_CLIENT_SECRET`         | Backend client secret                       | —                                                  |
| `SECRET_KEY`                     | Application secret key                      | —                                                  |
| `CORS_ORIGINS`                   | Allowed CORS origins (JSON array)           | `["http://localhost:3000"]`                        |
| `MCP_HOST`                       | MCP server bind host                        | `0.0.0.0`                                          |
| `MCP_PORT`                       | MCP server bind port                        | `8001`                                             |
| `BACKEND_DEBUG`                  | Enable debug mode                           | `false`                                            |
| `TELEGRAM_BOT_TOKEN`             | Telegram bot token for notifications        | —                                                  |
| `NEXT_PUBLIC_API_URL`            | Frontend → Backend API URL                  | `http://localhost:8000/api/v1`                     |
| `NEXT_PUBLIC_WS_URL`             | Frontend → WebSocket URL                    | `ws://localhost:8000/ws`                           |
| `NEXT_PUBLIC_KEYCLOAK_URL`       | Frontend → Keycloak URL                     | `http://localhost:8080`                            |
| `NEXT_PUBLIC_KEYCLOAK_REALM`     | Frontend Keycloak realm                     | `hvac`                                             |
| `NEXT_PUBLIC_KEYCLOAK_CLIENT_ID` | Frontend Keycloak client ID                 | `hvac-frontend`                                    |
| `NEXTAUTH_URL`                   | NextAuth callback URL                       | `http://localhost:3000`                            |
| `NEXTAUTH_SECRET`                | NextAuth secret key                         | —                                                  |

See [`.env.example`](.env.example) for a complete template.

## Project Structure

```
CRM/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/              # REST API route handlers
│   │   │       ├── tasks.py
│   │   │       ├── templates.py
│   │   │       ├── boards.py
│   │   │       ├── clients.py
│   │   │       ├── deals.py
│   │   │       ├── tenders.py
│   │   │       ├── time_tracking.py
│   │   │       ├── warehouse.py
│   │   │       ├── depreciation.py
│   │   │       ├── documents.py
│   │   │       ├── references.py
│   │   │       └── analytics.py
│   │   ├── core/                # Framework configuration
│   │   │   ├── config.py        # pydantic-settings
│   │   │   ├── database.py      # AsyncSession factory
│   │   │   ├── dependencies.py  # FastAPI DI
│   │   │   ├── exceptions.py    # Custom exception hierarchy
│   │   │   ├── pagination.py    # PaginatedResponse
│   │   │   └── security.py      # Keycloak JWT + RBAC
│   │   ├── mcp/                 # Model Context Protocol server
│   │   │   ├── server.py        # FastMCP instance
│   │   │   ├── tools/           # MCP tool definitions
│   │   │   │   ├── task_tools.py
│   │   │   │   ├── template_tools.py
│   │   │   │   ├── crm_tools.py
│   │   │   │   ├── tender_tools.py
│   │   │   │   ├── warehouse_tools.py
│   │   │   │   └── analytics_tools.py
│   │   │   ├── prompts/         # MCP prompt templates
│   │   │   └── resources/       # MCP resource definitions
│   │   ├── models/              # SQLAlchemy ORM models
│   │   │   ├── base.py          # BaseModel (UUID + timestamps)
│   │   │   ├── user.py
│   │   │   ├── client.py
│   │   │   ├── deal.py
│   │   │   ├── tender.py
│   │   │   ├── task_template.py
│   │   │   ├── task.py
│   │   │   ├── task_status.py
│   │   │   ├── board.py
│   │   │   ├── checklist.py
│   │   │   ├── time_entry.py
│   │   │   ├── warehouse_item.py
│   │   │   ├── warehouse_movement.py
│   │   │   ├── equipment.py
│   │   │   ├── depreciation_record.py
│   │   │   ├── document.py
│   │   │   ├── comment.py
│   │   │   ├── notification.py
│   │   │   └── reference.py
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── services/            # Business logic layer
│   │   │   ├── workflow_engine.py
│   │   │   ├── task_service.py
│   │   │   ├── template_service.py
│   │   │   └── document_service.py
│   │   ├── workers/             # Celery async tasks
│   │   │   ├── celery_app.py
│   │   │   ├── notifications.py
│   │   │   ├── depreciation_calc.py
│   │   │   ├── reports.py
│   │   │   └── sla_monitor.py
│   │   └── main.py              # FastAPI app factory
│   ├── migrations/              # Alembic migrations
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── Dockerfile               # Multi-stage: api, mcp, worker, beat
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router pages
│   │   ├── components/          # React components
│   │   ├── lib/                 # API client, WebSocket, utils
│   │   ├── stores/              # State management
│   │   └── types/               # TypeScript type definitions
│   └── package.json
├── docker/
│   ├── keycloak/
│   │   └── hvac-realm.json      # Pre-configured Keycloak realm
│   └── nginx/
│       └── nginx.conf           # Reverse proxy config
├── docs/
│   ├── architecture/
│   │   ├── system-overview.md
│   │   ├── database-schema.md
│   │   └── workflow-engine.md
│   ├── api/
│   │   ├── mcp-server.md
│   │   └── rest-api.md
│   └── adr/
│       └── 001-custom-task-engine.md
├── helm/                        # Kubernetes Helm charts
├── docker-compose.yml
├── .env.example
└── .gitignore
```

## License

MIT
