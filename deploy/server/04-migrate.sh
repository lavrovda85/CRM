#!/usr/bin/env bash
# Apply Alembic migrations (backend container). Use the same compose files as for `up`.
set -euo pipefail

REPO_ROOT="${1:?Usage: $0 /path/to/CRM}"

cd "${REPO_ROOT}"

if docker info >/dev/null 2>&1; then
  DC=(docker compose)
else
  DC=(sudo docker compose)
fi

if [[ -f deploy/server/docker-compose.ip.yml ]]; then
  COMPOSE=("${DC[@]}" -f docker-compose.yml -f deploy/server/docker-compose.ip.yml)
else
  COMPOSE=("${DC[@]}" -f docker-compose.yml)
fi

echo "Running: alembic upgrade head in backend..."
"${COMPOSE[@]}" exec -T backend alembic upgrade head
echo "Migrations OK."
