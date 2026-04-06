#!/usr/bin/env bash
# git pull origin master + rebuild/restart compose (run on server in repo dir).
set -euo pipefail

REPO_ROOT="${1:?Usage: $0 /opt/crm}"
cd "${REPO_ROOT}"

git fetch origin
git checkout master
git pull origin master

docker compose -f docker-compose.yml build --parallel
docker compose -f docker-compose.yml up -d --remove-orphans

echo "Redeploy OK at $(date -Iseconds)"
