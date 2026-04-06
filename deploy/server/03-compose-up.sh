#!/usr/bin/env bash
# Build and start CRM stack with docker compose (repo root with docker-compose.yml).
set -euo pipefail

REPO_ROOT="${1:?Usage: $0 /path/to/CRM}"
cd "${REPO_ROOT}"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy deploy/server/env.template.ip to .env and edit secrets."
  exit 1
fi

docker compose -f docker-compose.yml build --parallel
docker compose -f docker-compose.yml up -d

echo "Started. HTTP: http://$(grep -E '^PUBLIC_HOST=' .env | cut -d= -f2- || echo YOUR_IP)/"
