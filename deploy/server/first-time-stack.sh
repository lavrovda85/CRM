#!/usr/bin/env bash
# One-time (or any) full stack + deploy-agent on the server. Run from repository root.
# Usage: bash deploy/server/first-time-stack.sh [/opt/crm]
set -euo pipefail
ROOT="${1:-$(pwd)}"
cd "$ROOT"
COMPOSE=(docker compose -f docker-compose.yml -f deploy/server/docker-compose.ip.yml)
"${COMPOSE[@]}" up -d --build
echo "Stack is up. Admin deploy: set GITHUB_* and ADMIN_DEPLOY_ENABLED in .env, then open Settings → Admin → Deploy."
